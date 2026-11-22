"""Transactions list/get tests. Empty DB at this point — Session 6 adds transfers."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.main import app
from app.models import User, Wallet


async def _purge_test_users() -> None:
    async with SessionLocal() as db:
        user_ids = list(
            (await db.scalars(select(User.id).where(User.phone.like("+2547999%")))).all()
        )
        if not user_ids:
            return
        wallets = (
            await db.scalars(select(Wallet).where(Wallet.user_id.in_(user_ids)))
        ).all()
        for w in wallets:
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
    await _purge_test_users()
    yield
    await _purge_test_users()


async def _register_and_token(client, phone: str) -> str:
    await client.post(
        "/auth/register",
        json={"phone": phone, "full_name": "Tx Test", "password": "hunter2hunter2"},
    )
    r = await client.post(
        "/auth/login", json={"phone": phone, "password": "hunter2hunter2"}
    )
    return r.json()["access_token"]


async def test_transactions_empty_list(client, cleanup_users):
    token = await _register_and_token(client, "+254799900010")
    r = await client.get(
        "/transactions", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"] == []
    assert body["meta"] == {"total": 0, "limit": 20, "offset": 0}


async def test_transaction_get_not_found(client, cleanup_users):
    token = await _register_and_token(client, "+254799900011")
    r = await client.get(
        f"/transactions/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404
