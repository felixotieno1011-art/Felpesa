"""Auth business logic: register, login. Routers call these, never ORM directly."""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models import User, Wallet


class UserAlreadyExists(Exception):
    pass


class InvalidCredentials(Exception):
    pass


async def register_user(
    db: AsyncSession, *, phone: str, full_name: str, password: str
) -> tuple[User, Wallet]:
    """Create user + wallet atomically. Either both rows exist, or neither."""
    # Pre-check for a clean 409; the unique constraint is the real guard (see below).
    existing = await db.scalar(select(User).where(User.phone == phone))
    if existing is not None:
        raise UserAlreadyExists(phone)

    user = User(
        phone=phone,
        full_name=full_name,
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.flush()  # populate user.id without committing

    wallet = Wallet(
        user_id=user.id,
        currency="KES",
        balance=Decimal("0"),
        status="active",
    )
    db.add(wallet)
    await db.flush()

    # Single commit → atomic. If this throws (e.g. duplicate phone race),
    # both inserts roll back and the caller sees IntegrityError, not a
    # half-registered user. This is the whole point of doing it here.
    await db.commit()
    await db.refresh(user)
    await db.refresh(wallet)
    return user, wallet


async def authenticate_user(db: AsyncSession, *, phone: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.phone == phone))
    if user is None or not verify_password(password, user.password_hash):
        # Same exception for both cases — do not leak which one failed.
        raise InvalidCredentials
    if not user.is_active:
        raise InvalidCredentials
    return user
