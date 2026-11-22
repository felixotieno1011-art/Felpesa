"""Fixed-window rate limiter on Redis.

Key: ratelimit:{scope}:{identity}:{window_start_epoch_sec}
Window: 60 seconds (configurable)
Limit: settings.rate_limit_transfers_per_min (default 5)

Flow:
  INCR key  → 1, 2, 3, ...
  if value == 1, EXPIRE key 60  (only on first hit in a window)
  if value > limit, 429 with Retry-After = remaining seconds in window

Fixed-window tradeoff: two windows can produce 2x limit in a short burst
around the boundary (e.g. 5 in last second of minute 0, 5 in first second
of minute 1 = 10 in 2 seconds). Acceptable for v1; sliding-window
alternative documented in NEXT_STEPS.md.
"""
import time
import uuid

from fastapi import HTTPException, status
from redis.asyncio import Redis


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after


async def check_rate_limit(
    redis_client: Redis,
    *,
    scope: str,
    identity: uuid.UUID | str,
    limit: int,
    window_seconds: int = 60,
) -> None:
    """Raise RateLimitExceeded if `identity` exceeded `limit` in current window.

    Uses INCR + EXPIRE pattern. The key includes the window start epoch
    so each 60-second window has its own counter that naturally expires.
    """
    now = int(time.time())
    window_start = (now // window_seconds) * window_seconds
    key = f"ratelimit:{scope}:{identity}:{window_start}"

    count = await redis_client.incr(key)
    if count == 1:
        # First hit in this window — set TTL. `expire` on a fresh key.
        await redis_client.expire(key, window_seconds + 1)

    if count > limit:
        # Time until the next window begins.
        retry_after = window_start + window_seconds - now
        raise RateLimitExceeded(retry_after=max(1, retry_after))
