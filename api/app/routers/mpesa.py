import hmac
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
import httpx
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select

from app.core.config import get_settings
from app.core.rate_limit import RateLimitExceeded, check_rate_limit
from app.core.redis import get_redis
from app.deps import CurrentUser, SessionDep
from app.models import MpesaRequest
from app.services import daraja, mpesa_service, wallet_service

router = APIRouter(prefix="/mpesa", tags=["mpesa"])
RedisDep = Annotated[Redis, Depends(get_redis)]


class StkIn(BaseModel):
    phone: str = Field(pattern=r"^\+254[17]\d{8}$")
    amount: int = Field(ge=1, le=150000)


@router.post("/stk", status_code=202)
async def stk(payload: StkIn, user: CurrentUser, db: SessionDep, redis_client: RedisDep) -> dict:
    if not daraja.is_configured():
        raise HTTPException(503, "M-Pesa is not configured")
    try:
        await check_rate_limit(redis_client, scope="stk", identity=user.id, limit=3)
    except RateLimitExceeded as e:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded",
            headers={"Retry-After": str(e.retry_after)},
        )
    wallet = await wallet_service.get_wallet_for_user(db, user_id=user.id)
    if wallet is None:
        raise HTTPException(404, "Wallet not found")
    try:
        req = await mpesa_service.initiate_stk(
            db, user=user, wallet=wallet, phone=payload.phone, amount=payload.amount
        )
    except (daraja.DarajaError, mpesa_service.StkRejected) as e:
        raise HTTPException(502, str(e))
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach M-Pesa")
    return {"checkout_request_id": req.checkout_request_id, "status": req.status}


@router.get("/status/{checkout_request_id}")
async def stk_status(checkout_request_id: str, user: CurrentUser, db: SessionDep) -> dict:
    req = await db.scalar(
        select(MpesaRequest).where(
            MpesaRequest.checkout_request_id == checkout_request_id,
            MpesaRequest.user_id == user.id,
        )
    )
    if req is None:
        raise HTTPException(404, "Not found")
    return {
        "status": req.status,
        "result_desc": req.result_desc,
        "mpesa_receipt": req.mpesa_receipt,
        "amount": str(req.amount),
    }


@router.post("/callback/{secret}")
async def callback(secret: str, request: Request, db: SessionDep) -> dict:
    expected = get_settings().mpesa_callback_secret
    if not expected or not hmac.compare_digest(secret, expected):
        raise HTTPException(404, "Not found")
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(400, "Bad payload")
    await mpesa_service.handle_callback(db, payload)
    return {"ResultCode": 0, "ResultDesc": "Accepted"}
