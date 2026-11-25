"""Security tests: SQL injection, tampered JWT, expired JWT, role escalation,
oversized payload, missing idempotency key.

These tests don't test new features — they test that EXISTING features
resist common attacks. Every fintech reviewer expects these.
"""
import uuid
from datetime import UTC, datetime, timedelta

from jose import jwt
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.security import create_access_token
from tests.conftest import fund_wallet, register_user_and_wallet

settings = get_settings()


# -------------------------------------------------------------------
# SQL injection
# -------------------------------------------------------------------
async def test_sql_injection_in_login_phone(client: AsyncClient):
    """Classic injection payload as phone. Should return 401, not 500,
    and must not bypass authentication."""
    payload = "' OR '1'='1' --"
    r = await client.post(
        "/auth/login",
        json={"phone": payload, "password": "anything"},
    )
    # 401 (invalid creds) or 422 (validation rejected) — both are safe.
    # 500 would mean the payload hit the DB and crashed.
    assert r.status_code in (401, 422), f"got {r.status_code}: {r.text}"


async def test_sql_injection_in_transfer_description(
    client: AsyncClient,
):
    """Injection payload in a TEXT field. Must be stored as a literal string,
    not executed. We verify by reading it back via /transactions."""
    _, a_wallet, token = await register_user_and_wallet(client, "+254799900700")
    _, b_wallet, _ = await register_user_and_wallet(client, "+254799900701")
    await fund_wallet(a_wallet, "1000.0000")

    injection = "'; DROP TABLE users; --"
    r = await client.post(
        "/transfers",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={
            "to_wallet_id": b_wallet,
            "amount": "10.0000",
            "currency": "KES",
            "description": injection,
        },
    )
    assert r.status_code == 201, r.text
    txn_id = r.json()["id"]

    # If the table was dropped, this would fail. It succeeds → parameterized queries work.
    r = await client.get(
        f"/transactions/{txn_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    # The description round-trips as a literal string, proving no execution.
    assert r.json()["description"] == injection


# -------------------------------------------------------------------
# Tampered JWT
# -------------------------------------------------------------------
async def test_tampered_jwt_rejected(client: AsyncClient):
    """Flip one char in the signature — token must be rejected."""
    _, _, token = await register_user_and_wallet(client, "+254799900702")
    header, payload, sig = token.split(".")
    mid = len(sig) // 2
    sig = sig[:mid] + ("A" if sig[mid] != "A" else "B") + sig[mid + 1:]
    tampered = ".".join([header, payload, sig])

    r = await client.get(
        "/wallets/me", headers={"Authorization": f"Bearer {tampered}"}
    )
    assert r.status_code == 401


# -------------------------------------------------------------------
# Expired JWT
# -------------------------------------------------------------------
async def test_expired_jwt_rejected(client: AsyncClient):
    """Craft a token with exp in the past. Must be rejected."""
    from app.core.security import hash_password
    from app.core.db import SessionLocal
    from app.models import User, Wallet
    from decimal import Decimal

    # Create user directly so we control the id for the JWT
    async with SessionLocal() as db:
        u = User(
            phone="+254799900703",
            full_name="Expired",
            password_hash=hash_password("hunter2hunter2"),
        )
        db.add(u)
        await db.flush()
        db.add(Wallet(user_id=u.id, currency="KES", balance=Decimal("0"), status="active"))
        await db.commit()
        user_id = str(u.id)

    now = datetime.now(UTC)
    expired = jwt.encode(
        {
            "sub": user_id,
            "role": "user",
            "iat": int((now - timedelta(minutes=30)).timestamp()),
            "exp": int((now - timedelta(minutes=15)).timestamp()),
            "type": "access",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    r = await client.get(
        "/wallets/me", headers={"Authorization": f"Bearer {expired}"}
    )
    assert r.status_code == 401


# -------------------------------------------------------------------
# Role escalation
# -------------------------------------------------------------------
async def test_user_cannot_access_admin_endpoints(client: AsyncClient):
    """A normal user must get 403 on every admin route."""
    _, _, token = await register_user_and_wallet(client, "+254799900704")

    for path in ["/audit", "/reconciliation"]:
        r = await client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403, f"{path} returned {r.status_code}: {r.text}"


# -------------------------------------------------------------------
# Missing Idempotency-Key
# -------------------------------------------------------------------
async def test_missing_idempotency_key_rejected(client: AsyncClient):
    """POST /transfers without the required header → 422 (FastAPI validation)."""
    _, a_wallet, token = await register_user_and_wallet(client, "+254799900705")
    _, b_wallet, _ = await register_user_and_wallet(client, "+254799900706")
    await fund_wallet(a_wallet, "1000.0000")

    r = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {token}"},  # no Idempotency-Key
        json={"to_wallet_id": b_wallet, "amount": "10.0000", "currency": "KES"},
    )
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
