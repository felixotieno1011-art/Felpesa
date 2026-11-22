"""Reconciliation: prove the ledger is correct.

Two independent checks, both essential:

  Check A — For every transaction, SUM(debits) == SUM(credits).
            This proves the double-entry rule was applied correctly.
            If this fails, there is a bug in transfer_service: a transaction
            was written without balanced entries.

  Check B — For every wallet, wallet.balance == SUM(credits) - SUM(debits)
            across all its ledger entries. This proves the cached balance
            column (used for fast reads) matches the ledger (the truth).
            If this fails, transfer_service forgot to update the cache,
            or an admin script corrupted it.

Why both? They catch different bugs. Check A catches "the ledger itself
is malformed". Check B catches "the ledger is fine, but the cache drifted".
An accountant would insist on both.
"""
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LedgerEntry, Transaction, Wallet
from app.schemas.reconciliation import (
    LedgerAnomaly,
    ReconciliationReport,
    WalletAnomaly,
)


async def check_transaction_balance(db: AsyncSession) -> list[LedgerAnomaly]:
    """Return all transactions where SUM(debits) != SUM(credits)."""
    debit_sum = func.coalesce(
        func.sum(case((LedgerEntry.direction == "debit", LedgerEntry.amount), else_=0)),
        Decimal("0"),
    )
    credit_sum = func.coalesce(
        func.sum(case((LedgerEntry.direction == "credit", LedgerEntry.amount), else_=0)),
        Decimal("0"),
    )

    stmt = (
        select(
            Transaction.id,
            debit_sum.label("debit_total"),
            credit_sum.label("credit_total"),
        )
        .join(LedgerEntry, LedgerEntry.transaction_id == Transaction.id)
        .group_by(Transaction.id)
        .having(debit_sum != credit_sum)
    )

    rows = (await db.execute(stmt)).all()
    return [
        LedgerAnomaly(
            transaction_id=r.id,
            debit_total=r.debit_total,
            credit_total=r.credit_total,
            difference=r.debit_total - r.credit_total,
        )
        for r in rows
    ]


async def check_wallet_balance(db: AsyncSession) -> list[WalletAnomaly]:
    """Return all wallets whose cached balance != ledger-derived balance."""
    credit_sum = func.coalesce(
        func.sum(case((LedgerEntry.direction == "credit", LedgerEntry.amount), else_=0)),
        Decimal("0"),
    )
    debit_sum = func.coalesce(
        func.sum(case((LedgerEntry.direction == "debit", LedgerEntry.amount), else_=0)),
        Decimal("0"),
    )
    ledger_balance = (credit_sum - debit_sum).label("ledger_balance")

    stmt = (
        select(Wallet.id, Wallet.balance, ledger_balance)
        .outerjoin(LedgerEntry, LedgerEntry.wallet_id == Wallet.id)
        .group_by(Wallet.id, Wallet.balance)
        .having(Wallet.balance != ledger_balance)
    )

    rows = (await db.execute(stmt)).all()
    return [
        WalletAnomaly(
            wallet_id=r.id,
            cached_balance=r.balance,
            ledger_balance=r.ledger_balance,
            difference=r.balance - r.ledger_balance,
        )
        for r in rows
    ]


async def full_reconciliation(db: AsyncSession) -> ReconciliationReport:
    """Run both checks, return a structured report."""
    checked_tx = int(
        (await db.scalar(select(func.count(Transaction.id)))) or 0
    )
    checked_wallets = int(
        (await db.scalar(select(func.count(Wallet.id)))) or 0
    )

    unbalanced = await check_transaction_balance(db)
    mismatched = await check_wallet_balance(db)

    return ReconciliationReport(
        ok=(not unbalanced and not mismatched),
        checked_transactions=checked_tx,
        checked_wallets=checked_wallets,
        unbalanced_transactions=unbalanced,
        wallet_mismatches=mismatched,
        checked_at=datetime.now(UTC),
    )
