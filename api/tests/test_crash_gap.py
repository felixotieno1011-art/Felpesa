"""Crash gap: a debited withdrawal with no attempt is sent exactly once, never twice."""
import asyncio
import uuid
from decimal import Decimal

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import MpesaRequest, Transaction
from app.payments.adapters.mock_adapter import MockProvider
from app.services import payment_recon_service as recon
from app.services import withdrawal_service
from tests.test_payment_recon import _pending_withdrawal
from tests.test_withdrawal_flow import _bal, _status


def _mock(monkeypatch, behavior="accept"):
    monkeypatch.setattr(get_settings(), "payment_provider", "mock")
    monkeypatch.setattr(MockProvider, "payout_behavior", behavior)
    calls = []
    orig = MockProvider.initiate_payout

    async def counted(self, req):
        calls.append(req.reference)
        return await orig(self, req)

    monkeypatch.setattr(MockProvider, "initiate_payout", counted)
    return calls


async def _retry(txn_id):
    async with SessionLocal() as db:
        return await withdrawal_service.retry_unsent_withdrawal(db, txn_id)


async def _attempts(txn_id) -> int:
    async with SessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(MpesaRequest).where(
            MpesaRequest.transaction_id == txn_id, MpesaRequest.kind == "payout"))


async def test_retry_sends_once_and_never_duplicates(client, monkeypatch):
    calls = _mock(monkeypatch)
    uid, w, txn_id = await _pending_withdrawal(client, "+254799901900")
    assert await _retry(txn_id) == "sent"
    assert await _retry(txn_id) == "skipped"
    assert len(calls) == 1 and await _attempts(txn_id) == 1
    assert await _status(str(txn_id)) == "pending"
    assert await _bal(w) == Decimal("450.0000")


async def test_retry_rejected_payout_is_reversed(client, monkeypatch):
    _mock(monkeypatch, "reject")
    uid, w, txn_id = await _pending_withdrawal(client, "+254799901901")
    assert await _retry(txn_id) == "sent"
    assert await _status(str(txn_id)) == "reversed"
    assert await _bal(w) == Decimal("500.0000")
    assert await _retry(txn_id) == "skipped"
    assert await _bal(w) == Decimal("500.0000")


async def test_two_concurrent_retries_send_once(client, monkeypatch):
    calls = _mock(monkeypatch)
    uid, w, txn_id = await _pending_withdrawal(client, "+254799901902")
    results = await asyncio.gather(_retry(txn_id), _retry(txn_id))
    assert sorted(results) == ["sent", "skipped"], results
    assert len(calls) == 1 and await _attempts(txn_id) == 1


async def test_reconciliation_run_retries_unsent(client, monkeypatch):
    calls = _mock(monkeypatch)
    uid, w, txn_id = await _pending_withdrawal(client, "+254799901903")
    async with SessionLocal() as db:
        out = await recon.run_reconciliation(db, min_age_seconds=-60)
    assert str(txn_id) in out["withdrawals_without_payout"]
    assert out["withdrawals_retried"].get("sent", 0) >= 1
    assert len(calls) >= 1 and await _attempts(txn_id) == 1
