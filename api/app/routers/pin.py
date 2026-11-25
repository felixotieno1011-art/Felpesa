from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.core.redis import get_redis
from app.deps import CurrentUser, SessionDep
from app.services import pin_service

router = APIRouter(prefix="/pin", tags=["pin"])
RedisDep = Annotated[Redis, Depends(get_redis)]


class SetPinRequest(BaseModel):
    pin: str = Field(pattern=r"^\d{4}$")
    old_pin: str | None = Field(default=None, pattern=r"^\d{4}$")


@router.get("/status")
async def pin_status(user: CurrentUser) -> dict:
    return {"has_pin": user.pin_hash is not None}


@router.post("")
async def set_pin(
    payload: SetPinRequest, user: CurrentUser, db: SessionDep, redis_client: RedisDep
) -> dict:
    try:
        await pin_service.set_pin(
            db, redis_client, user=user, new_pin=payload.pin, old_pin=payload.old_pin
        )
    except pin_service.WeakPin:
        raise HTTPException(422, "PIN too easy to guess (avoid 1111, 1234, ...)")
    except pin_service.PinRequired:
        raise HTTPException(403, "Current PIN required")
    except pin_service.PinInvalid:
        raise HTTPException(403, "Current PIN is wrong")
    except pin_service.PinLocked as e:
        raise HTTPException(
            429, "Too many wrong PINs. Try again later.",
            headers={"Retry-After": str(e.retry_after)},
        )
    return {"ok": True}
