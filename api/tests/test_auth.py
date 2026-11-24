"""Auth tests: register, login, protected route, invalid token."""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.main import app
from app.models import User, Wallet






async def test_register_creates_user_and_wallet(client, cleanup_users):
    r = await client.post(
        "/auth/register",
        json={
            "phone": "+254799900001",
            "full_name": "Test One",
            "password": "hunter2hunter2",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["phone"] == "+254799900001"
    assert body["wallet_id"]

    # Verify in DB
    async with SessionLocal() as db:
        user = (await db.scalars(select(User).where(User.phone == "+254799900001"))).first()
        assert user is not None
        wallet = (await db.scalars(select(Wallet).where(Wallet.user_id == user.id))).first()
        assert wallet is not None
        assert str(wallet.id) == body["wallet_id"]
        assert wallet.balance == 0


async def test_register_duplicate_phone_returns_409(client, cleanup_users):
    payload = {
        "phone": "+254799900002",
        "full_name": "Dup",
        "password": "hunter2hunter2",
    }
    r1 = await client.post("/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/auth/register", json=payload)
    assert r2.status_code == 409


async def test_login_success_and_protected_route(client, cleanup_users):
    await client.post(
        "/auth/register",
        json={
            "phone": "+254799900003",
            "full_name": "LogMeIn",
            "password": "hunter2hunter2",
        },
    )
    r = await client.post(
        "/auth/login",
        json={"phone": "+254799900003", "password": "hunter2hunter2"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    r2 = await client.get("/wallets/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["balance"] == "0.0000"
    assert r2.json()["currency"] == "KES"


async def test_login_wrong_password_returns_401(client, cleanup_users):
    await client.post(
        "/auth/register",
        json={
            "phone": "+254799900004",
            "full_name": "Nope",
            "password": "hunter2hunter2",
        },
    )
    r = await client.post(
        "/auth/login",
        json={"phone": "+254799900004", "password": "wrong-password"},
    )
    assert r.status_code == 401


async def test_protected_route_without_token_returns_401(client):
    r = await client.get("/wallets/me")
    assert r.status_code == 401


async def test_protected_route_with_bad_token_returns_401(client):
    r = await client.get(
        "/wallets/me",
        headers={"Authorization": "Bearer this.is.not.a.jwt"},
    )
    assert r.status_code == 401


async def test_concurrent_duplicate_register_returns_409(client: AsyncClient):
    """Two concurrent registers with same phone: exactly one 201, one 409."""
    phone = "+254799900910"

    async def attempt():
        return await client.post(
            "/auth/register",
            json={"phone": phone, "full_name": "Race User", "password": "hunter2hunter2"},
        )

    r1, r2 = await __import__("asyncio").gather(attempt(), attempt())
    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [201, 409], f"got {statuses}: {r1.text} / {r2.text}"
