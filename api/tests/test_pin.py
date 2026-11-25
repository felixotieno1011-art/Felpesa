"""Transaction PIN tests."""
import uuid
from decimal import Decimal

from httpx import AsyncClient

from app.core.db import SessionLocal
from app.models import Wallet
from tests.conftest import fund_wallet, register_user_and_wallet


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _tx_headers(token: str, pin: str | None = None) -> dict:
    h = {**_bearer(token), "Idempotency-Key": str(uuid.uuid4())}
    if pin:
        h["X-Pin"] = pin
    return h


async def _set(client: AsyncClient, token: str, pin: str, old: str | None = None):
    return await client.post("/pin", headers=_bearer(token), json={"pin": pin, "old_pin": old})


async def _setup(client: AsyncClient, p1: str, p2: str):
    _, a_wallet, token = await register_user_and_wallet(client, p1)
    _, b_wallet, _ = await register_user_and_wallet(client, p2)
    await fund_wallet(a_wallet, "1000.0000")
    return a_wallet, b_wallet, token


def _transfer_body(b_wallet: str) -> dict:
    return {"to_wallet_id": b_wallet, "amount": "100.0000", "currency": "KES"}


async def test_pin_status_and_set(client: AsyncClient):
    _, _, token = await register_user_and_wallet(client, "+254799900400")
    r = await client.get("/pin/status", headers=_bearer(token))
    assert r.json() == {"has_pin": False}
    assert (await _set(client, token, "2468")).status_code == 200
    r = await client.get("/pin/status", headers=_bearer(token))
    assert r.json() == {"has_pin": True}


async def test_weak_pin_rejected(client: AsyncClient):
    _, _, token = await register_user_and_wallet(client, "+254799900401")
    assert (await _set(client, token, "1111")).status_code == 422
    assert (await _set(client, token, "12")).status_code == 422


async def test_transfer_requires_pin(client: AsyncClient):
    _, b_wallet, token = await _setup(client, "+254799900402", "+254799900403")
    assert (await _set(client, token, "2468")).status_code == 200

    r = await client.post("/transfers", headers=_tx_headers(token), json=_transfer_body(b_wallet))
    assert r.status_code == 403 and r.json()["detail"] == "PIN required"

    r = await client.post(
        "/transfers", headers=_tx_headers(token, "2468"), json=_transfer_body(b_wallet)
    )
    assert r.status_code == 201, r.text


async def test_lockout_after_three_wrong_pins(client: AsyncClient):
    a_wallet, b_wallet, token = await _setup(client, "+254799900404", "+254799900405")
    assert (await _set(client, token, "2468")).status_code == 200

    for expected in (403, 403, 429):
        r = await client.post(
            "/transfers", headers=_tx_headers(token, "9999"), json=_transfer_body(b_wallet)
        )
        assert r.status_code == expected, r.text

    # Even the correct PIN is refused while locked.
    r = await client.post(
        "/transfers", headers=_tx_headers(token, "2468"), json=_transfer_body(b_wallet)
    )
    assert r.status_code == 429
    assert "Retry-After" in r.headers

    async with SessionLocal() as db:
        w = await db.get(Wallet, uuid.UUID(a_wallet))
        assert w.balance == Decimal("1000.0000")


async def test_change_pin_requires_old(client: AsyncClient):
    a_wallet, b_wallet, token = await _setup(client, "+254799900406", "+254799900407")
    assert (await _set(client, token, "2468")).status_code == 200

    assert (await _set(client, token, "1357")).status_code == 403          # no old pin
    assert (await _set(client, token, "1357", old="0000")).status_code == 403  # wrong old
    assert (await _set(client, token, "1357", old="2468")).status_code == 200

    r = await client.post(
        "/transfers", headers=_tx_headers(token, "2468"), json=_transfer_body(b_wallet)
    )
    assert r.status_code == 403  # old PIN no longer works
    r = await client.post(
        "/transfers", headers=_tx_headers(token, "1357"), json=_transfer_body(b_wallet)
    )
    assert r.status_code == 201, r.text


async def test_withdrawal_needs_pin_but_deposit_does_not(client: AsyncClient):
    _, _, token = await _setup(client, "+254799900408", "+254799900409")
    assert (await _set(client, token, "2468")).status_code == 200
    body = {"amount": 100, "currency": "KES"}

    r = await client.post("/deposits", headers=_tx_headers(token), json=body)
    assert r.status_code == 201, r.text

    r = await client.post("/withdrawals", headers=_tx_headers(token), json=body)
    assert r.status_code == 403
    r = await client.post("/withdrawals", headers=_tx_headers(token, "2468"), json=body)
    assert r.status_code == 201, r.text
