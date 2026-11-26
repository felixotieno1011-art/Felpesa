"""Live hints: published after commit, and the stream needs auth."""
import uuid

from app.core.redis import get_redis_client
from tests.conftest import fund_wallet, register_user_and_wallet


async def test_transfer_publishes_live_event_to_receiver(client):
    _, a, ta = await register_user_and_wallet(client, "+254799901100")
    ub, b, _ = await register_user_and_wallet(client, "+254799901101")
    await fund_wallet(a, "1000.0000")

    ps = get_redis_client().pubsub()
    await ps.subscribe(f"live:{ub}")
    await ps.get_message(timeout=1)  # subscribe confirmation

    r = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {ta}", "Idempotency-Key": str(uuid.uuid4())},
        json={"to_wallet_id": b, "amount": "50.0000", "currency": "KES"},
    )
    assert r.status_code == 201, r.text

    msg = None
    for _ in range(10):
        msg = await ps.get_message(ignore_subscribe_messages=True, timeout=0.5)
        if msg:
            break
    await ps.aclose()
    assert msg is not None and msg["data"] in ("refresh", b"refresh")


async def test_stream_requires_auth(client):
    r = await client.get("/notifications/stream")
    assert r.status_code == 401
