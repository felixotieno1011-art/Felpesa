"""Thin Daraja (Safaricom) sandbox client. Sandbox only, by design."""
import base64
import time
from datetime import datetime

import httpx

from app.core.config import get_settings

SANDBOX = "https://sandbox.safaricom.co.ke"
_token: tuple[str, float] | None = None


class DarajaError(Exception):
    pass


def is_configured() -> bool:
    s = get_settings()
    return s.mpesa_env == "sandbox" and all(
        [s.mpesa_consumer_key, s.mpesa_consumer_secret, s.mpesa_shortcode,
         s.mpesa_passkey, s.mpesa_callback_base_url, s.mpesa_callback_secret]
    )


async def _get_token(client: httpx.AsyncClient) -> str:
    global _token
    if _token and _token[1] > time.monotonic():
        return _token[0]
    s = get_settings()
    r = await client.get(
        f"{SANDBOX}/oauth/v1/generate",
        params={"grant_type": "client_credentials"},
        auth=(s.mpesa_consumer_key, s.mpesa_consumer_secret),
    )
    if r.status_code != 200:
        raise DarajaError("Could not authenticate with Daraja (check key/secret)")
    data = r.json()
    _token = (data["access_token"], time.monotonic() + int(data.get("expires_in", 3599)) - 60)
    return _token[0]


async def stk_push(*, phone: str, amount: int, reference: str, description: str,
                   callback_url: str) -> dict:
    """phone must be 2547XXXXXXXX (no +). amount must be a whole number."""
    s = get_settings()
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{s.mpesa_shortcode}{s.mpesa_passkey}{ts}".encode()).decode()
    payload = {
        "BusinessShortCode": s.mpesa_shortcode,
        "Password": password,
        "Timestamp": ts,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone,
        "PartyB": s.mpesa_shortcode,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": reference[:12],
        "TransactionDesc": description[:13],
    }
    async with httpx.AsyncClient(timeout=20) as client:
        token = await _get_token(client)
        r = await client.post(
            f"{SANDBOX}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
    try:
        data = r.json()
    except ValueError:
        raise DarajaError(f"Daraja returned HTTP {r.status_code}")
    if r.status_code >= 400:
        raise DarajaError(data.get("errorMessage") or f"Daraja returned HTTP {r.status_code}")
    return data
