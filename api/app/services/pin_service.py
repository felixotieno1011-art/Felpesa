"""Transaction PIN: set/change, verify, lockout after 3 wrong attempts."""
import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models import User

MAX_ATTEMPTS = 3
LOCK_SECONDS = 15 * 60
WEAK_PINS = {str(d) * 4 for d in range(10)} | {"1234", "4321", "0123", "3210"}


class PinError(Exception):
    pass


class PinRequired(PinError):
    pass


class PinInvalid(PinError):
    pass


class WeakPin(PinError):
    pass


class PinLocked(PinError):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after


def _key(user_id: uuid.UUID) -> str:
    return f"pinfail:{user_id}"


async def verify_pin(redis_client: Redis, user: User, pin: str | None) -> None:
    """Raises PinRequired/PinInvalid/PinLocked. No PIN set: required unless REQUIRE_PIN=false."""
    if user.pin_hash is None:
        if get_settings().require_pin:
            raise PinRequired
        return
    key = _key(user.id)
    fails = int(await redis_client.get(key) or 0)
    if fails >= MAX_ATTEMPTS:
        raise PinLocked(max(1, int(await redis_client.ttl(key))))
    if not pin:
        raise PinRequired
    if not verify_password(pin, user.pin_hash):
        count = await redis_client.incr(key)
        if count == 1 or count >= MAX_ATTEMPTS:
            await redis_client.expire(key, LOCK_SECONDS)
        if count >= MAX_ATTEMPTS:
            raise PinLocked(LOCK_SECONDS)
        raise PinInvalid
    await redis_client.delete(key)


async def set_pin(
    db: AsyncSession,
    redis_client: Redis,
    *,
    user: User,
    new_pin: str,
    old_pin: str | None,
) -> None:
    if new_pin in WEAK_PINS:
        raise WeakPin
    had_pin = user.pin_hash is not None
    if had_pin:
        await verify_pin(redis_client, user, old_pin)
    user.pin_hash = hash_password(new_pin)
    await audit(
        db,
        actor_id=user.id,
        action="pin.changed" if had_pin else "pin.set",
        entity_type="user",
        entity_id=user.id,
        metadata={},
    )
    await db.commit()
