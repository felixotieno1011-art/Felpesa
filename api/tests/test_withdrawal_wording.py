"""Pending withdrawals are not described as already paid out."""
from tests.test_withdrawal_flow import _attempt, _h, _settle, _setup


async def _titles(client, token):
    r = await client.get("/notifications", headers={"Authorization": f"Bearer {token}"})
    return [n["title"] for n in r.json()["items"]]


async def test_pending_then_confirmed_wording(client, monkeypatch):
    _, token = await _setup(client, monkeypatch, "+254799901800")
    r = await client.post("/withdrawals", headers=_h(token), json={"amount": 100, "currency": "KES"})
    assert r.status_code == 201 and r.json()["status"] == "pending", r.text

    titles = await _titles(client, token)
    assert "Withdrawal processing" in titles and "Withdrawal" not in titles

    t = await client.get(f"/transactions/{r.json()['id']}",
                         headers={"Authorization": f"Bearer {token}"})
    assert "being processed" in t.json()["message"]

    att = await _attempt(r.json()["id"])
    await _settle(att.id, True)
    assert "Withdrawal sent" in await _titles(client, token)
