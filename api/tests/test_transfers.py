"""Transfer tests: happy path, idempotency, insufficient funds, same-wallet,
concurrency, and lock-primitive proof."""
import asyncio
import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import LedgerEntry, Wallet
from app.services import transfer_service
from tests.conftest import fund_wallet, register_user_and_wallet


async def test_transfer_happy_path(client: AsyncClient):
    _, a_wallet, token = await register_user_and_wallet(client, "+254799900100")
    _, b_wallet, _ = await register_user_and_wallet(client, "+254799900101")
    await fund_wallet(a_wallet, "1000.0000")

    r = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
        json={"to_wallet_id": b_wallet, "amount": "250.0000", "currency": "KES"},
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


async def test_transfer_idempotency(client: AsyncClient):
    _, a_wallet, token = await register_user_and_wallet(client, "+254799900102")
    _, b_wallet, _ = await register_user_and_wallet(client, "+254799900103")
    await fund_wallet(a_wallet, "1000.0000")
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
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text
    assert r1.json()["id"] == r2.json()["id"]

    async with SessionLocal() as db:
        a = await db.get(Wallet, uuid.UUID(a_wallet))
        b = await db.get(Wallet, uuid.UUID(b_wallet))
        assert a.balance == Decimal("900.0000")
        assert b.balance == Decimal("100.0000")


async def test_transfer_insufficient_funds(client: AsyncClient):
    _, a_wallet, token = await register_user_and_wallet(client, "+254799900104")
    _, b_wallet, _ = await register_user_and_wallet(client, "+254799900105")
    await fund_wallet(a_wallet, "50.0000")

    r = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
        json={"to_wallet_id": b_wallet, "amount": "100.0000", "currency": "KES"},
    )
    assert r.status_code == 422
    assert "Insufficient" in r.json()["detail"]


async def test_transfer_to_self(client: AsyncClient):
    _, a_wallet, token = await register_user_and_wallet(client, "+254799900106")
    await fund_wallet(a_wallet, "1000.0000")

    r = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
        json={"to_wallet_id": a_wallet, "amount": "10.0000", "currency": "KES"},
    )
    assert r.status_code == 422
    assert "self" in r.json()["detail"].lower()


async def test_transfer_ledger_balances(client: AsyncClient):
    _, a_wallet, token = await register_user_and_wallet(client, "+254799900107")
    _, b_wallet, _ = await register_user_and_wallet(client, "+254799900108")
    await fund_wallet(a_wallet, "500.0000")

    r = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
        json={"to_wallet_id": b_wallet, "amount": "200.0000", "currency": "KES"},
    )
    assert r.status_code == 201, r.text
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


async def test_concurrent_transfers_no_double_spend(client: AsyncClient):
    a_id, a_wallet, _ = await register_user_and_wallet(client, "+254799900109")
    _, b_wallet, _ = await register_user_and_wallet(client, "+254799900110")
    _, c_wallet, _ = await register_user_and_wallet(client, "+254799900111")
    await fund_wallet(a_wallet, "100.0000")

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
        assert a.balance == Decimal("0.0000")


async def test_for_update_blocks_concurrent_writers(client: AsyncClient):
    import time
    _, a_wallet, _ = await register_user_and_wallet(client, "+254799900112")
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
    assert results[1] > 0.2, f"expected >0.2s wait, got {results[1]:.3f}s"
