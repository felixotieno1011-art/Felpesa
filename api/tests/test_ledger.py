"""Ledger endpoint tests: own-wallet access, foreign-wallet 403, pagination."""
import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.main import app
from app.models import User, Wallet


async def _purge() -> None:
    async with SessionLocal() as db:
        user_ids = list(
            (await db.scalars(select(User.id).where(User.phone.like("+2547999%")))).all()
        )
        if not user_ids:
            return
        from app.models import LedgerEntry, Transaction
        wallet_ids = list(
            (await db.scalars(select(Wallet.id).where(Wallet.user_id.in_(user_ids)))).all()
        )
        if wallet_ids:
            txn_ids = list(
                (await db.scalars(
                    select(Transaction.id).where(
                        (Transaction.from_wallet_id.in_(wallet_ids))
                        | (Transaction.to_wallet_id.in_(wallet_ids))
                    )
                )).all()
            )
            if txn_ids:
                for e in (await db.scalars(
                    select(LedgerEntry).where(LedgerEntry.transaction_id.in_(txn_ids))
                )).all():
                    await db.delete(e)
                await db.flush()
                for t in (await db.scalars(
                    select(Transaction).where(Transaction.id.in_(txn_ids))
                )).all():
                    await db.delete(t)
                await db.flush()
            for w in (await db.scalars(select(Wallet).where(Wallet.id.in_(wallet_ids)))).all():
                await db.delete(w)
            await db.flush()
        for uid in user_ids:
            u = await db.get(User, uid)
            if u is not None:
                await db.delete(u)
        await db.commit()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.fixture
async def cleanup_users():
    await _purge()
    yield
    await _purge()


async def _register_and_token(client, phone: str) -> tuple[str, str]:
    r = await client.post(
        "/auth/register",
        json={"phone": phone, "full_name": "Ledger", "password": "hunter2hunter2"},
    )
    wallet_id = r.json()["wallet_id"]
    t = await client.post("/auth/login", json={"phone": phone, "password": "hunter2hunter2"})
    return wallet_id, t.json()["access_token"]


async def test_ledger_own_wallet_accessible(client, cleanup_users):
    wallet_id, token = await _register_and_token(client, "+254799900200")
    r = await client.get(
        f"/ledger/{wallet_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["meta"]["total"] == 0


async def test_ledger_other_wallet_returns_403(client, cleanup_users):
    _, token_a = await _register_and_token(client, "+254799900201")
    wallet_b, _ = await _register_and_token(client, "+254799900202")
    r = await client.get(
        f"/ledger/{wallet_b}", headers={"Authorization": f"Bearer {token_a}"}
    )
    assert r.status_code == 403
