"""Ledger endpoint tests: own-wallet access, foreign-wallet 403, pagination."""
from httpx import AsyncClient

from tests.conftest import register_and_login


async def test_ledger_own_wallet_accessible(client: AsyncClient):
    wallet_id, token = await register_and_login(client, "+254799900200")
    r = await client.get(
        f"/ledger/{wallet_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["meta"]["total"] == 0


async def test_ledger_other_wallet_returns_403(client: AsyncClient):
    _, token_a = await register_and_login(client, "+254799900201")
    wallet_b, _ = await register_and_login(client, "+254799900202")
    r = await client.get(
        f"/ledger/{wallet_b}", headers={"Authorization": f"Bearer {token_a}"}
    )
    assert r.status_code == 403
