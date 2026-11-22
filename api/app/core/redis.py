"""Async Redis client. Single connection pool, wired via a dependency."""
from collections.abc import AsyncGenerator

import redis.asyncio as redis
from redis.asyncio import Redis

from app.core.config import get_settings

settings = get_settings()

# Global client — created once, reused across the process. `decode_responses=True`
# means .get() returns str, not bytes. Easier for logging.
_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_client


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency. Yields the shared client (no per-request open/close)."""
    yield get_redis_client()


async def close_redis() -> None:
    """Called from app lifespan shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
