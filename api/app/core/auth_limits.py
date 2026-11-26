from fastapi import HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.rate_limit import RateLimitExceeded, check_rate_limit


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def enforce(redis_client: Redis, *, scope: str, identity: str) -> None:
    try:
        await check_rate_limit(
            redis_client, scope=scope, identity=identity,
            limit=get_settings().rate_limit_auth_per_min,
        )
    except RateLimitExceeded as e:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many attempts. Try again shortly.",
            headers={"Retry-After": str(e.retry_after)},
        )
    except RedisError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Service temporarily unavailable")
