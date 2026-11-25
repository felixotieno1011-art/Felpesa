import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select

from app.core.rate_limit import RateLimitExceeded, check_rate_limit
from app.core.redis import get_redis
from app.deps import CurrentUser, SessionDep
from app.models import User, Wallet
from app.schemas.wallet import WalletOut

router = APIRouter(prefix="/wallets", tags=["wallets"])
RedisDep = Annotated[Redis, Depends(get_redis)]


class RecipientOut(BaseModel):
    name_masked: str
    wallet_id: uuid.UUID


def mask_name(full_name: str) -> str:
    """'Felix Otieno' -> 'FELIX O***'. Never reveals the full name."""
    parts = full_name.split()
    if not parts:
        return "***"
    if len(parts) == 1:
        return f"{parts[0][:1].upper()}***"
    return f"{parts[0].upper()} {parts[-1][:1].upper()}***"


@router.get("/me", response_model=WalletOut)
async def get_my_wallet(user: CurrentUser, db: SessionDep) -> WalletOut:
    wallet = await db.scalar(select(Wallet).where(Wallet.user_id == user.id))
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return WalletOut.model_validate(wallet)


@router.get("/lookup", response_model=RecipientOut)
async def lookup_recipient(
    user: CurrentUser,
    db: SessionDep,
    redis_client: RedisDep,
    phone: Annotated[str, Query(min_length=7, max_length=15)],
) -> RecipientOut:
    # Anti-enumeration: limit how fast one user can probe phone numbers.
    try:
        await check_rate_limit(redis_client, scope="lookup", identity=user.id, limit=10)
    except RateLimitExceeded as e:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Rate limit exceeded",
            headers={"Retry-After": str(e.retry_after)},
        )

    # An unencoded "+" in a URL arrives as a space, so restore it.
    phone = phone.strip().replace(" ", "+")

    row = (
        await db.execute(
            select(User.full_name, Wallet.id)
            .join(Wallet, Wallet.user_id == User.id)
            .where(
                User.phone == phone,
                User.is_active.is_(True),
                Wallet.is_system.is_(False),
                Wallet.currency == "KES",
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Recipient not found")
    return RecipientOut(name_masked=mask_name(row[0]), wallet_id=row[1])
