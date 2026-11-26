"""With REQUIRE_PIN on, a user without a PIN cannot move money but can set one."""
import uuid

from app.core.config import get_settings
from tests.conftest import fund_wallet, register_user_and_wallet


def _h(t, pin=None):
    h = {"Authorization": f"Bearer {t}", "Idempotency-Key": str(uuid.uuid4())}
    if pin:
        h["X-Pin"] = pin
    return h


async def test_no_pin_blocks_money_endpoints(client, monkeypatch):
    _, a, ta = await register_user_and_wallet(client, "+254799901400")
    _, b, _ = await register_user_and_wallet(client, "+254799901401")
    await fund_wallet(a, "1000.0000")
    monkeypatch.setattr(get_settings(), "require_pin", True)

    r = await client.post("/transfers", headers=_h(ta),
                          json={"to_wallet_id": b, "amount": "10.0000", "currency": "KES"})
    assert r.status_code == 403 and r.json()["detail"] == "PIN required"
    r = await client.post("/withdrawals", headers=_h(ta), json={"amount": 10, "currency": "KES"})
    assert r.status_code == 403
    r = await client.post("/airtime", headers=_h(ta),
                          json={"phone": "+254712345678", "amount": "10.0000", "currency": "KES"})
    assert r.status_code == 403
    r = await client.post("/payments/till", headers=_h(ta),
                          json={"number": "770999", "amount": "10.0000", "currency": "KES"})
    assert r.status_code == 403


async def test_can_set_first_pin_then_transact(client, monkeypatch):
    _, a, ta = await register_user_and_wallet(client, "+254799901402")
    _, b, _ = await register_user_and_wallet(client, "+254799901403")
    await fund_wallet(a, "1000.0000")
    monkeypatch.setattr(get_settings(), "require_pin", True)

    r = await client.post("/pin", headers={"Authorization": f"Bearer {ta}"}, json={"pin": "2468"})
    assert r.status_code == 200, r.text
    r = await client.post("/transfers", headers=_h(ta, "2468"),
                          json={"to_wallet_id": b, "amount": "10.0000", "currency": "KES"})
    assert r.status_code == 201, r.text
