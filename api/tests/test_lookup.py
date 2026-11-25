"""Recipient lookup tests."""
from httpx import AsyncClient

from app.routers.wallets import mask_name
from tests.conftest import register_user_and_wallet


def test_mask_name():
    assert mask_name("Felix Otieno") == "FELIX O***"
    assert mask_name("Amina") == "A***"
    assert mask_name("Mary Wanjiru Kamau") == "MARY K***"


async def test_lookup_found(client: AsyncClient):
    _, _, token = await register_user_and_wallet(client, "+254799900330")
    _, b_wallet, _ = await register_user_and_wallet(client, "+254799900331")

    r = await client.get(
        "/wallets/lookup",
        params={"phone": "+254799900331"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["wallet_id"] == b_wallet
    assert body["name_masked"].endswith("***")


async def test_lookup_not_found(client: AsyncClient):
    _, _, token = await register_user_and_wallet(client, "+254799900332")
    r = await client.get(
        "/wallets/lookup",
        params={"phone": "+254799900399"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


async def test_lookup_requires_auth(client: AsyncClient):
    r = await client.get("/wallets/lookup", params={"phone": "+254799900331"})
    assert r.status_code in (401, 403)
