"""Reconciliation tests, including the deliberate-corruption proof."""
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Wallet
from tests.conftest import register_and_login


async def test_reconciliation_requires_admin(client: AsyncClient):
    _, token = await register_and_login(client, "+254799900300")
    r = await client.get("/reconciliation", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


async def test_reconciliation_clean_db_returns_ok(client: AsyncClient):
    _, token = await register_and_login(client, "+254799900301", admin=True)
    r = await client.get("/reconciliation", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["unbalanced_transactions"] == []
    assert body["wallet_mismatches"] == []


async def test_reconciliation_detects_corruption(client: AsyncClient):
    admin_wallet, token = await register_and_login(
        client, "+254799900302", admin=True
    )

    # Baseline
    r = await client.get("/reconciliation", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["ok"] is True

    # Corrupt
    async with SessionLocal() as db:
        w = await db.get(Wallet, __import__("uuid").UUID(admin_wallet))
        w.balance = Decimal("999.0000")
        await db.commit()

    r = await client.get("/reconciliation", headers={"Authorization": f"Bearer {token}"})
    body = r.json()
    assert body["ok"] is False
    assert len(body["wallet_mismatches"]) >= 1
    mism = [m for m in body["wallet_mismatches"] if m["wallet_id"] == admin_wallet]
    assert len(mism) == 1
    assert Decimal(mism[0]["difference"]) == Decimal("999.0000")

    # Repair
    async with SessionLocal() as db:
        w = await db.get(Wallet, __import__("uuid").UUID(admin_wallet))
        w.balance = Decimal("0")
        await db.commit()

    r = await client.get("/reconciliation", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["ok"] is True
