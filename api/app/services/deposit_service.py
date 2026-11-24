"""Deposits and withdrawals: money moving between user wallets and the clearing wallet.

Design: the clearing wallet represents the system's liability to users.
A deposit increases the user's balance and decreases the clearing balance
(more negative = more owed). Both legs are recorded as ledger entries so
every transaction has 2 sides and balances to zero.

In v1, this is a sandbox — any authenticated user can deposit up to the
daily limit. In production, the deposit path becomes a Daraja/M-Pesa
webhook with its own authentication. See NEXT_STEPS.md.
"""
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.models import LedgerEntry, Transaction, Wallet
from app.services.wallet_service import get_clearing_wallet


class DepositError(Exception):
    pass


class WithdrawalError(Exception):
    pass


class InsufficientFunds(WithdrawalError):
    pass


class DailyLimitExceeded(DepositError):
    pass


async def _lock_user_wallet(db: AsyncSession, wallet_id: uuid.UUID) -> Wallet:
    from sqlalchemy import select as _select
    w = await db.scalar(
        _select(Wallet)
        .where(Wallet.id == wallet_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if w is None:
        raise DepositError(f"Wallet {wallet_id} not found")
    return w


async def _lock_clearing_wallet(db: AsyncSession) -> Wallet:
    w = await db.scalar(
        select(Wallet)
        .where(Wallet.is_system.is_(True), Wallet.currency == "KES")
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if w is None:
        raise RuntimeError("Clearing wallet missing — run alembic upgrade head")
    return w


async def _todays_deposit_total(db: AsyncSession, user_id: uuid.UUID) -> Decimal:
    """Sum of today's completed deposits for this user."""
    row = await db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.initiated_by == user_id,
            Transaction.type == "deposit",
            Transaction.status == "completed",
            func.date(Transaction.created_at) == func.date(func.now()),
        )
    )
    return Decimal(str(row or 0))


async def deposit(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    to_wallet_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    idempotency_key: str,
    daily_limit: Decimal = Decimal("100000.0000"),
    description: str | None = None,
) -> Transaction:
    """Deposit money into a user wallet, debiting the clearing wallet.

    Both legs recorded; both must be balanced. Idempotent by
    (initiated_by, idempotency_key).
    """
    if amount <= 0:
        raise DepositError("Amount must be positive")

    # Idempotency fast-path
    existing = await db.scalar(
        select(Transaction).where(
            Transaction.initiated_by == user_id,
            Transaction.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing

    try:
        # Lock in deterministic order (clearing has stable UUID so this is safe)
        clearing = await _lock_clearing_wallet(db)
        user_w = await _lock_user_wallet(db, to_wallet_id)

        # Re-check idempotency after locks (same pattern as transfers)
        existing_after = await db.scalar(
            select(Transaction).where(
                Transaction.initiated_by == user_id,
                Transaction.idempotency_key == idempotency_key,
            )
        )
        if existing_after is not None:
            await db.commit()
            return existing_after

        if user_w.is_system:
            raise DepositError("Cannot deposit to a system wallet")
        if user_w.currency != currency:
            raise DepositError(
                f"Currency mismatch: wallet {user_w.currency} != {currency}"
            )

        # Daily limit check
        if daily_limit > 0:
            today = await _todays_deposit_total(db, user_id)
            if today + amount > daily_limit:
                raise DailyLimitExceeded(
                    f"Daily deposit limit {daily_limit} KES exceeded "
                    f"(already deposited {today} today)"
                )

        # Build the transaction
        txn = Transaction(
            idempotency_key=idempotency_key,
            type="deposit",
            status="pending",
            amount=amount,
            currency=currency,
            from_wallet_id=None,  # external source
            to_wallet_id=user_w.id,
            initiated_by=user_id,
            description=description,
            flagged_fraud=False,
        )
        db.add(txn)
        await db.flush()

        # Double-entry: clearing debit, user credit
        clearing_after = clearing.balance - amount
        user_after = user_w.balance + amount

        db.add(LedgerEntry(
            transaction_id=txn.id,
            wallet_id=clearing.id,
            direction="debit",
            amount=amount,
            balance_after=clearing_after,
        ))
        db.add(LedgerEntry(
            transaction_id=txn.id,
            wallet_id=user_w.id,
            direction="credit",
            amount=amount,
            balance_after=user_after,
        ))

        clearing.balance = clearing_after
        user_w.balance = user_after

        from sqlalchemy import func as _func
        txn.status = "completed"
        txn.completed_at = _func.now()

        await db.flush()

        await audit(
            db,
            actor_id=user_id,
            action="deposit.completed",
            entity_type="transaction",
            entity_id=txn.id,
            metadata={
                "amount": str(amount),
                "currency": currency,
                "to_wallet_id": str(user_w.id),
                "clearing_wallet_id": str(clearing.id),
            },
        )

        await db.commit()

    except IntegrityError:
        await db.rollback()
        winner = await db.scalar(
            select(Transaction).where(
                Transaction.initiated_by == user_id,
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


async def withdraw(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    from_wallet_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    idempotency_key: str,
    description: str | None = None,
) -> Transaction:
    """Withdraw from a user wallet, crediting the clearing wallet.

    Mirror of deposit. Rejects if user has insufficient funds.
    """
    if amount <= 0:
        raise DepositError("Amount must be positive")

    existing = await db.scalar(
        select(Transaction).where(
            Transaction.initiated_by == user_id,
            Transaction.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing

    try:
        clearing = await _lock_clearing_wallet(db)
        user_w = await _lock_user_wallet(db, from_wallet_id)

        existing_after = await db.scalar(
            select(Transaction).where(
                Transaction.initiated_by == user_id,
                Transaction.idempotency_key == idempotency_key,
            )
        )
        if existing_after is not None:
            await db.commit()
            return existing_after

        if user_w.is_system:
            raise DepositError("Cannot withdraw from a system wallet")
        if user_w.currency != currency:
            raise DepositError(
                f"Currency mismatch: wallet {user_w.currency} != {currency}"
            )
        if user_w.balance < amount:
            raise InsufficientFunds(f"Balance {user_w.balance} < amount {amount}")

        txn = Transaction(
            idempotency_key=idempotency_key,
            type="withdrawal",
            status="pending",
            amount=amount,
            currency=currency,
            from_wallet_id=user_w.id,
            to_wallet_id=None,
            initiated_by=user_id,
            description=description,
            flagged_fraud=False,
        )
        db.add(txn)
        await db.flush()

        user_after = user_w.balance - amount
        clearing_after = clearing.balance + amount

        db.add(LedgerEntry(
            transaction_id=txn.id,
            wallet_id=user_w.id,
            direction="debit",
            amount=amount,
            balance_after=user_after,
        ))
        db.add(LedgerEntry(
            transaction_id=txn.id,
            wallet_id=clearing.id,
            direction="credit",
            amount=amount,
            balance_after=clearing_after,
        ))

        user_w.balance = user_after
        clearing.balance = clearing_after

        from sqlalchemy import func as _func
        txn.status = "completed"
        txn.completed_at = _func.now()

        await db.flush()

        await audit(
            db,
            actor_id=user_id,
            action="withdrawal.completed",
            entity_type="transaction",
            entity_id=txn.id,
            metadata={
                "amount": str(amount),
                "currency": currency,
                "from_wallet_id": str(user_w.id),
                "clearing_wallet_id": str(clearing.id),
            },
        )

        await db.commit()

    except IntegrityError:
        await db.rollback()
        winner = await db.scalar(
            select(Transaction).where(
                Transaction.initiated_by == user_id,
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
