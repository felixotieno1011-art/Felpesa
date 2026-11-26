"""Uncertain STK outcomes are kept for review; Redis errors give 503."""
import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import MpesaRequest
from app.services import daraja
from tests.conftest import register_user_and_wallet


async def _setup(client, monkeypatch, phone, push):
    _, _, token = await register_user_and_wallet(client, phone)
    s = get_settings()
    monkeypatch.setattr(daraja, "stk_push", push)
    monkeypatch.setattr(daraja, "is_configured", lambda: True)
    monkeypatch.setattr(s, "mpesa_callback_secret", "x")
    monkeypatch.setattr(s, "mpesa_callback_base_url", "https://example.test")
    return token


async def _status_of_latest() -> str:
    async with SessionLocal() as db:
        r = await db.scalar(select(MpesaRequest).order_by(MpesaRequest.created_at.desc()).limit(1))
        return r.status


async def test_timeout_is_needs_review(client, monkeypatch):
    async def timeout(**kw):
        raise httpx.ReadTimeout("slow")

    token = await _setup(client, monkeypatch, "+254799901300", timeout)
    r = await client.post("/mpesa/stk", headers={"Authorization": f"Bearer {token}"},
                          json={"phone": "+254708374149", "amount": 10})
    assert r.status_code == 502
    assert await _status_of_latest() == "needs_review"


async def test_clear_rejection_is_failed(client, monkeypatch):
    async def refused(**kw):
        raise daraja.DarajaError("rejected")

    token = await _setup(client, monkeypatch, "+254799901301", refused)
    await client.post("/mpesa/stk", headers={"Authorization": f"Bearer {token}"},
                      json={"phone": "+254708374149", "amount": 10})
    assert await _status_of_latest() == "failed"


async def test_redis_error_gives_503(client, monkeypatch):
    from app.core import auth_limits

    async def boom(*a, **k):
        from redis.exceptions import RedisError
        raise RedisError("down")

    monkeypatch.setattr("app.routers.wallets.check_rate_limit", boom)
    _, _, token = await register_user_and_wallet(client, "+254799901302")
    r = await client.get("/wallets/lookup", params={"phone": "+254799901399"},
                         headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 503
