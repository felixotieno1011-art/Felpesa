"""Transactions list/get tests. Empty DB at this point — Session 6 adds transfers."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.main import app
from tests.conftest import register_and_login
from app.models import User, Wallet




async def _register_and_token(client, phone: str) -> str:
    await client.post(
        "/auth/register",
        json={"phone": phone, "full_name": "Tx Test", "password": "hunter2hunter2"},
    )
    r = await client.post(
        "/auth/login", json={"phone": phone, "password": "hunter2hunter2"}
    )
    return r.json()["access_token"]


async def test_transactions_empty_list(client, cleanup_users):
    token = await _register_and_token(client, "+254799900010")
    r = await client.get(
        "/transactions", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"] == []
    assert body["meta"] == {"total": 0, "limit": 20, "offset": 0}


async def test_transaction_get_not_found(client, cleanup_users):
    token = await _register_and_token(client, "+254799900011")
    r = await client.get(
        f"/transactions/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


async def test_invalid_filter_returns_422(client: AsyncClient):
    """Bad ?type= value must return 422, not 500."""
    _, token = await register_and_login(client, "+254799900900")
    r = await client.get(
        "/transactions?type=foo",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
