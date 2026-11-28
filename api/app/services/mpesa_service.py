import asyncio
import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import MpesaRequest, User, Wallet
from app.payments.interfaces import CollectionRequest
from app.payments.registry import get_provider
from app.services import daraja, deposit_service

log = logging.getLogger(__name__)


class StkRejected(Exception):
    pass



async def _auto_complete_mock(checkout_request_id: str, phone: str, amount: Decimal) -> None:
    await asyncio.sleep(2)
    from app.core.db import SessionLocal
    async with SessionLocal() as db:
        await handle_callback(db, {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": checkout_request_id,
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": float(amount)},
                            {"Name": "MpesaReceiptNumber", "Value": "SBX" + checkout_request_id[-7:].upper()},
                            {"Name": "PhoneNumber", "Value": int(phone.lstrip("+"))},
                        ]
                    },
                }
            }
        })


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
        resp = await get_provider().initiate_collection(CollectionRequest(
            phone=phone, amount=Decimal(amount), reference="FELPESA",
            description="Felpesa topup", callback_url=callback_url,
        ))
        if not resp.accepted:
            raise StkRejected(resp.message or "Request rejected")
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
    req.checkout_request_id = resp.provider_ref
    req.merchant_request_id = resp.secondary_ref
    await db.commit()
    await db.refresh(req)
    if s.payment_provider == "mock" and req.checkout_request_id:
        asyncio.create_task(_auto_complete_mock(req.checkout_request_id, phone, req.amount))
    return req


async def _verified_paid(checkout_request_id: str) -> bool:
    """Confirm with Safaricom directly that this request was paid."""
    try:
        status = await get_provider().query_status(checkout_request_id)
    except Exception:
        log.exception("stk query failed checkout=%s", checkout_request_id)
        return False
    return status == "paid"


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
