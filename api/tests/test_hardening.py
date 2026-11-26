"""Hardening: prod deposit switch, idempotency conflicts, auth rate limits."""
import uuid
from decimal import Decimal

from httpx import AsyncClient

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.models import Wallet
from tests.conftest import fund_wallet, register_user_and_wallet


def _h(token: str, key: str | None = None) -> dict:
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": key or str(uuid.uuid4())}


async def _balance(wallet_id: str) -> Decimal:
    async with SessionLocal() as db:
        return (await db.get(Wallet, uuid.UUID(wallet_id))).balance


async def test_deposits_disabled_in_prod(client: AsyncClient, monkeypatch):
    _, _, token = await register_user_and_wallet(client, "+254799900800")
    monkeypatch.setattr(get_settings(), "app_env", "prod")
    r = await client.post("/deposits", headers=_h(token), json={"amount": 100, "currency": "KES"})
    assert r.status_code == 404


async def test_transfer_key_reuse_with_different_params_is_409(client: AsyncClient):
    _, a, token = await register_user_and_wallet(client, "+254799900801")
    _, b, _ = await register_user_and_wallet(client, "+254799900802")
    _, c, _ = await register_user_and_wallet(client, "+254799900803")
    await fund_wallet(a, "1000.0000")
    key = str(uuid.uuid4())

    def body(to, amt):
        return {"to_wallet_id": to, "amount": amt, "currency": "KES"}

    r1 = await client.post("/transfers", headers=_h(token, key), json=body(b, "100.0000"))
    assert r1.status_code == 201, r1.text
    assert (await client.post("/transfers", headers=_h(token, key), json=body(b, "500.0000"))).status_code == 409
    assert (await client.post("/transfers", headers=_h(token, key), json=body(c, "100.0000"))).status_code == 409
    r4 = await client.post("/transfers", headers=_h(token, key), json=body(b, "100.0000"))
    assert r4.status_code == 201 and r4.json()["id"] == r1.json()["id"]
    assert await _balance(a) == Decimal("900.0000")


async def test_deposit_key_reuse_with_different_amount_is_409(client: AsyncClient):
    _, w, token = await register_user_and_wallet(client, "+254799900804")
    key = str(uuid.uuid4())
    r1 = await client.post("/deposits", headers=_h(token, key), json={"amount": 100, "currency": "KES"})
    assert r1.status_code == 201, r1.text
    r2 = await client.post("/deposits", headers=_h(token, key), json={"amount": 200, "currency": "KES"})
    assert r2.status_code == 409
    assert await _balance(w) == Decimal("100.0000")


async def _clear(scope: str) -> None:
    r = get_redis_client()
    async for k in r.scan_iter(f"ratelimit:{scope}:*"):
        await r.delete(k)


async def test_login_is_rate_limited(client: AsyncClient, monkeypatch):
    await register_user_and_wallet(client, "+254799900805")
    monkeypatch.setattr(get_settings(), "rate_limit_auth_per_min", 3)
    await _clear("login-ip")
    await _clear("login-phone")
    bad = {"phone": "+254799900805", "password": "wrong-password"}
    codes = []
    for _ in range(8):  # 8 covers a window rollover mid-test
        r = await client.post("/auth/login", json=bad)
        codes.append(r.status_code)
        if r.status_code == 429:
            assert "Retry-After" in r.headers
            break
    assert 429 in codes, codes
    assert codes.index(429) >= 3, codes
    assert set(codes[:-1]) == {401}, codes


async def test_register_is_rate_limited(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_auth_per_min", 3)
    await _clear("register-ip")
    codes = []
    for i in range(8):
        r = await client.post(
            "/auth/register",
            json={"phone": f"+2547999008{20 + i}", "full_name": "Rate Test",
                  "password": "hunter2hunter2"},
        )
        codes.append(r.status_code)
        if r.status_code == 429:
            break
    assert 429 in codes, codes
    assert codes.index(429) >= 3, codes
    assert set(codes[:-1]) == {201}, codes
