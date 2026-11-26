"""Live hints over Redis pub/sub. The DB stays the source of truth."""
import logging

from app.core.redis import get_redis_client

log = logging.getLogger(__name__)


def channel(user_id) -> str:
    return f"live:{user_id}"


async def publish(user_id) -> None:
    try:
        await get_redis_client().publish(channel(user_id), "refresh")
    except Exception:  # a failed hint must never affect a payment
        log.warning("live publish failed user=%s", user_id)
