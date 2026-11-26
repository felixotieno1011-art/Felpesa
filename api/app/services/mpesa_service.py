import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import MpesaRequest, User, Wallet
from app.services import daraja, deposit_service

log = logging.getLogger(__name__)


class StkRejected(Exception):
    pass


async def initiate_stk(
    db: AsyncSession, *, user: User, wallet: Wallet, phone: str, amount: int
) -> MpesaRequest:
    s = get_settings()
    callback_url = f"{s.mpesa_callback_base_url.rstrip('/')}/hooks/stk/{s.mpesa_callback_secret}"
    # 1. Save the attempt first, so a crash after Safaricom accepts can never lose it.
    req = MpesaRequest(user_id=user.id, wallet_id=wallet.id, phone=phone, amount=Decimal(amount))
    db.add(req)
    await db.commit()
    await db.refresh(req)
    req_id = req.id
    try:
        resp = await daraja.stk_push(
            phone=phone.lstrip("+"), amount=amount, reference="FELPESA",
            description="Felpesa topup", callback_url=callback_url,
        )
        if str(resp.get("ResponseCode")) != "0" or not resp.get("CheckoutRequestID"):
            raise StkRejected(resp.get("ResponseDescription") or "Request rejected")
    except (StkRejected, daraja.DarajaError) as e:
        # Safaricom answered with a clear refusal: nothing was charged.
        req = await db.get(MpesaRequest, req_id)
        req.status = "failed"
        req.result_desc = str(e)[:255]
        await db.commit()
        raise
    except Exception as e:
        # Timeout or network error: the customer may still have paid. Keep it for review.
        req = await db.get(MpesaRequest, req_id)
        req.status = "needs_review"
        req.result_desc = ("Uncertain outcome: " + str(e))[:255]
        await db.commit()
        raise
    # 2. Record Safaricom's reference.
    req = await db.get(MpesaRequest, req_id)
    req.checkout_request_id = resp["CheckoutRequestID"]
    req.merchant_request_id = resp.get("MerchantRequestID")
    await db.commit()
    await db.refresh(req)
    return req


async def _verified_paid(checkout_request_id: str) -> bool:
    """Confirm with Safaricom directly that this request was paid."""
    try:
        q = await daraja.stk_query(checkout_request_id)
    except Exception:
        log.exception("stk query failed checkout=%s", checkout_request_id)
        return False
    return str(q.get("ResultCode")) == "0"


async def handle_callback(db: AsyncSession, payload: dict) -> None:
    """Idempotent: only a 'pending' request is ever acted on."""
    cb = (payload.get("Body") or {}).get("stkCallback")
    if not cb:
        return
    req = await db.scalar(
        select(MpesaRequest)
        .where(MpesaRequest.checkout_request_id == cb.get("CheckoutRequestID"))
        .with_for_update()
    )
    if req is None or req.status != "pending":
        await db.rollback()
        return

    code = int(cb.get("ResultCode", -1))
    req.result_code = code
    req.result_desc = str(cb.get("ResultDesc", ""))[:255]

    if code != 0:
        req.status = "cancelled" if code == 1032 else "failed"
        await db.commit()
        return

    items = {i.get("Name"): i.get("Value") for i in (cb.get("CallbackMetadata") or {}).get("Item", [])}
    paid = Decimal(str(items.get("Amount", 0)))
    req.mpesa_receipt = str(items.get("MpesaReceiptNumber", ""))[:20] or None

    if paid != req.amount:
        log.error("mpesa amount mismatch checkout=%s paid=%s expected=%s",
                  req.checkout_request_id, paid, req.amount)
        req.status = "needs_review"
        req.result_desc = f"Amount mismatch: paid {paid}, expected {req.amount}"
        await db.commit()
        return

    if not await _verified_paid(req.checkout_request_id):
        req.status = "needs_review"
        req.result_desc = "Callback not confirmed by Safaricom query"
        await db.commit()
        return

    req_id, user_id, wallet_id = req.id, req.user_id, req.wallet_id
    checkout, amount, receipt = req.checkout_request_id, req.amount, req.mpesa_receipt
    try:
        # Real money already moved at Safaricom, so no daily limit here (0 = off).
        txn = await deposit_service.deposit(
            db, user_id=user_id, to_wallet_id=wallet_id, amount=amount, currency="KES",
            idempotency_key=checkout, daily_limit=Decimal("0"),
            description=f"M-Pesa {receipt or checkout}",
        )
    except deposit_service.DepositError as e:
        req = await db.get(MpesaRequest, req_id)
        req.status = "needs_review"
        req.result_desc = str(e)[:255]
        await db.commit()
        return
    req = await db.get(MpesaRequest, req_id)
    req.status = "completed"
    req.transaction_id = txn.id
    await db.commit()
