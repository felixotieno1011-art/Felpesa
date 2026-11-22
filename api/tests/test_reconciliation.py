"""Reconciliation tests, including the deliberate-corruption proof.

The corruption test is the one that matters. Without it, a /reconciliation
that always returns {"ok": true} passes. The corruption test proves the
endpoint can actually detect imbalance — i.e. that it does something.
"""
import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

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


async def _make_admin(phone: str) -> str:
    """Register a user, promote to admin, return token."""
    async with SessionLocal() as db:
        # Make sure a fresh user exists via direct insert (avoids /auth/register
        # conflict). We'll set role to admin immediately.
        from app.core.security import hash_password
        u = User(
            phone=phone,
            full_name="Admin",
            password_hash=hash_password("hunter2hunter2"),
            role="admin",
        )
        db.add(u)
        await db.flush()
        w = Wallet(user_id=u.id, currency="KES", balance=Decimal("0"), status="active")
        db.add(w)
        await db.commit()

    # login
    r = await _client().post(
        "/auth/login", json={"phone": phone, "password": "hunter2hunter2"}
    )
    # We need an AsyncClient; simplest is to just make one inline.
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(
                "/auth/login", json={"phone": phone, "password": "hunter2hunter2"}
            )
            return r.json()["access_token"]


def _client():
    return None  # placeholder, unused


async def test_reconciliation_requires_admin(client, cleanup_users):
    # non-admin token
    await client.post(
        "/auth/register",
        json={"phone": "+254799900300", "full_name": "User", "password": "hunter2hunter2"},
    )
    t = await client.post(
        "/auth/login", json={"phone": "+254799900300", "password": "hunter2hunter2"}
    )
    token = t.json()["access_token"]
    r = await client.get("/reconciliation", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


async def test_reconciliation_clean_db_returns_ok(client, cleanup_users):
    # Make admin
    from app.core.security import hash_password
    async with SessionLocal() as db:
        u = User(
            phone="+254799900301",
            full_name="Admin",
            password_hash=hash_password("hunter2hunter2"),
            role="admin",
        )
        db.add(u)
        await db.flush()
        w = Wallet(user_id=u.id, currency="KES", balance=Decimal("0"), status="active")
        db.add(w)
        await db.commit()

    t = await client.post(
        "/auth/login", json={"phone": "+254799900301", "password": "hunter2hunter2"}
    )
    token = t.json()["access_token"]
    r = await client.get("/reconciliation", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["unbalanced_transactions"] == []
    assert body["wallet_mismatches"] == []


async def test_reconciliation_detects_corruption(client, cleanup_users):
    """THE proof. Corrupt a wallet's cached balance, expect ok: false."""
    from app.core.security import hash_password

    # Create admin
    async with SessionLocal() as db:
        u = User(
            phone="+254799900302",
            full_name="Admin",
            password_hash=hash_password("hunter2hunter2"),
            role="admin",
        )
        db.add(u)
        await db.flush()
        w_admin = Wallet(user_id=u.id, currency="KES", balance=Decimal("0"), status="active")
        db.add(w_admin)
        await db.commit()
        admin_wallet_id = w_admin.id

    t = await client.post(
        "/auth/login", json={"phone": "+254799900302", "password": "hunter2hunter2"}
    )
    token = t.json()["access_token"]

    # Baseline: clean
    r = await client.get("/reconciliation", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["ok"] is True

    # Corrupt: set the admin's wallet balance to 999 even though ledger says 0
    async with SessionLocal() as db:
        w = await db.get(Wallet, admin_wallet_id)
        w.balance = Decimal("999.0000")
        await db.commit()

    # Reconcile should now find ONE wallet mismatch
    r = await client.get("/reconciliation", headers={"Authorization": f"Bearer {token}"})
    body = r.json()
    assert body["ok"] is False
    assert len(body["wallet_mismatches"]) >= 1
    mism = [m for m in body["wallet_mismatches"] if m["wallet_id"] == str(admin_wallet_id)]
    assert len(mism) == 1
    assert Decimal(mism[0]["difference"]) == Decimal("999.0000")

    # Repair: restore to 0
    async with SessionLocal() as db:
        w = await db.get(Wallet, admin_wallet_id)
        w.balance = Decimal("0")
        await db.commit()

    # Reconcile should be ok again
    r = await client.get("/reconciliation", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["ok"] is True
