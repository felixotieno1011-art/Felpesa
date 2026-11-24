"""Seed demo paybill/till merchants. Safe to run repeatedly."""
import asyncio

from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.models import Merchant, User, Wallet

DEMO_MERCHANTS = [
    ("paybill", "888880", "Demo Power Co"),
    ("paybill", "888881", "Demo Water Ltd"),
    ("buygoods", "500100", "Demo Duka"),
    ("buygoods", "500101", "Demo Cafe"),
]


async def seed() -> None:
    async with SessionLocal() as db:
        for kind, number, name in DEMO_MERCHANTS:
            exists = await db.scalar(
                select(Merchant).where(Merchant.kind == kind, Merchant.number == number)
            )
            if exists:
                print(f"skip  {kind} {number}")
                continue

            code = "1" if kind == "paybill" else "2"
            user = User(
                phone=f"+00{code}{number}",
                full_name=name,
                password_hash="!",  # invalid hash: can never log in
                role="user",
                is_active=False,
            )
            db.add(user)
            await db.flush()

            wallet = Wallet(user_id=user.id, currency="KES", is_system=False)
            db.add(wallet)
            await db.flush()

            db.add(Merchant(kind=kind, number=number, name=name, wallet_id=wallet.id))
            print(f"added {kind} {number} {name}")
        await db.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
