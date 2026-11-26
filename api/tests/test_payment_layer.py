"""Provider layer: registry and Daraja adapter mapping."""
from decimal import Decimal

import pytest

from app.payments.interfaces import CollectionRequest, PayoutRequest
from app.payments.registry import UnknownProvider, get_provider
from app.services import daraja


def test_registry_returns_daraja_and_rejects_unknown():
    assert get_provider().name == "daraja"
    with pytest.raises(UnknownProvider):
        get_provider("nope")


async def test_collection_accepted_and_rejected(monkeypatch):
    async def ok(**kw):
        assert kw["phone"] == "254708374149" and kw["amount"] == 10
        return {"ResponseCode": "0", "CheckoutRequestID": "ck1", "MerchantRequestID": "mr1"}

    monkeypatch.setattr(daraja, "stk_push", ok)
    req = CollectionRequest("+254708374149", Decimal("10"), "REF", "desc", "https://x.test/cb")
    r = await get_provider().initiate_collection(req)
    assert r.accepted and r.provider_ref == "ck1" and r.secondary_ref == "mr1"

    async def no(**kw):
        return {"ResponseCode": "1", "ResponseDescription": "refused"}

    monkeypatch.setattr(daraja, "stk_push", no)
    r = await get_provider().initiate_collection(req)
    assert not r.accepted and r.message == "refused"


async def test_query_status_mapping(monkeypatch):
    for body, want in [({"ResultCode": "0"}, "paid"),
                       ({"ResultCode": "1032"}, "failed"),
                       ({"errorCode": "x"}, "pending")]:
        async def q(_ref, body=body):
            return body
        monkeypatch.setattr(daraja, "stk_query", q)
        assert await get_provider().query_status("ck") == want


async def test_payout_not_supported_yet():
    with pytest.raises(NotImplementedError):
        await get_provider().initiate_payout(PayoutRequest("+254708374149", Decimal("5"), "r"))
