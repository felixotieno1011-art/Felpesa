"""Wallet read operations. No money movement here — that's transfer_service."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Wallet


async def get_wallet_for_user(
    db: AsyncSession, *, user_id: uuid.UUID
) -> Wallet | None:
    """The user's wallet (v1: one wallet per user; multi-currency adds `currency=`)."""
    return await db.scalar(select(Wallet).where(Wallet.user_id == user_id))


async def get_wallet_by_id(
    db: AsyncSession, *, wallet_id: uuid.UUID
) -> Wallet | None:
    return await db.get(Wallet, wallet_id)


async def list_wallets(db: AsyncSession) -> list[Wallet]:
    """Admin: all wallets. Not paginated in v1 — small enough at demo scale."""
    return list((await db.scalars(select(Wallet).order_by(Wallet.created_at))).all())
