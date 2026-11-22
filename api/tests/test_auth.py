"""Auth tests: register, login, protected route, invalid token."""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.main import app
from app.models import User, Wallet


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def _purge_test_users() -> None:
    """Delete all test users (+ their wallets) with the +2547999% prefix.

    Order matters: wallets FK to users with ON DELETE RESTRICT, so we must
    delete wallets first. This is the same constraint the production code
    depends on — it's not just here to satisfy the test, it's here to
    demonstrate the RESTRICT is doing its job.
    """
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
async def cleanup_users():
    """Wipe test users before AND after each test. Idempotent.

    Before: cleans up leftovers from a crashed earlier run.
    After:  leaves a clean DB for the next test (or the next person who
            runs pytest on this machine).

    Running twice is cheap; running zero times on a dirty DB is expensive.
    """
    await _purge_test_users()
    yield
    await _purge_test_users()


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
