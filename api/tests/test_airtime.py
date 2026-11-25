"""Airtime tests."""
import uuid
from decimal import Decimal

from httpx import AsyncClient

from app.core.db import SessionLocal
from app.models import Wallet
from tests.conftest import fund_wallet, register_user_and_wallet
from tests.test_payments import make_merchant

PHONE = "+254712345678"


def _h(token: str, pin: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())}
    if pin:
        h["X-Pin"] = pin
    return h


def _body(amount: str = "50.0000", phone: str = PHONE) -> dict:
    return {"phone": phone, "amount": amount, "currency": "KES"}


async def _setup(client: AsyncClient, p_provider: str, p_user: str, num: str):
    provider = await make_merchant(client, p_provider, "airtime", num)
    _, wallet, token = await register_user_and_wallet(client, p_user)
    await fund_wallet(wallet, "500.0000")
    return provider, wallet, token


async def test_airtime_happy_path(client: AsyncClient):
    provider, wallet, token = await _setup(
        client, "+254799900500", "+254799900501", "770100"
    )
    r = await client.post("/airtime", headers=_h(token), json=_body())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert f"airtime bought for {PHONE}" in body["message"]
    assert "New balance Ksh450.00" in body["message"]

    async with SessionLocal() as db:
        assert (await db.get(Wallet, uuid.UUID(wallet))).balance == Decimal("450.0000")
        assert (await db.get(Wallet, uuid.UUID(provider))).balance == Decimal("50.0000")


async def test_airtime_amount_limits_and_bad_phone(client: AsyncClient):
    _, _, token = await _setup(client, "+254799900502", "+254799900503", "770101")
    assert (await client.post("/airtime", headers=_h(token), json=_body("4.0000"))).status_code == 422
    assert (await client.post("/airtime", headers=_h(token), json=_body("5001.0000"))).status_code == 422
    assert (await client.post("/airtime", headers=_h(token), json=_body(phone="0712345678"))).status_code == 422


async def test_airtime_insufficient_funds(client: AsyncClient):
    _, _, token = await _setup(client, "+254799900504", "+254799900505", "770102")
    r = await client.post("/airtime", headers=_h(token), json=_body("600.0000"))
    assert r.status_code == 422 and r.json()["detail"] == "Insufficient funds"


async def test_airtime_requires_pin_when_set(client: AsyncClient):
    _, _, token = await _setup(client, "+254799900506", "+254799900507", "770103")
    await client.post("/pin", headers={"Authorization": f"Bearer {token}"}, json={"pin": "2468"})
    assert (await client.post("/airtime", headers=_h(token), json=_body())).status_code == 403
    assert (await client.post("/airtime", headers=_h(token, "2468"), json=_body())).status_code == 201


async def test_airtime_idempotent_and_history_filter(client: AsyncClient):
    _, wallet, token = await _setup(client, "+254799900508", "+254799900509", "770104")
    h = _h(token)
    r1 = await client.post("/airtime", headers=h, json=_body())
    r2 = await client.post("/airtime", headers=h, json=_body())
    assert r1.json()["id"] == r2.json()["id"]

    async with SessionLocal() as db:
        assert (await db.get(Wallet, uuid.UUID(wallet))).balance == Decimal("450.0000")

    r = await client.get("/transactions?type=airtime", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and len(r.json()["items"]) == 1
