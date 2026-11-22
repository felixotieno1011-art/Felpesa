"""Shared pytest fixtures for Felpesa tests.

Async SQLAlchemy + pytest-asyncio note:
  Each pytest-asyncio test runs in its OWN event loop. A shared asyncpg
  connection pool cannot be reused across loops — futures/pending
  operations bind to the loop that created them. The fix is to dispose
  the engine before and after every test so each test starts with a
  fresh pool bound to its own loop.
"""
import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.main import app
from app.models import AuditLog, LedgerEntry, Transaction, User, Wallet


TEST_PHONE_PREFIX = "+2547999"


async def purge_test_users() -> None:
    """Delete all test users with their wallets, transactions, ledger entries.

    FK-safe order (all use ON DELETE RESTRICT):
      audit_logs → ledger_entries → transactions → wallets → users
    """
    async with SessionLocal() as db:
        user_ids = list(
            (await db.scalars(
                select(User.id).where(User.phone.like(f"{TEST_PHONE_PREFIX}%"))
            )).all()
        )
        if not user_ids:
            return

        for a in (await db.scalars(
            select(AuditLog).where(AuditLog.actor_id.in_(user_ids))
        )).all():
            await db.delete(a)
        await db.flush()

        wallet_ids = list(
            (await db.scalars(select(Wallet.id).where(Wallet.user_id.in_(user_ids)))).all()
        )
        if wallet_ids:
            txn_ids = list(
                (await db.scalars(
                    select(Transaction.id).where(
                        (Transaction.from_wallet_id.in_(wallet_ids))
                        | (Transaction.to_wallet_id.in_(wallet_ids))
                        | (Transaction.initiated_by.in_(user_ids))
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
            for w in (await db.scalars(
                select(Wallet).where(Wallet.id.in_(wallet_ids))
            )).all():
                await db.delete(w)
            await db.flush()
        for uid in user_ids:
            u = await db.get(User, uid)
            if u is not None:
                await db.delete(u)
        await db.commit()


@pytest.fixture(autouse=True)
async def _reset_pool() -> AsyncGenerator[None, None]:
    """Dispose the asyncpg + Redis pool before AND after every test.

    Why: pytest-asyncio creates a fresh event loop per test. Pooled
    connections from the previous loop's engine/Redis client cannot be
    used on the new loop. Disposing between tests forces fresh
    connections bound to the current loop.

    - asyncpg via engine.dispose()
    - Redis via resetting the module-level singleton

    Costs ~100ms/test, buys cross-loop correctness.
    """
    from app.core import redis as redis_module

    await engine.dispose()
    # Reset Redis singleton so the next test creates a client bound to its loop
    if redis_module._redis_client is not None:
        try:
            await redis_module._redis_client.aclose()
        except Exception:
            pass
        redis_module._redis_client = None

    yield

    try:
        await engine.dispose()
    except Exception:
        pass
    if redis_module._redis_client is not None:
        try:
            await redis_module._redis_client.aclose()
        except Exception:
            pass
        redis_module._redis_client = None


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
async def cleanup_users() -> AsyncGenerator[None, None]:
    await purge_test_users()
    yield
    try:
        await purge_test_users()
    except Exception:
        pass


async def register_and_login(
    client: AsyncClient, phone: str, *, admin: bool = False
) -> tuple[str, str]:
    from app.core.security import hash_password

    if admin:
        async with SessionLocal() as db:
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
            wallet_id = str(w.id)
    else:
        r = await client.post(
            "/auth/register",
            json={"phone": phone, "full_name": "Test User", "password": "hunter2hunter2"},
        )
        assert r.status_code == 201, f"register({phone}) → {r.status_code}: {r.text}"
        wallet_id = r.json()["wallet_id"]

    t = await client.post(
        "/auth/login", json={"phone": phone, "password": "hunter2hunter2"}
    )
    assert t.status_code == 200, f"login({phone}) → {t.status_code}: {t.text}"
    return wallet_id, t.json()["access_token"]


async def fund_wallet(wallet_id: str, amount: str) -> None:
    async with SessionLocal() as db:
        w = await db.get(Wallet, uuid.UUID(wallet_id))
        if w is None:
            raise AssertionError(f"fund_wallet: wallet {wallet_id} not found")
        amt = Decimal(amount)
        txn = Transaction(
            idempotency_key=f"seed-{uuid.uuid4()}",
            type="deposit",
            status="completed",
            amount=amt,
            currency="KES",
            from_wallet_id=None,
            to_wallet_id=w.id,
            initiated_by=w.user_id,
            description="test seed",
        )
        db.add(txn)
        await db.flush()
        db.add(
            LedgerEntry(
                transaction_id=txn.id,
                wallet_id=w.id,
                direction="credit",
                amount=amt,
                balance_after=w.balance + amt,
            )
        )
        w.balance = w.balance + amt
        await db.commit()


async def register_user_and_wallet(
    client: AsyncClient, phone: str
) -> tuple[str, str, str]:
    """Register a fresh user and login. Returns (user_id, wallet_id, access_token).

    For transfer tests that need initiated_by=user_id. The plain
    register_and_login returns only (wallet_id, access_token).
    """
    r = await client.post(
        "/auth/register",
        json={"phone": phone, "full_name": "Test User", "password": "hunter2hunter2"},
    )
    assert r.status_code == 201, f"register({phone}) → {r.status_code}: {r.text}"
    body = r.json()
    user_id = body["id"]
    wallet_id = body["wallet_id"]

    t = await client.post(
        "/auth/login", json={"phone": phone, "password": "hunter2hunter2"}
    )
    assert t.status_code == 200, f"login({phone}) → {t.status_code}: {t.text}"
    return user_id, wallet_id, t.json()["access_token"]
