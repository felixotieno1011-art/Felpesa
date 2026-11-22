"""Transfer service: the double-entry money movement.

This is the most important file in Felpesa. Every other file either sets up
its preconditions (models, auth, wallets) or proves it works (reconciliation,
tests). Get this one right and the ledger is correct forever.
"""
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.models import LedgerEntry, Transaction, Wallet
from app.services import fraud_service


class TransferError(Exception):
    """Base class for all transfer business errors. Router maps these to 4xx."""


class InsufficientFunds(TransferError):
    pass


class SameWallet(TransferError):
    pass


class CurrencyMismatch(TransferError):
    pass


class WalletNotActive(TransferError):
    pass


class WalletNotFound(TransferError):
    pass


async def _lock_wallet(db: AsyncSession, wallet_id: uuid.UUID) -> Wallet:
    """Row-level lock. Held until the surrounding transaction commits/rolls back.

    FOR UPDATE prevents concurrent transfers from both reading the same
    balance and both thinking there's enough money. This is the mechanism
    that makes the concurrency test pass.
    """
    wallet = await db.scalar(
        select(Wallet).where(Wallet.id == wallet_id).with_for_update()
    )
    if wallet is None:
        raise WalletNotFound(str(wallet_id))
    return wallet


async def execute_transfer(
    db: AsyncSession,
    *,
    initiated_by: uuid.UUID,
    from_wallet_id: uuid.UUID,
    to_wallet_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    idempotency_key: str,
    description: str | None = None,
) -> Transaction:
    """Execute a transfer atomically. Returns the transaction (new or replayed).

    Guarantees:
      - Idempotent: same (initiated_by, idempotency_key) = same transaction.
      - Atomic: all writes commit, or none do.
      - Balanced: every transfer creates exactly 2 ledger entries summing to zero.
      - Concurrency-safe: FOR UPDATE locks prevent double-spend.
    """
    # ---- Step 1: idempotency fast path (outside the lock) ----
    existing = await db.scalar(
        select(Transaction).where(
            Transaction.initiated_by == initiated_by,
            Transaction.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing

    # ---- Steps 2–9: row locks, validate, write, commit ----
    # NOTE: the FastAPI get_session dependency does NOT commit. It only
    # yields a session. Every write path must call db.commit() explicitly.
    # The row locks (FOR UPDATE) are held from the first SELECT until commit,
    # which is what makes the concurrency test pass.
    try:
        from_w = await _lock_wallet(db, from_wallet_id)
        to_w = await _lock_wallet(db, to_wallet_id)

        if from_w.id == to_w.id:
            raise SameWallet("Cannot transfer to self")
        if from_w.status != "active":
            raise WalletNotActive(f"Sender wallet is {from_w.status}")
        if to_w.status != "active":
            raise WalletNotActive(f"Receiver wallet is {to_w.status}")
        if from_w.currency != to_w.currency:
            raise CurrencyMismatch(
                f"Currency mismatch: {from_w.currency} != {to_w.currency}"
            )
        if from_w.currency != currency:
            raise CurrencyMismatch(
                f"Transfer currency {currency} != wallet currency {from_w.currency}"
            )
        if from_w.balance < amount:
            raise InsufficientFunds(f"Balance {from_w.balance} < amount {amount}")

        # ---- Fraud evaluation (flag, not block) ----
        flag = await fraud_service.evaluate(db, user_id=initiated_by, amount=amount)

        txn = Transaction(
            idempotency_key=idempotency_key,
            type="transfer",
            status="pending",
            amount=amount,
            currency=currency,
            from_wallet_id=from_w.id,
            to_wallet_id=to_w.id,
            initiated_by=initiated_by,
            description=description,
            flagged_fraud=flag.flagged,
            fraud_reason=flag.reason,
        )
        db.add(txn)
        await db.flush()

        from_after = from_w.balance - amount
        to_after = to_w.balance + amount

        db.add(
            LedgerEntry(
                transaction_id=txn.id,
                wallet_id=from_w.id,
                direction="debit",
                amount=amount,
                balance_after=from_after,
            )
        )
        db.add(
            LedgerEntry(
                transaction_id=txn.id,
                wallet_id=to_w.id,
                direction="credit",
                amount=amount,
                balance_after=to_after,
            )
        )

        from_w.balance = from_after
        to_w.balance = to_after

        from sqlalchemy import func
        txn.status = "completed"
        txn.completed_at = func.now()

        await db.flush()

        # Audit record is part of the same transaction as the transfer.
        # If the transfer rolls back, this rolls back too — which is what
        # makes the audit trail trustworthy.
        await audit(
            db,
            actor_id=initiated_by,
            action="transfer.initiated",
            entity_type="transaction",
            entity_id=txn.id,
            metadata={
                "amount": str(amount),
                "currency": currency,
                "from_wallet_id": str(from_w.id),
                "to_wallet_id": str(to_w.id),
            },
        )

        await db.commit()

    except IntegrityError:
        # Concurrent request won the idempotency race. Reload and return.
        await db.rollback()
        winner = await db.scalar(
            select(Transaction).where(
                Transaction.initiated_by == initiated_by,
                Transaction.idempotency_key == idempotency_key,
            )
        )
        if winner is not None:
            return winner
        raise
    except Exception:
        await db.rollback()
        raise

    await db.refresh(txn)
    return txn
