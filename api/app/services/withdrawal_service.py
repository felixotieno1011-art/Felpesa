"""Provider-backed withdrawals: debit -> pending -> completed, or reversed by a new entry."""
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.models import LedgerEntry, MpesaRequest, Transaction, User
from app.payments.interfaces import PayoutRequest
from app.payments.registry import get_provider
from app.services import deposit_service, notification_service
from app.services.deposit_service import _lock_clearing_wallet, _lock_user_wallet

log = logging.getLogger(__name__)


async def _claim_attempt(db: AsyncSession, *, txn_id, user_id, wallet_id, provider_name,
                         phone, amount) -> uuid.UUID | None:
    """Write the payout attempt BEFORE calling the provider. None = someone already claimed it."""
    existing = await db.scalar(select(MpesaRequest.id).where(
        MpesaRequest.transaction_id == txn_id, MpesaRequest.kind == "payout"))
    if existing is not None:
        await db.rollback()
        return None
    attempt_id = uuid.uuid4()
    db.add(MpesaRequest(id=attempt_id, user_id=user_id, wallet_id=wallet_id,
                        provider=provider_name, kind="payout", phone=phone,
                        amount=amount, transaction_id=txn_id))
    try:
        await db.commit()
    except IntegrityError:  # unique (transaction_id, kind): a concurrent claim won
        await db.rollback()
        return None
    return attempt_id


async def _send_payout(db: AsyncSession, provider, attempt_id, phone, amount) -> None:
    try:
        res = await provider.initiate_payout(
            PayoutRequest(phone=phone, amount=amount, reference=str(attempt_id)[:12]))
    except NotImplementedError as e:
        await settle_payout(db, attempt_id, success=False, reason=str(e))
        return
    except Exception as e:
        # Timeout or network error: the customer may already have been paid. Never auto-reverse.
        a = await db.get(MpesaRequest, attempt_id)
        a.status = "needs_review"
        a.result_desc = ("Uncertain outcome: " + str(e))[:255]
        await db.commit()
        return
    if not res.accepted:
        await settle_payout(db, attempt_id, success=False, reason=res.message)
    else:
        a = await db.get(MpesaRequest, attempt_id)
        a.checkout_request_id = res.provider_ref
        await db.commit()


async def request_withdrawal(db: AsyncSession, *, user, wallet, amount, currency,
                             idempotency_key, description=None) -> Transaction:
    phone = user.phone
    txn = await deposit_service.withdraw(
        db, user_id=user.id, from_wallet_id=wallet.id, amount=amount, currency=currency,
        idempotency_key=idempotency_key, description=description, pending=True,
    )
    if txn.status != "pending":
        return txn
    txn_id = txn.id
    provider = get_provider()
    attempt_id = await _claim_attempt(
        db, txn_id=txn_id, user_id=user.id, wallet_id=wallet.id,
        provider_name=provider.name, phone=phone, amount=amount)
    if attempt_id is None:
        return await db.get(Transaction, txn_id)  # reload: rollback expired txn
    await _send_payout(db, provider, attempt_id, phone, amount)
    return await db.get(Transaction, txn_id)


async def retry_unsent_withdrawal(db: AsyncSession, txn_id: uuid.UUID) -> str:
    """Crash gap: a pending withdrawal with no attempt. Claims it, then sends exactly once."""
    txn = await db.scalar(
        select(Transaction).where(Transaction.id == txn_id)
        .with_for_update().execution_options(populate_existing=True))
    if txn is None or txn.type != "withdrawal" or txn.status != "pending":
        await db.rollback()
        return "skipped"
    user = await db.get(User, txn.initiated_by)
    user_id, wallet_id, amount, phone = txn.initiated_by, txn.from_wallet_id, txn.amount, user.phone
    provider = get_provider()
    attempt_id = await _claim_attempt(
        db, txn_id=txn_id, user_id=user_id, wallet_id=wallet_id,
        provider_name=provider.name, phone=phone, amount=amount)
    if attempt_id is None:
        return "skipped"
    await _send_payout(db, provider, attempt_id, phone, amount)
    return "sent"


async def settle_payout(db: AsyncSession, attempt_id: uuid.UUID, *, success: bool,
                        reason: str | None = None) -> None:
    """Apply the provider's final result. Safe to call twice: only a pending payout is acted on."""
    att = await db.scalar(
        select(MpesaRequest)
        .where(MpesaRequest.id == attempt_id, MpesaRequest.kind == "payout")
        .with_for_update().execution_options(populate_existing=True))
    if att is None or att.status not in ("pending", "needs_review"):
        await db.rollback()
        return
    txn = await db.scalar(
        select(Transaction).where(Transaction.id == att.transaction_id)
        .with_for_update().execution_options(populate_existing=True))
    if txn is None or txn.status != "pending":
        await db.rollback()
        return

    if success:
        att.status = "completed"
        txn.status = "completed"
        txn.completed_at = func.now()
        await audit(db, actor_id=txn.initiated_by, action="withdrawal.confirmed",
                    entity_type="transaction", entity_id=txn.id, metadata={})
        notification_service.after_payout_confirmed(db, txn=txn)
        await db.commit()
        return

    att.status = "failed"
    att.result_desc = (reason or "Payout failed")[:255]
    await _reverse(db, txn)
    await db.commit()


async def _reverse(db: AsyncSession, txn: Transaction) -> None:
    """Compensating entries. The unique idempotency key makes a second refund impossible."""
    clearing = await _lock_clearing_wallet(db)
    user_w = await _lock_user_wallet(db, txn.from_wallet_id)
    amount = txn.amount
    rev = Transaction(
        idempotency_key=f"rev-{txn.id}", type="withdrawal_reversal", status="completed",
        amount=amount, currency=txn.currency, from_wallet_id=clearing.id,
        to_wallet_id=user_w.id, initiated_by=txn.initiated_by,
        description=f"Reversal of {txn.id}", flagged_fraud=False, completed_at=func.now(),
    )
    db.add(rev)
    await db.flush()
    clearing_after = clearing.balance - amount
    user_after = user_w.balance + amount
    db.add(LedgerEntry(transaction_id=rev.id, wallet_id=clearing.id, direction="debit",
                       amount=amount, balance_after=clearing_after))
    db.add(LedgerEntry(transaction_id=rev.id, wallet_id=user_w.id, direction="credit",
                       amount=amount, balance_after=user_after))
    clearing.balance = clearing_after
    user_w.balance = user_after
    txn.status = "reversed"
    await db.flush()
    await audit(db, actor_id=txn.initiated_by, action="withdrawal.reversed",
                entity_type="transaction", entity_id=txn.id,
                metadata={"reversal_id": str(rev.id), "amount": str(amount)})
    notification_service.add(
        db, user_w.user_id, "withdrawal", "Withdrawal reversed",
        f"Ksh{amount:,.2f} returned to your wallet: the withdrawal failed.", rev.id)
