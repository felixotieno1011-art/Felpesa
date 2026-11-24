"""Auth business logic: register, login. Routers call these, never ORM directly."""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.security import hash_password, verify_password
from app.models import User, Wallet


class UserAlreadyExists(Exception):
    pass


class InvalidCredentials(Exception):
    pass


async def register_user(
    db: AsyncSession,
    *,
    phone: str,
    full_name: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, Wallet]:
    existing = await db.scalar(select(User).where(User.phone == phone))
    if existing is not None:
        raise UserAlreadyExists(phone)

    try:
        user = User(phone=phone, full_name=full_name, password_hash=hash_password(password))
        db.add(user)
        await db.flush()

        wallet = Wallet(
            user_id=user.id,
            currency="KES",
            balance=Decimal("0"),
            status="active",
        )
        db.add(wallet)
        await db.flush()

        await audit(
            db,
            actor_id=user.id,
            action="auth.register",
            entity_type="user",
            entity_id=user.id,
            metadata={"phone": phone, "wallet_id": str(wallet.id)},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await db.commit()
    except IntegrityError:
        # Race: another request registered the same phone between our
        # pre-check and our INSERT. The unique constraint fires here — re-raise
        # as UserAlreadyExists so the router returns 409 (same as pre-check path).
        await db.rollback()
        raise UserAlreadyExists(phone)

    await db.refresh(user)
    await db.refresh(wallet)
    return user, wallet


async def authenticate_user(
    db: AsyncSession,
    *,
    phone: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> User:
    user = await db.scalar(select(User).where(User.phone == phone))
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials
    if not user.is_active:
        raise InvalidCredentials

    await audit(
        db,
        actor_id=user.id,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        metadata={"phone": phone},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await db.commit()
    return user
