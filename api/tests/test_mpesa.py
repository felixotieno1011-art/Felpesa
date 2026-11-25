"""Daraja STK top-up tests. Safaricom is mocked."""
import uuid
from decimal import Decimal

from httpx import AsyncClient

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import Wallet
from app.services import daraja
from tests.conftest import register_user_and_wallet

SECRET = "test-callback-secret"


def _bearer(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _cb(checkout: str, code: int = 0, amount: int = 100, receipt: str = "TEST123ABC") -> dict:
    body = {"MerchantRequestID": "mr1", "CheckoutRequestID": checkout,
            "ResultCode": code, "ResultDesc": "desc"}
    if code == 0:
        body["CallbackMetadata"] = {"Item": [
            {"Name": "Amount", "Value": amount},
            {"Name": "MpesaReceiptNumber", "Value": receipt},
            {"Name": "PhoneNumber", "Value": 254712345678},
        ]}
    return {"Body": {"stkCallback": body}}


async def _start(client, monkeypatch, token, amount=100) -> str:
    checkout = "ws_CO_" + uuid.uuid4().hex[:20]

    async def fake_stk(**kw):
        return {"MerchantRequestID": "mr1", "CheckoutRequestID": checkout, "ResponseCode": "0"}

    s = get_settings()
    monkeypatch.setattr(daraja, "stk_push", fake_stk)
    monkeypatch.setattr(daraja, "is_configured", lambda: True)
    monkeypatch.setattr(s, "mpesa_callback_secret", SECRET)
    monkeypatch.setattr(s, "mpesa_callback_base_url", "https://example.test")
    r = await client.post("/mpesa/stk", headers=_bearer(token),
                          json={"phone": "+254712345678", "amount": amount})
    assert r.status_code == 202, r.text
    assert r.json()["checkout_request_id"] == checkout
    return checkout


async def _balance(wallet_id: str) -> Decimal:
    async with SessionLocal() as db:
        return (await db.get(Wallet, uuid.UUID(wallet_id))).balance


async def _status(client, token, checkout) -> dict:
    r = await client.get(f"/mpesa/status/{checkout}", headers=_bearer(token))
    assert r.status_code == 200, r.text
    return r.json()


async def test_stk_success_credits_once(client: AsyncClient, monkeypatch):
    _, wallet, token = await register_user_and_wallet(client, "+254799900600")
    checkout = await _start(client, monkeypatch, token, 100)
    assert (await _status(client, token, checkout))["status"] == "pending"
    assert await _balance(wallet) == Decimal("0")

    for _ in range(2):  # second call = Safaricom retry
        r = await client.post(f"/mpesa/callback/{SECRET}", json=_cb(checkout))
        assert r.status_code == 200 and r.json()["ResultCode"] == 0

    st = await _status(client, token, checkout)
    assert st["status"] == "completed" and st["mpesa_receipt"] == "TEST123ABC"
    assert await _balance(wallet) == Decimal("100.0000")


async def test_stk_cancelled_by_user(client: AsyncClient, monkeypatch):
    _, wallet, token = await register_user_and_wallet(client, "+254799900601")
    checkout = await _start(client, monkeypatch, token)
    await client.post(f"/mpesa/callback/{SECRET}", json=_cb(checkout, code=1032))
    assert (await _status(client, token, checkout))["status"] == "cancelled"
    assert await _balance(wallet) == Decimal("0")


async def test_callback_wrong_secret_rejected(client: AsyncClient, monkeypatch):
    _, wallet, token = await register_user_and_wallet(client, "+254799900602")
    checkout = await _start(client, monkeypatch, token)
    r = await client.post("/mpesa/callback/wrong", json=_cb(checkout))
    assert r.status_code == 404
    assert await _balance(wallet) == Decimal("0")


async def test_amount_mismatch_needs_review(client: AsyncClient, monkeypatch):
    _, wallet, token = await register_user_and_wallet(client, "+254799900603")
    checkout = await _start(client, monkeypatch, token, 100)
    await client.post(f"/mpesa/callback/{SECRET}", json=_cb(checkout, amount=1))
    assert (await _status(client, token, checkout))["status"] == "needs_review"
    assert await _balance(wallet) == Decimal("0")


async def test_status_is_private_to_owner(client: AsyncClient, monkeypatch):
    _, _, token = await register_user_and_wallet(client, "+254799900604")
    _, _, other = await register_user_and_wallet(client, "+254799900605")
    checkout = await _start(client, monkeypatch, token)
    r = await client.get(f"/mpesa/status/{checkout}", headers=_bearer(other))
    assert r.status_code == 404
