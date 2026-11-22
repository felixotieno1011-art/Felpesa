"""Transfer tests: happy path, idempotency, insufficient funds, same-wallet,
currency mismatch, and the concurrency test that proves the row lock works."""
import asyncio
import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.main import app
from app.models import LedgerEntry, Transaction, User, Wallet


async def _purge_test_users() -> None:
    async with SessionLocal() as db:
        user_ids = list(
            (await db.scalars(select(User.id).where(User.phone.like("+2547999%")))).all()
        )
        if not user_ids:
            return
        wallet_ids = list(
            (await db.scalars(select(Wallet.id).where(Wallet.user_id.in_(user_ids)))).all()
        )
        # txn -> ledger_entries -> wallets -> users (respect RESTRICT).
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
                entries = (
                    await db.scalars(
                        select(LedgerEntry).where(LedgerEntry.transaction_id.in_(txn_ids))
                    )
                ).all()
                for e in entries:
                    await db.delete(e)
                await db.flush()
                txns = (
                    await db.scalars(select(Transaction).where(Transaction.id.in_(txn_ids)))
                ).all()
                for t in txns:
                    await db.delete(t)
                await db.flush()
            wallets = (
                await db.scalars(select(Wallet).where(Wallet.id.in_(wallet_ids)))
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


async def _register(client, phone: str) -> tuple[str, str]:
    """Returns (user_id, wallet_id)."""
    r = await client.post(
        "/auth/register",
        json={"phone": phone, "full_name": "Tx", "password": "hunter2hunter2"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"], r.json()["wallet_id"]


async def _token(client, phone: str) -> str:
    r = await client.post("/auth/login", json={"phone": phone, "password": "hunter2hunter2"})
    return r.json()["access_token"]


async def _fund_wallet(wallet_id: str, amount: str) -> None:
    """Test-only: give a wallet money by directly writing ledger + balance.

    In real life this would be a deposit endpoint. For v1, we bootstrap
    balances this way so transfers have something to move.
    """
    async with SessionLocal() as db:
        w = await db.get(Wallet, uuid.UUID(wallet_id))
        # Insert a synthetic deposit transaction so the ledger stays consistent.
        txn = Transaction(
            idempotency_key=f"seed-{uuid.uuid4()}",
            type="deposit",
            status="completed",
            amount=Decimal(amount),
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
                amount=Decimal(amount),
                balance_after=w.balance + Decimal(amount),
            )
        )
        # Counter-entry: deposit from "external" — modeled as debit on a
        # synthetic wallet is out of scope for v1; instead we permit the
        # ledger's "deposits may have single-sided entries" exception and
        # document it in reconciliation (v1 only reconciles transfers).
        w.balance = w.balance + Decimal(amount)
        await db.commit()


async def test_transfer_happy_path(client, cleanup_users):
    a_id, a_wallet = await _register(client, "+254799900100")
    b_id, b_wallet = await _register(client, "+254799900101")
    await _fund_wallet(a_wallet, "1000.0000")
    token = await _token(client, "+254799900100")

    r = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
        json={
            "to_wallet_id": b_wallet,
            "amount": "250.0000",
            "currency": "KES",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["amount"] == "250.0000"

    async with SessionLocal() as db:
        a = await db.get(Wallet, uuid.UUID(a_wallet))
        b = await db.get(Wallet, uuid.UUID(b_wallet))
        assert a.balance == Decimal("750.0000")
        assert b.balance == Decimal("250.0000")


async def test_transfer_idempotency(client, cleanup_users):
    _, a_wallet = await _register(client, "+254799900102")
    _, b_wallet = await _register(client, "+254799900103")
    await _fund_wallet(a_wallet, "1000.0000")
    token = await _token(client, "+254799900102")
    key = str(uuid.uuid4())

    body = {"to_wallet_id": b_wallet, "amount": "100.0000", "currency": "KES"}
    r1 = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
        json=body,
    )
    r2 = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
        json=body,
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]

    async with SessionLocal() as db:
        a = await db.get(Wallet, uuid.UUID(a_wallet))
        b = await db.get(Wallet, uuid.UUID(b_wallet))
        assert a.balance == Decimal("900.0000")
        assert b.balance == Decimal("100.0000")


async def test_transfer_insufficient_funds(client, cleanup_users):
    _, a_wallet = await _register(client, "+254799900104")
    _, b_wallet = await _register(client, "+254799900105")
    await _fund_wallet(a_wallet, "50.0000")
    token = await _token(client, "+254799900104")

    r = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
        json={"to_wallet_id": b_wallet, "amount": "100.0000", "currency": "KES"},
    )
    assert r.status_code == 422
    assert "Insufficient" in r.json()["detail"]


async def test_transfer_to_self(client, cleanup_users):
    _, a_wallet = await _register(client, "+254799900106")
    await _fund_wallet(a_wallet, "1000.0000")
    token = await _token(client, "+254799900106")

    r = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
        json={"to_wallet_id": a_wallet, "amount": "10.0000", "currency": "KES"},
    )
    assert r.status_code == 422
    assert "self" in r.json()["detail"].lower()


async def test_transfer_ledger_balances(client, cleanup_users):
    """Every transfer creates exactly 2 ledger entries summing to zero."""
    _, a_wallet = await _register(client, "+254799900107")
    _, b_wallet = await _register(client, "+254799900108")
    await _fund_wallet(a_wallet, "500.0000")
    token = await _token(client, "+254799900107")

    r = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
        json={"to_wallet_id": b_wallet, "amount": "200.0000", "currency": "KES"},
    )
    assert r.status_code == 201
    txn_id = uuid.UUID(r.json()["id"])

    async with SessionLocal() as db:
        entries = (
            await db.scalars(
                select(LedgerEntry).where(LedgerEntry.transaction_id == txn_id)
            )
        ).all()
        assert len(entries) == 2
        debits = sum(e.amount for e in entries if e.direction == "debit")
        credits = sum(e.amount for e in entries if e.direction == "credit")
        assert debits == credits == Decimal("200.0000")


async def test_concurrent_transfers_no_double_spend(client, cleanup_users):
    """Two simultaneous transfers attempt to drain the same 100 KES wallet.

    This test calls execute_transfer directly from two separate DB sessions,
    NOT through the HTTP client. Reason: httpx.AsyncClient + ASGITransport
    serializes requests through one event loop task, so `asyncio.gather` on
    two client.post calls may run them sequentially (first commits + releases
    lock, THEN second begins). That would pass by accident and prove nothing.

    By opening two real sessions and calling the service directly, we
    guarantee concurrent transactions and exercise the real FOR UPDATE lock.
    """
    a_id, a_wallet = await _register(client, "+254799900109")
    _, b_wallet = await _register(client, "+254799900110")
    _, c_wallet = await _register(client, "+254799900111")
    await _fund_wallet(a_wallet, "100.0000")

    from app.services import transfer_service

    async def attempt(to_wallet_id: str):
        async with SessionLocal() as db:
            try:
                txn = await transfer_service.execute_transfer(
                    db,
                    initiated_by=uuid.UUID(a_id),
                    from_wallet_id=uuid.UUID(a_wallet),
                    to_wallet_id=uuid.UUID(to_wallet_id),
                    amount=Decimal("100.0000"),
                    currency="KES",
                    idempotency_key=str(uuid.uuid4()),
                )
                return ("ok", str(txn.id))
            except transfer_service.InsufficientFunds:
                return ("insufficient", None)

    results = await asyncio.gather(attempt(b_wallet), attempt(c_wallet))
    outcomes = sorted([r[0] for r in results])
    assert outcomes == ["insufficient", "ok"], f"got {outcomes}"

    async with SessionLocal() as db:
        a = await db.get(Wallet, uuid.UUID(a_wallet))
        assert a.balance == Decimal("0.0000"), f"expected 0, got {a.balance}"


async def test_for_update_blocks_concurrent_writers(client, cleanup_users):
    """Direct proof that SELECT ... FOR UPDATE serializes writers.

    Holds the lock on a wallet for 300ms in session A; measures how long
    session B blocks trying to take the same lock. If FOR UPDATE works,
    B waits at least ~0.2s (tolerance for scheduling jitter).
    """
    import time

    from sqlalchemy import select

    a_id, a_wallet = await _register(client, "+254799900112")
    wallet_uuid = uuid.UUID(a_wallet)

    async def hold_lock_briefly() -> None:
        async with SessionLocal() as db:
            await db.execute(
                select(Wallet).where(Wallet.id == wallet_uuid).with_for_update()
            )
            await asyncio.sleep(0.3)
            await db.commit()

    async def take_lock_measure() -> float:
        async with SessionLocal() as db:
            start = time.monotonic()
            await db.execute(
                select(Wallet).where(Wallet.id == wallet_uuid).with_for_update()
            )
            elapsed = time.monotonic() - start
            await db.commit()
            return elapsed

    results = await asyncio.gather(hold_lock_briefly(), take_lock_measure())
    wait_time = results[1]
    assert wait_time > 0.2, (
        f"Expected second lock to wait >0.2s (lock not working?), got {wait_time:.3f}s"
    )
