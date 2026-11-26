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
from app.services import airtime_service, message_service, transfer_service, wallet_service

router = APIRouter(prefix="/airtime", tags=["airtime"])
settings = get_settings()
RedisDep = Annotated[Redis, Depends(get_redis)]
IdemKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=64)]


class AirtimeRequest(BaseModel):
    phone: str = Field(pattern=r"^\+[1-9]\d{9,14}$")
    amount: Decimal = Field(ge=5, le=5000, max_digits=19, decimal_places=4)
    currency: str = Field(min_length=3, max_length=3)


@router.post(
    "", response_model=TransactionOut, status_code=201,
    dependencies=[Depends(require_pin)],
)
async def buy_airtime(
    payload: AirtimeRequest,
    user: CurrentUser,
    db: SessionDep,
    redis_client: RedisDep,
    idempotency_key: IdemKey,
) -> TransactionOut:
    try:
        await check_rate_limit(
            redis_client, scope="transfer", identity=user.id,
            limit=settings.rate_limit_transfers_per_min,
        )
    except RateLimitExceeded as e:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded",
            headers={"Retry-After": str(e.retry_after)},
        )

    wallet = await wallet_service.get_wallet_for_user(db, user_id=user.id)
    if wallet is None:
        raise HTTPException(404, "Sender wallet not found")

    try:
        txn = await airtime_service.buy_airtime(
            db, user_id=user.id, from_wallet_id=wallet.id, phone=payload.phone,
            amount=payload.amount, currency=payload.currency,
            idempotency_key=idempotency_key,
        )
    except airtime_service.ProviderNotFound:
        raise HTTPException(503, "Airtime is not available right now")
    except transfer_service.InsufficientFunds:
        raise HTTPException(422, "Insufficient funds")
    except (
        transfer_service.WalletNotActive,
        transfer_service.CurrencyMismatch,
        transfer_service.SameWallet,
    ) as e:
        raise HTTPException(422, str(e))
    except (transfer_service.SystemWalletNotAllowed, transfer_service.NotWalletOwner):
        raise HTTPException(403, "Not allowed")
    except transfer_service.WalletNotFound:
        raise HTTPException(404, "Wallet not found")

    out = TransactionOut.model_validate(txn)
    msgs = await message_service.build_messages(db, [txn], wallet.id)
    out.message = msgs.get(txn.id)
    return out
