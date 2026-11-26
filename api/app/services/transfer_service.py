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


class SystemWalletNotAllowed(TransferError):
    pass


class NotWalletOwner(TransferError):
    pass


async def _lock_wallet(db: AsyncSession, wallet_id: uuid.UUID) -> Wallet:
    """Row-level lock. Held until the surrounding transaction commits/rolls back.

    FOR UPDATE prevents concurrent transfers from both reading the same
    balance and both thinking there's enough money. This is the mechanism
    that makes the concurrency test pass.
    """
    wallet = await db.scalar(
        select(Wallet)
        .where(Wallet.id == wallet_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if wallet is None:
        raise WalletNotFound(str(wallet_id))
    return wallet


async def _execute_transfer(
    db: AsyncSession,
    *,
    initiated_by: uuid.UUID,
    from_wallet_id: uuid.UUID,
    to_wallet_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    idempotency_key: str,
    description: str | None = None,
    txn_type: str = "transfer",
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
        # Lock wallets in sorted-by-UUID order to prevent deadlock.
        #
        # Why this matters: if Alice→Bob and Bob→Alice run concurrently and
        # each locks the sender first, you get:
        #   Tx1: lock(Alice) → wait for Bob
        #   Tx2: lock(Bob)   → wait for Alice
        # Postgres detects the deadlock and kills one — the user sees a random
        # 500. Sorting the lock order makes both transactions acquire locks
        # in the same sequence, so one waits for the other instead of
        # deadlocking. This is the canonical fix for row-level lock ordering.
        first_id, second_id = sorted([from_wallet_id, to_wallet_id], key=str)
        first_w = await _lock_wallet(db, first_id)
        second_w = await _lock_wallet(db, second_id)

        if from_wallet_id == first_id:
            from_w, to_w = first_w, second_w
        else:
            from_w, to_w = second_w, first_w

        # Re-check idempotency AFTER acquiring the locks. The fast-path check
        # above runs before the locks and can miss a concurrent duplicate that
        # is currently in progress. Once we hold the locks, any competing
        # transaction with the same key has either committed (→ we return it)
        # or will commit later (→ it sees our transaction). This second check
        # is what makes the transfer idempotent under real concurrency.
        # Without it, a retry can hit "Insufficient funds" on a transfer that
        # already succeeded, or double-send money.
        winner = await db.scalar(
            select(Transaction).where(
                Transaction.initiated_by == initiated_by,
                Transaction.idempotency_key == idempotency_key,
            )
        )
        if winner is not None:
            # Another request won the race while we waited for locks.
            # Capture winner.id BEFORE any session operation — accessing
            # attributes on an expired instance triggers lazy-load, which
            # fails with MissingGreenlet in async context.
            winner_id = winner.id
            # Commit (not rollback) to release locks cleanly. With
            # expire_on_commit=False (our session config), commit leaves
            # `winner` fully populated and safe to serialize.
            await db.commit()
            return winner

        if from_w.id == to_w.id:
            raise SameWallet("Cannot transfer to self")
        if from_w.is_system or to_w.is_system:
            raise SystemWalletNotAllowed("System wallets cannot be used in transfers")
        if from_w.user_id != initiated_by:
            raise NotWalletOwner("Sender wallet does not belong to the initiating user")
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
            type=txn_type,
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


async def execute_transfer(db: AsyncSession, **kw) -> Transaction:
    """Runs the transfer, then rejects key reuse with different params."""
    from app.services.idempotency import ensure_same

    txn = await _execute_transfer(db, **kw)
    ensure_same(
        txn,
        type=kw.get("txn_type", "transfer"),
        amount=kw["amount"],
        currency=kw["currency"],
        from_wallet_id=kw["from_wallet_id"],
        to_wallet_id=kw["to_wallet_id"],
        description=kw.get("description"),
    )
    return txn
