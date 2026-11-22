"""Fraud flag tests. Verify flags are set but transfers still succeed."""
import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Transaction
from tests.conftest import fund_wallet, register_user_and_wallet


async def _do_transfer(client, token, to_wallet, amount, idem=None):
    return await client.post(
        "/transfers",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": idem or str(uuid.uuid4()),
        },
        json={"to_wallet_id": to_wallet, "amount": amount, "currency": "KES"},
    )


async def test_amount_threshold_flags_transfer(client: AsyncClient):
    _, a_wallet, token = await register_user_and_wallet(client, "+254799900600")
    _, b_wallet, _ = await register_user_and_wallet(client, "+254799900601")
    await fund_wallet(a_wallet, "100000.0000")

    # 60,000 > threshold (50,000) → flagged
    r = await _do_transfer(client, token, b_wallet, "60000.0000")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["flagged_fraud"] is True
    assert body["fraud_reason"].startswith("amount_above_threshold")

    # Also verify transaction succeeded (not blocked)
    async with SessionLocal() as db:
        txn = await db.get(Transaction, uuid.UUID(body["id"]))
        assert txn.status == "completed"
        assert txn.flagged_fraud is True


async def test_small_transfer_not_flagged(client: AsyncClient):
    _, a_wallet, token = await register_user_and_wallet(client, "+254799900602")
    _, b_wallet, _ = await register_user_and_wallet(client, "+254799900603")
    await fund_wallet(a_wallet, "1000.0000")

    r = await _do_transfer(client, token, b_wallet, "100.0000")
    assert r.status_code == 201
    body = r.json()
    assert body["flagged_fraud"] is False
    assert body["fraud_reason"] is None


async def test_velocity_flags_fourth_transfer(client: AsyncClient):
    _, a_wallet, token = await register_user_and_wallet(client, "+254799900604")
    _, b_wallet, _ = await register_user_and_wallet(client, "+254799900605")
    await fund_wallet(a_wallet, "1000.0000")

    flags = []
    for i in range(5):
        r = await _do_transfer(client, token, b_wallet, "10.0000")
        assert r.status_code == 201, f"transfer {i+1}: {r.text}"
        flags.append(r.json()["flagged_fraud"])

    # Config: fraud_rapid_max_transfers=3, so the 4th and 5th (index 3, 4) flag.
    # (each transfer creates 1 row before evaluation, so count at eval time for
    # transfer N is N-1. Transfer 4 sees count=3, which is >= max(3) → flag.)
    assert flags[0] is False
    assert flags[1] is False
    assert flags[2] is False
    assert flags[3] is True, f"4th should flag, flags: {flags}"
    assert flags[4] is True, f"5th should flag, flags: {flags}"
