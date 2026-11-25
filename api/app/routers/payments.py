from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.rate_limit import RateLimitExceeded, check_rate_limit
from app.core.redis import get_redis
from app.deps import CurrentUser, SessionDep
from app.pin_dep import require_pin
from app.schemas.transaction import TransactionOut
from app.services import message_service, payment_service, transfer_service, wallet_service

router = APIRouter(prefix="/payments", tags=["payments"])
settings = get_settings()
RedisDep = Annotated[Redis, Depends(get_redis)]
IdemKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=64)]


class PayRequest(BaseModel):
    number: str = Field(pattern=r"^\d{5,10}$")
    account_ref: str | None = Field(default=None, max_length=30)
    amount: Decimal = Field(gt=0, max_digits=19, decimal_places=4)
    currency: str = Field(min_length=3, max_length=3)


async def _pay(kind, payload, user, db, redis_client, idem):
    try:
        await check_rate_limit(
            redis_client,
            scope="transfer",
            identity=user.id,
            limit=settings.rate_limit_transfers_per_min,
        )
    except RateLimitExceeded as e:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Rate limit exceeded",
            headers={"Retry-After": str(e.retry_after)},
        )

    wallet = await wallet_service.get_wallet_for_user(db, user_id=user.id)
    if wallet is None:
        raise HTTPException(404, "Sender wallet not found")

    try:
        txn = await payment_service.pay_merchant(
            db,
            user_id=user.id,
            from_wallet_id=wallet.id,
            kind=kind,
            number=payload.number,
            account_ref=payload.account_ref,
            amount=payload.amount,
            currency=payload.currency,
            idempotency_key=idem,
        )
    except payment_service.MerchantNotFound:
        raise HTTPException(404, "Merchant not found")
    except transfer_service.InsufficientFunds:
        raise HTTPException(422, "Insufficient funds")
    except (
        transfer_service.WalletNotActive,
        transfer_service.CurrencyMismatch,
        transfer_service.SameWallet,
    ) as e:
        raise HTTPException(422, str(e))
    except transfer_service.WalletNotFound:
        raise HTTPException(404, "Wallet not found")
    out = TransactionOut.model_validate(txn)
    msgs = await message_service.build_messages(db, [txn], wallet.id)
    out.message = msgs.get(txn.id)
    return out


@router.post("/paybill", response_model=TransactionOut, status_code=201,
             dependencies=[Depends(require_pin)])
async def pay_bill(
    payload: PayRequest,
    user: CurrentUser,
    db: SessionDep,
    redis_client: RedisDep,
    idempotency_key: IdemKey,
):
    if not payload.account_ref:
        raise HTTPException(422, "account_ref is required for paybill")
    return await _pay("paybill", payload, user, db, redis_client, idempotency_key)


@router.post("/till", response_model=TransactionOut, status_code=201,
             dependencies=[Depends(require_pin)])
async def buy_goods(
    payload: PayRequest,
    user: CurrentUser,
    db: SessionDep,
    redis_client: RedisDep,
    idempotency_key: IdemKey,
):
    return await _pay("buygoods", payload, user, db, redis_client, idempotency_key)
