"""Phase 1 hardening: prod withdrawals off, JWT type enforced."""
import time

from jose import jwt

from app.core.config import get_settings
from tests.conftest import register_user_and_wallet


async def test_withdrawals_disabled_in_prod(client, monkeypatch):
    _, _, token = await register_user_and_wallet(client, "+254799901200")
    monkeypatch.setattr(get_settings(), "app_env", "prod")
    r = await client.post(
        "/withdrawals",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "k-wd-prod-1"},
        json={"amount": 10, "currency": "KES"},
    )
    assert r.status_code == 404


async def test_non_access_token_rejected(client):
    uid, _, _ = await register_user_and_wallet(client, "+254799901201")
    s = get_settings()
    refresh = jwt.encode(
        {"sub": uid, "role": "user", "type": "refresh", "exp": int(time.time()) + 600},
        s.jwt_secret, algorithm=s.jwt_algorithm,
    )
    r = await client.get("/wallets/me", headers={"Authorization": f"Bearer {refresh}"})
    assert r.status_code == 401
