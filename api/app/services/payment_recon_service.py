"""Re-check stuck payment attempts against the provider. Never guesses: acts only on explicit answers."""
import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MpesaRequest, Transaction
from app.payments.registry import get_provider
from app.services import deposit_service, withdrawal_service

log = logging.getLogger(__name__)
OPEN = ("pending", "needs_review")


async def reconcile_collection(db: AsyncSession, attempt_id: uuid.UUID) -> str:
    att = await db.get(MpesaRequest, attempt_id)
    if att is None or att.kind != "collection" or not att.checkout_request_id:
        return "skipped"
    if att.status not in OPEN:
        return "skipped"
    # needs_review for other reasons (amount mismatch, deposit error) is for a human.
    if att.status == "needs_review" and not (att.result_desc or "").startswith(
        "Callback not confirmed"
    ):
        return "manual"
    ref, provider = att.checkout_request_id, att.provider
    try:
        answer = await get_provider(provider).query_status(ref)
    except Exception:
        log.exception("reconcile query failed ref=%s", ref)
        await db.rollback()
        return "error"
    if answer == "pending":
        await db.rollback()
        return "pending"

    att = await db.scalar(
        select(MpesaRequest).where(MpesaRequest.id == attempt_id)
        .with_for_update().execution_options(populate_existing=True))
    if att is None or att.status not in OPEN:
        await db.rollback()
        return "skipped"
    if answer == "failed":
        att.status = "failed"
        att.result_desc = "Confirmed failed by provider query"
        await db.commit()
        return "failed"

    user_id, wallet_id, amount = att.user_id, att.wallet_id, att.amount
    desc = f"M-Pesa {att.mpesa_receipt or ref}"  # same text as the callback path
    try:
        txn = await deposit_service.deposit(
            db, user_id=user_id, to_wallet_id=wallet_id, amount=amount, currency="KES",
            idempotency_key=ref, daily_limit=Decimal("0"), description=desc)
    except deposit_service.DepositError as e:
        att = await db.get(MpesaRequest, attempt_id)
        att.status = "needs_review"
        att.result_desc = str(e)[:255]
        await db.commit()
        return "manual"
    att = await db.get(MpesaRequest, attempt_id)
    att.status = "completed"
    att.transaction_id = txn.id
    await db.commit()
    return "credited"


async def reconcile_payout(db: AsyncSession, attempt_id: uuid.UUID) -> str:
    att = await db.get(MpesaRequest, attempt_id)
    if att is None or att.kind != "payout" or att.status not in OPEN:
        return "skipped"
    reference, provider = str(att.id)[:12], att.provider
    try:
        answer = await get_provider(provider).query_payout(reference)
    except NotImplementedError:
        await db.rollback()
        return "manual"
    except Exception:
        log.exception("payout query failed ref=%s", reference)
        await db.rollback()
        return "error"
    if answer == "paid":
        await withdrawal_service.settle_payout(db, attempt_id, success=True)
        return "confirmed"
    if answer == "failed":
        await withdrawal_service.settle_payout(
            db, attempt_id, success=False, reason="Provider reports payout failed")
        return "reversed"
    await db.rollback()
    return "pending"


async def find_unattempted_withdrawals(db: AsyncSession, min_age_seconds: int = 300) -> list[str]:
    """Crash gap: pending withdrawal with no payout attempt. Reported only."""
    cutoff = datetime.now(UTC) - timedelta(seconds=min_age_seconds)
    rows = await db.scalars(
        select(Transaction.id).where(
            Transaction.type == "withdrawal", Transaction.status == "pending",
            Transaction.created_at <= cutoff,
            ~exists().where(MpesaRequest.transaction_id == Transaction.id,
                            MpesaRequest.kind == "payout")))
    return [str(i) for i in rows.all()]


async def run_reconciliation(db: AsyncSession, min_age_seconds: int = 300) -> dict:
    cutoff = datetime.now(UTC) - timedelta(seconds=min_age_seconds)
    rows = (await db.execute(
        select(MpesaRequest.id, MpesaRequest.kind).where(
            MpesaRequest.status.in_(OPEN), MpesaRequest.created_at <= cutoff))).all()
    await db.rollback()
    counts: dict[str, int] = {}
    for att_id, kind in rows:
        fn = reconcile_collection if kind == "collection" else reconcile_payout
        outcome = await fn(db, att_id)
        counts[f"{kind}:{outcome}"] = counts.get(f"{kind}:{outcome}", 0) + 1
    unsent = await find_unattempted_withdrawals(db, min_age_seconds)
    retried: dict[str, int] = {}
    for tid in unsent:
        outcome = await withdrawal_service.retry_unsent_withdrawal(db, uuid.UUID(tid))
        retried[outcome] = retried.get(outcome, 0) + 1
    return {"checked": len(rows), "outcomes": counts,
            "withdrawals_without_payout": unsent, "withdrawals_retried": retried}
