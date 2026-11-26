"""Inbox: created with the money movement, private, soft-deletable."""
import uuid

from tests.conftest import fund_wallet, register_user_and_wallet


def _b(t):
    return {"Authorization": f"Bearer {t}"}


async def _send(client, token, to, amt="100.0000"):
    r = await client.post(
        "/transfers",
        headers={**_b(token), "Idempotency-Key": str(uuid.uuid4())},
        json={"to_wallet_id": to, "amount": amt, "currency": "KES"},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _inbox(client, token):
    r = await client.get("/notifications", headers=_b(token))
    assert r.status_code == 200, r.text
    return r.json()


async def test_transfer_notifies_sender_and_receiver(client):
    _, a, ta = await register_user_and_wallet(client, "+254799901000")
    _, b, tb = await register_user_and_wallet(client, "+254799901001")
    await fund_wallet(a, "1000.0000")
    txn = await _send(client, ta, b)

    sent = [n for n in (await _inbox(client, ta))["items"] if n["kind"] == "sent"]
    got = await _inbox(client, tb)
    recv = [n for n in got["items"] if n["kind"] == "received"]
    assert len(sent) == 1 and sent[0]["transaction_id"] == txn["id"]
    assert len(recv) == 1 and "received" in recv[0]["body"]
    assert got["unread"] == 1


async def test_read_and_read_all(client):
    _, a, ta = await register_user_and_wallet(client, "+254799901002")
    _, b, tb = await register_user_and_wallet(client, "+254799901003")
    await fund_wallet(a, "1000.0000")
    await _send(client, ta, b)
    await _send(client, ta, b)
    items = (await _inbox(client, tb))["items"]
    assert len(items) == 2
    r = await client.post(f"/notifications/{items[0]['id']}/read", headers=_b(tb))
    assert r.status_code == 200
    assert (await _inbox(client, tb))["unread"] == 1
    await client.post("/notifications/read-all", headers=_b(tb))
    assert (await client.get("/notifications/unread-count", headers=_b(tb))).json() == {"unread": 0}


async def test_delete_hides_message_only(client):
    _, a, ta = await register_user_and_wallet(client, "+254799901004")
    _, b, tb = await register_user_and_wallet(client, "+254799901005")
    await fund_wallet(a, "1000.0000")
    txn = await _send(client, ta, b)
    nid = (await _inbox(client, tb))["items"][0]["id"]

    assert (await client.delete(f"/notifications/{nid}", headers=_b(tb))).status_code == 200
    assert (await _inbox(client, tb))["items"] == []
    # the transaction itself is untouched
    r = await client.get(f"/transactions/{txn['id']}", headers=_b(tb))
    assert r.status_code == 200 and r.json()["status"] == "completed"


async def test_cannot_touch_someone_elses_message(client):
    _, a, ta = await register_user_and_wallet(client, "+254799901006")
    _, b, tb = await register_user_and_wallet(client, "+254799901007")
    await fund_wallet(a, "1000.0000")
    await _send(client, ta, b)
    nid = (await _inbox(client, tb))["items"][0]["id"]
    assert (await client.delete(f"/notifications/{nid}", headers=_b(ta))).status_code == 404
    assert (await client.post(f"/notifications/{nid}/read", headers=_b(ta))).status_code == 404
