"""Audit log tests: admin-only, records writes, action filter."""
from httpx import AsyncClient

from tests.conftest import fund_wallet, register_and_login


async def test_audit_requires_admin(client: AsyncClient):
    _, token = await register_and_login(client, "+254799900400")
    r = await client.get("/audit", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


async def test_audit_records_register_and_login(client: AsyncClient):
    _, token = await register_and_login(client, "+254799900401", admin=True)
    r = await client.get("/audit", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    actions = [it["action"] for it in items]
    # admin was inserted directly (no auth.register audit for them)
    # but their /auth.login should be there
    assert "auth.login" in actions


async def test_audit_filter_by_action(client: AsyncClient):
    a_wallet, token = await register_and_login(client, "+254799900402")
    b_wallet, _ = await register_and_login(client, "+254799900403")
    await fund_wallet(a_wallet, "1000.0000")

    # Do a transfer — should write transfer.initiated
    r = await client.post(
        "/transfers",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "audit-test-1",
        },
        json={"to_wallet_id": b_wallet, "amount": "50.0000", "currency": "KES"},
    )
    assert r.status_code == 201, r.text

    # Now admin reads filtered by transfer.initiated
    _, admin_token = await register_and_login(client, "+254799900404", admin=True)
    r = await client.get(
        "/audit?action=transfer.initiated",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert all(i["action"] == "transfer.initiated" for i in items)
    # metadata should include the transfer amount
    assert any(i["metadata_json"].get("amount") == "50.0000" for i in items)
