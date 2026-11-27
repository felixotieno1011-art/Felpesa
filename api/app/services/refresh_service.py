"""Rotating refresh tokens. A reused (already rotated) token revokes the whole session."""
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.config import get_settings
from app.models import RefreshToken, User


class InvalidRefresh(Exception):
    pass


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _new_row(user_id, family_id) -> tuple[str, RefreshToken]:
    raw = secrets.token_urlsafe(48)
    days = get_settings().refresh_token_ttl_days
    row = RefreshToken(
        user_id=user_id, family_id=family_id, token_hash=_hash(raw),
        expires_at=datetime.now(UTC) + timedelta(days=days),
    )
    return raw, row


async def issue(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Start a new session family and return the raw token (only ever shown once)."""
    raw, row = _new_row(user_id, uuid.uuid4())
    db.add(row)
    await db.commit()
    return raw


async def rotate(db: AsyncSession, raw: str) -> tuple[User, str]:
    row = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == _hash(raw))
        .with_for_update().execution_options(populate_existing=True))
    if row is None:
        await db.rollback()
        raise InvalidRefresh
    now = datetime.now(UTC)
    if row.revoked_at is not None or row.expires_at <= now:
        await db.rollback()
        raise InvalidRefresh
    user_id, family_id = row.user_id, row.family_id
    if row.used_at is not None:
        # An old token came back: someone copied it. Kill the whole session.
        await db.execute(update(RefreshToken).where(
            RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
        ).values(revoked_at=now))
        await audit(db, actor_id=user_id, action="auth.refresh_reuse", entity_type="user",
                    entity_id=user_id, metadata={"family_id": str(family_id)})
        await db.commit()
        raise InvalidRefresh
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        await db.rollback()
        raise InvalidRefresh
    row.used_at = now
    new_raw, new_row = _new_row(user_id, family_id)
    db.add(new_row)
    await db.commit()
    return user, new_raw


async def revoke(db: AsyncSession, raw: str) -> None:
    row = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(raw)))
    if row is None:
        return
    await db.execute(update(RefreshToken).where(
        RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None)
    ).values(revoked_at=datetime.now(UTC)))
    await db.commit()
