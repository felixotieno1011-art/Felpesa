"""FastAPI dependency: checks the X-Pin header for users who have a PIN."""
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from redis.asyncio import Redis

from app.core.redis import get_redis
from app.deps import CurrentUser
from app.services import pin_service

RedisDep = Annotated[Redis, Depends(get_redis)]


async def require_pin(
    user: CurrentUser,
    redis_client: RedisDep,
    x_pin: Annotated[str | None, Header(alias="X-Pin")] = None,
) -> None:
    try:
        await pin_service.verify_pin(redis_client, user, x_pin)
    except pin_service.PinRequired:
        raise HTTPException(403, "PIN required")
    except pin_service.PinInvalid:
        raise HTTPException(403, "Invalid PIN")
    except pin_service.PinLocked as e:
        raise HTTPException(
            429,
            "Too many wrong PINs. Try again later.",
            headers={"Retry-After": str(e.retry_after)},
        )
