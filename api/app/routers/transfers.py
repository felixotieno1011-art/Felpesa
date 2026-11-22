from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.rate_limit import RateLimitExceeded, check_rate_limit
from app.core.redis import get_redis
from app.deps import CurrentUser, SessionDep
from app.schemas.transaction import TransactionOut, TransferRequest
from app.services import transfer_service, wallet_service

router = APIRouter(prefix="/transfers", tags=["transfers"])
settings = get_settings()

RedisDep = Annotated[Redis, Depends(get_redis)]


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def create_transfer(
    payload: TransferRequest,
    user: CurrentUser,
    db: SessionDep,
    redis_client: RedisDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=64)],
) -> TransactionOut:
    # ---- Rate limit BEFORE any business logic ----
    try:
        await check_rate_limit(
            redis_client,
            scope="transfer",
            identity=user.id,
            limit=settings.rate_limit_transfers_per_min,
        )
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(e.retry_after)},
        )

    # ---- Business logic ----
    from_wallet = await wallet_service.get_wallet_for_user(db, user_id=user.id)
    if from_wallet is None:
        raise HTTPException(status_code=404, detail="Sender wallet not found")

    try:
        txn = await transfer_service.execute_transfer(
            db,
            initiated_by=user.id,
            from_wallet_id=from_wallet.id,
            to_wallet_id=payload.to_wallet_id,
            amount=payload.amount,
            currency=payload.currency,
            idempotency_key=idempotency_key,
            description=payload.description,
        )
    except transfer_service.SameWallet:
        raise HTTPException(status_code=422, detail="Cannot transfer to self")
    except transfer_service.WalletNotFound:
        raise HTTPException(status_code=404, detail="Wallet not found")
    except transfer_service.WalletNotActive as e:
        raise HTTPException(status_code=422, detail=str(e))
    except transfer_service.CurrencyMismatch as e:
        raise HTTPException(status_code=422, detail=str(e))
    except transfer_service.InsufficientFunds:
        raise HTTPException(status_code=422, detail="Insufficient funds")

    return TransactionOut.model_validate(txn)
