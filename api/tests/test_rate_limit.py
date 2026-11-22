"""Rate limit tests: exceeding limit returns 429 with Retry-After header."""
import uuid

import pytest
from httpx import AsyncClient

from app.core.redis import get_redis_client
from tests.conftest import fund_wallet, register_user_and_wallet


@pytest.fixture(autouse=True)
async def flush_rate_limits():
    """Clear all rate-limit keys before/after each test to prevent bleed."""
    redis = get_redis_client()
    async for key in redis.scan_iter(match="ratelimit:*"):
        await redis.delete(key)
    yield
    async for key in redis.scan_iter(match="ratelimit:*"):
        await redis.delete(key)


async def test_transfer_rate_limit_hits_429(client: AsyncClient):
    _, a_wallet, token = await register_user_and_wallet(client, "+254799900500")
    _, b_wallet, _ = await register_user_and_wallet(client, "+254799900501")
    await fund_wallet(a_wallet, "1000.0000")

    # 5 transfers pass (default limit is 5/min)
    for i in range(5):
        r = await client.post(
            "/transfers",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": str(uuid.uuid4()),
            },
            json={"to_wallet_id": b_wallet, "amount": "10.0000", "currency": "KES"},
        )
        assert r.status_code == 201, f"transfer {i+1} failed: {r.status_code} {r.text}"

    # 6th should be rate limited
    r = await client.post(
        "/transfers",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={"to_wallet_id": b_wallet, "amount": "10.0000", "currency": "KES"},
    )
    assert r.status_code == 429, f"expected 429, got {r.status_code}: {r.text}"
    assert "Retry-After" in r.headers
    assert int(r.headers["Retry-After"]) >= 1


async def test_rate_limit_per_user_isolated(client: AsyncClient):
    """Different users have independent counters."""
    _, a_wallet, token_a = await register_user_and_wallet(client, "+254799900502")
    _, b_wallet, token_b = await register_user_and_wallet(client, "+254799900503")
    _, c_wallet, _ = await register_user_and_wallet(client, "+254799900504")
    await fund_wallet(a_wallet, "1000.0000")
    await fund_wallet(b_wallet, "1000.0000")

    # User A hits limit
    for _ in range(5):
        await client.post(
            "/transfers",
            headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": str(uuid.uuid4())},
            json={"to_wallet_id": c_wallet, "amount": "1.0000", "currency": "KES"},
        )
    r = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": str(uuid.uuid4())},
        json={"to_wallet_id": c_wallet, "amount": "1.0000", "currency": "KES"},
    )
    assert r.status_code == 429

    # User B is unaffected
    r = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {token_b}", "Idempotency-Key": str(uuid.uuid4())},
        json={"to_wallet_id": c_wallet, "amount": "1.0000", "currency": "KES"},
    )
    assert r.status_code == 201, r.text
