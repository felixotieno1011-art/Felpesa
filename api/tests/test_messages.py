"""Confirmation message tests."""
import uuid

from httpx import AsyncClient

from tests.conftest import fund_wallet, register_user_and_wallet
from tests.test_payments import make_merchant


async def test_paybill_message_and_type_filter(client: AsyncClient):
    await make_merchant(client, "+254799900320", "paybill", "770010")
    _, u_wallet, token = await register_user_and_wallet(client, "+254799900321")
    await fund_wallet(u_wallet, "1000.0000")
    h = {"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())}

    r = await client.post(
        "/payments/paybill",
        headers=h,
        json={"number": "770010", "account_ref": "ACC1", "amount": "250.0000", "currency": "KES"},
    )
    assert r.status_code == 201, r.text
    msg = r.json()["message"]
    assert "Confirmed. Ksh250.00 paid to" in msg
    assert "Test Merchant acc ACC1" in msg
    assert "New balance Ksh750.00" in msg

    r2 = await client.get(
        "/transactions?type=paybill", headers={"Authorization": f"Bearer {token}"}
    )
    assert r2.status_code == 200, r2.text
    items = r2.json()["items"]
    assert len(items) == 1
    assert items[0]["message"] == msg
