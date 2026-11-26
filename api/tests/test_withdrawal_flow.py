"""Provider-backed withdrawals: pending, confirmed, rejected, timeout, no double refund."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import MpesaRequest, Transaction, Wallet
from app.payments.adapters.mock_adapter import MockProvider
from app.payments.registry import UnknownProvider, get_provider
from app.services import withdrawal_service
from tests.conftest import fund_wallet, register_user_and_wallet


def _h(t, key=None):
    return {"Authorization": f"Bearer {t}", "Idempotency-Key": key or str(uuid.uuid4())}


async def _setup(client, monkeypatch, phone, behavior="accept"):
    s = get_settings()
    monkeypatch.setattr(s, "withdrawal_mode", "provider")
    monkeypatch.setattr(s, "payment_provider", "mock")
    monkeypatch.setattr(MockProvider, "payout_behavior", behavior)
    _, w, token = await register_user_and_wallet(client, phone)
    await fund_wallet(w, "500.0000")
    return w, token


async def _bal(w):
    async with SessionLocal() as db:
        return (await db.get(Wallet, uuid.UUID(w))).balance


async def _attempt(txn_id):
    async with SessionLocal() as db:
        return await db.scalar(select(MpesaRequest).where(
            MpesaRequest.transaction_id == uuid.UUID(txn_id), MpesaRequest.kind == "payout"))


async def _settle(att_id, ok):
    async with SessionLocal() as db:
        await withdrawal_service.settle_payout(db, att_id, success=ok, reason="test")


async def _status(txn_id):
    async with SessionLocal() as db:
        return (await db.get(Transaction, uuid.UUID(txn_id))).status


async def test_accepted_stays_pending_until_confirmed(client, monkeypatch):
    w, token = await _setup(client, monkeypatch, "+254799901600")
    key = str(uuid.uuid4())
    body = {"amount": 100, "currency": "KES"}
    r1 = await client.post("/withdrawals", headers=_h(token, key), json=body)
    r2 = await client.post("/withdrawals", headers=_h(token, key), json=body)
    assert r1.status_code == 201 and r1.json()["status"] == "pending", r1.text
    assert r2.json()["id"] == r1.json()["id"]
    assert await _bal(w) == Decimal("400.0000")  # debited once

    att = await _attempt(r1.json()["id"])
    assert att.status == "pending" and att.provider == "mock"
    await _settle(att.id, True)
    assert await _status(r1.json()["id"]) == "completed"
    await _settle(att.id, False)  # late failure must not undo a confirmed payout
    assert await _status(r1.json()["id"]) == "completed"
    assert await _bal(w) == Decimal("400.0000")


async def test_rejected_payout_is_reversed(client, monkeypatch):
    w, token = await _setup(client, monkeypatch, "+254799901601", "reject")
    r = await client.post("/withdrawals", headers=_h(token), json={"amount": 100, "currency": "KES"})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "reversed"
    assert await _bal(w) == Decimal("500.0000")
    async with SessionLocal() as db:
        revs = (await db.scalars(select(Transaction).where(
            Transaction.type == "withdrawal_reversal",
            Transaction.description.like(f"%{r.json()['id']}%")))).all()
    assert len(revs) == 1


async def test_timeout_is_held_then_reversed_once(client, monkeypatch):
    w, token = await _setup(client, monkeypatch, "+254799901602", "timeout")
    r = await client.post("/withdrawals", headers=_h(token), json={"amount": 100, "currency": "KES"})
    assert r.status_code == 201 and r.json()["status"] == "pending"
    att = await _attempt(r.json()["id"])
    assert att.status == "needs_review"
    assert await _bal(w) == Decimal("400.0000")  # held, not refunded

    await _settle(att.id, False)
    await _settle(att.id, False)  # replayed failure
    assert await _status(r.json()["id"]) == "reversed"
    assert await _bal(w) == Decimal("500.0000")  # refunded exactly once


def test_mock_provider_refused_in_prod(monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "prod")
    with pytest.raises(UnknownProvider):
        get_provider("mock")
