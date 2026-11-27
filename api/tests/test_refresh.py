"""Refresh tokens: rotate, detect reuse, revoke on logout, hardened cookie."""
from tests.conftest import register_user_and_wallet

C = "felpesa_refresh"


async def _login(client, phone):
    await register_user_and_wallet(client, phone)
    client.cookies.clear()
    r = await client.post("/auth/login", json={"phone": phone, "password": "hunter2hunter2"})
    assert r.status_code == 200, r.text
    return r, r.cookies.get(C)


async def _refresh(client, raw):
    client.cookies.clear()
    headers = {"Cookie": f"{C}={raw}"} if raw else {}
    return await client.post("/auth/refresh", headers=headers)


async def test_login_sets_hardened_cookie(client):
    r, raw = await _login(client, "+254799902000")
    assert raw
    sc = r.headers["set-cookie"].lower()
    assert "httponly" in sc and "samesite=strict" in sc


async def test_refresh_rotates_and_new_access_token_works(client):
    _, raw = await _login(client, "+254799902001")
    r = await _refresh(client, raw)
    assert r.status_code == 200, r.text
    new_raw = r.cookies.get(C)
    assert new_raw and new_raw != raw
    me = await client.get("/wallets/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200
    assert (await _refresh(client, new_raw)).status_code == 200  # the rotated one is valid


async def test_reuse_revokes_whole_session(client):
    _, raw = await _login(client, "+254799902002")
    r1 = await _refresh(client, raw)
    newest = r1.cookies.get(C)
    assert (await _refresh(client, raw)).status_code == 401   # old token replayed
    assert (await _refresh(client, newest)).status_code == 401  # session now dead


async def test_logout_revokes(client):
    _, raw = await _login(client, "+254799902003")
    client.cookies.clear()
    r = await client.post("/auth/logout", headers={"Cookie": f"{C}={raw}"})
    assert r.status_code == 200
    assert (await _refresh(client, raw)).status_code == 401


async def test_missing_or_garbage_cookie_is_401(client):
    assert (await _refresh(client, None)).status_code == 401
    assert (await _refresh(client, "garbage")).status_code == 401
