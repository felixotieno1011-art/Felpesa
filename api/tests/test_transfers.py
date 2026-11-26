"""Transfer tests: happy path, idempotency, insufficient funds, same-wallet,
concurrency, and lock-primitive proof."""
import asyncio
import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import LedgerEntry, Transaction, Wallet
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


async def test_concurrent_opposite_direction_transfers_no_deadlock(client: AsyncClient):
    """A→B and B→A at the same time must both succeed, not deadlock.

    Before the fix: both lock the sender first. Tx1 locks Alice, Tx2 locks
    Bob. Each waits on the other. Postgres kills one → random 500.
    After the fix: both lock in sorted UUID order, so one waits for the
    other instead of deadlocking. Both transfers complete in sequence.

    This is the canonical row-lock ordering test. If it passes, the transfer
    service is safe under concurrent opposite-direction traffic.
    """
    _, a_wallet, token_a = await register_user_and_wallet(client, "+254799900800")
    _, b_wallet, token_b = await register_user_and_wallet(client, "+254799900801")
    await fund_wallet(a_wallet, "1000.0000")
    await fund_wallet(b_wallet, "1000.0000")

    # Barrier: verify funding is fully visible before the concurrent transfer.
    # Without this, the transfer's lock query can race the fund commit
    # (asyncpg + READ COMMITTED), causing the balance to read stale — a
    # source of flaky test failures that aren't a bug in transfer_service.
    async with SessionLocal() as db:
        wa = await db.get(Wallet, uuid.UUID(a_wallet))
        wb = await db.get(Wallet, uuid.UUID(b_wallet))
        assert wa.balance == Decimal("1000.0000"), f"pre-transfer A={wa.balance}"
        assert wb.balance == Decimal("1000.0000"), f"pre-transfer B={wb.balance}"

    async def do_transfer(token: str, to_wallet: str, idem_suffix: str):
        return await client.post(
            "/transfers",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": f"deadlock-test-{idem_suffix}",
            },
            json={"to_wallet_id": to_wallet, "amount": "100.0000", "currency": "KES"},
        )

    # Fire A→B and B→A concurrently.
    r_ab, r_ba = await asyncio.gather(
        do_transfer(token_a, b_wallet, "ab"),
        do_transfer(token_b, a_wallet, "ba"),
    )

    # Both must succeed. If the deadlock fires, one will be a 500.
    assert r_ab.status_code == 201, f"A→B failed: {r_ab.status_code} {r_ab.text}"
    assert r_ba.status_code == 201, f"B→A failed: {r_ba.status_code} {r_ba.text}"

    # Both balances back where they started (each net ±0).
    async with SessionLocal() as db:
        a = await db.get(Wallet, uuid.UUID(a_wallet))
        b = await db.get(Wallet, uuid.UUID(b_wallet))
        assert a.balance == Decimal("1000.0000"), f"a={a.balance}"
        assert b.balance == Decimal("1000.0000"), f"b={b.balance}"


async def test_concurrent_duplicate_idempotency_key_only_one_transfer(client: AsyncClient):
    """Two concurrent requests with the SAME idempotency key must produce
    exactly one transfer. Both callers get the SAME transaction ID.

    Before the fix: both pass the fast-path idempotency check, one commits,
    the other hits the post-lock validation with a now-depleted balance and
    raises InsufficientFunds (wrong error) — OR, if the balance is still
    sufficient, both transfers succeed (double-charge).

    After the fix: the loser's post-lock idempotency re-check finds the
    winner's transaction and returns it. Exactly one transfer moves money.
    """
    a_user, a_wallet, token = await register_user_and_wallet(client, "+254799900810")
    _, b_wallet, _ = await register_user_and_wallet(client, "+254799900811")
    await fund_wallet(a_wallet, "100.0000")

    idem_key = str(uuid.uuid4())

    async def attempt() -> tuple[int, dict | str]:
        r = await client.post(
            "/transfers",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": idem_key,
            },
            json={"to_wallet_id": b_wallet, "amount": "100.0000", "currency": "KES"},
        )
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text

    # Fire both at the same time. Same token, same key, same body.
    r1, r2 = await asyncio.gather(attempt(), attempt())

    # Both must succeed (201) — the loser replays the winner's response.
    assert r1[0] == 201, f"req1 failed: {r1}"
    assert r2[0] == 201, f"req2 failed: {r2}"

    # Both must return the SAME transaction ID — that's the idempotency proof.
    txn_id_1 = r1[1]["id"] if isinstance(r1[1], dict) else None
    txn_id_2 = r2[1]["id"] if isinstance(r2[1], dict) else None
    assert txn_id_1 is not None and txn_id_2 is not None, f"missing id in response: {r1}, {r2}"
    assert txn_id_1 == txn_id_2, f"different txns: {txn_id_1} vs {txn_id_2}"

    # And the balances must reflect exactly ONE transfer, not two.
    async with SessionLocal() as db:
        a = await db.get(Wallet, uuid.UUID(a_wallet))
        b = await db.get(Wallet, uuid.UUID(b_wallet))
        assert a.balance == Decimal("0.0000"), f"sender A={a.balance}, expected 0"
        assert b.balance == Decimal("100.0000"), f"receiver B={b.balance}, expected 100"


async def test_ledger_created_at_uses_clock_timestamp(client: AsyncClient):
    """ledger_entries.created_at defaults to clock_timestamp(), not now()."""
    from sqlalchemy import text as sql_text
    async with SessionLocal() as db:
        row = (await db.execute(sql_text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name='ledger_entries' AND column_name='created_at'"
        ))).scalar()
    assert row is not None
    assert "clock_timestamp" in row.lower(), f"expected clock_timestamp, got {row}"
