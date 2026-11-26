"""Reconciliation: acts only on explicit provider answers, never twice."""
import uuid
from decimal import Decimal

from sqlalchemy import select, update

from app.core.db import SessionLocal
from app.models import MpesaRequest, User, Wallet
from app.payments.adapters.mock_adapter import MockProvider
from app.services import daraja, deposit_service
from app.services import payment_recon_service as recon
from tests.conftest import fund_wallet, register_user_and_wallet
from tests.test_withdrawal_flow import _attempt, _bal, _setup, _status

STUCK = "Callback not confirmed by Safaricom query"


async def _make(uid, wid, **kw) -> uuid.UUID:
    async with SessionLocal() as db:
        a = MpesaRequest(user_id=uuid.UUID(uid), wallet_id=uuid.UUID(wid),
                         phone="+254708374149", amount=Decimal("100"),
                         checkout_request_id="ws_CO_recon_" + uuid.uuid4().hex[:12], **kw)
        db.add(a)
        await db.commit()
        return a.id


async def _run(fn, *a, **k):
    async with SessionLocal() as db:
        return await fn(db, *a, **k)


async def _att_status(aid) -> str:
    async with SessionLocal() as db:
        return (await db.get(MpesaRequest, aid)).status


def _query(monkeypatch, body):
    async def q(_ref):
        return body
    monkeypatch.setattr(daraja, "stk_query", q)


async def test_paid_collection_credited_once(client, monkeypatch):
    uid, w, _ = await register_user_and_wallet(client, "+254799901700")
    aid = await _make(uid, w, status="needs_review", result_desc=STUCK)
    _query(monkeypatch, {"ResultCode": "0"})
    assert await _run(recon.reconcile_collection, aid) == "credited"
    assert await _run(recon.reconcile_collection, aid) == "skipped"
    assert await _bal(w) == Decimal("100.0000")
    assert await _att_status(aid) == "completed"


async def test_failed_collection_marked_failed(client, monkeypatch):
    uid, w, _ = await register_user_and_wallet(client, "+254799901701")
    aid = await _make(uid, w, status="pending")
    _query(monkeypatch, {"ResultCode": "1032"})
    assert await _run(recon.reconcile_collection, aid) == "failed"
    assert await _att_status(aid) == "failed"
    assert await _bal(w) == Decimal("0")


async def test_pending_collection_left_alone(client, monkeypatch):
    uid, w, _ = await register_user_and_wallet(client, "+254799901702")
    aid = await _make(uid, w, status="pending")
    _query(monkeypatch, {"errorCode": "x"})
    assert await _run(recon.reconcile_collection, aid) == "pending"
    assert await _att_status(aid) == "pending"


async def test_amount_mismatch_is_manual_not_credited(client, monkeypatch):
    uid, w, _ = await register_user_and_wallet(client, "+254799901703")
    aid = await _make(uid, w, status="needs_review", result_desc="Amount mismatch: paid 1, expected 100")
    _query(monkeypatch, {"ResultCode": "0"})
    assert await _run(recon.reconcile_collection, aid) == "manual"
    assert await _bal(w) == Decimal("0")


async def _timeout_withdrawal(client, monkeypatch, phone):
    w, token = await _setup(client, monkeypatch, phone, "timeout")
    r = await client.post("/withdrawals", json={"amount": 100, "currency": "KES"},
                          headers={"Authorization": f"Bearer {token}",
                                   "Idempotency-Key": str(uuid.uuid4())})
    assert r.status_code == 201, r.text
    att = await _attempt(r.json()["id"])
    assert att.status == "needs_review"
    return w, r.json()["id"], att.id


async def test_payout_paid_confirms(client, monkeypatch):
    w, txn, aid = await _timeout_withdrawal(client, monkeypatch, "+254799901704")
    monkeypatch.setattr(MockProvider, "payout_status", "paid")
    assert await _run(recon.reconcile_payout, aid) == "confirmed"
    assert await _status(txn) == "completed"
    assert await _bal(w) == Decimal("400.0000")


async def test_payout_failed_reverses_once(client, monkeypatch):
    w, txn, aid = await _timeout_withdrawal(client, monkeypatch, "+254799901705")
    monkeypatch.setattr(MockProvider, "payout_status", "failed")
    assert await _run(recon.reconcile_payout, aid) == "reversed"
    assert await _run(recon.reconcile_payout, aid) == "skipped"
    assert await _status(txn) == "reversed"
    assert await _bal(w) == Decimal("500.0000")


async def test_payout_pending_stays_held(client, monkeypatch):
    w, txn, aid = await _timeout_withdrawal(client, monkeypatch, "+254799901706")
    monkeypatch.setattr(MockProvider, "payout_status", "pending")
    assert await _run(recon.reconcile_payout, aid) == "pending"
    assert await _status(txn) == "pending"
    assert await _bal(w) == Decimal("400.0000")


async def _pending_withdrawal(client, phone):
    uid, w, _ = await register_user_and_wallet(client, phone)
    await fund_wallet(w, "500.0000")
    async with SessionLocal() as db:
        txn = await deposit_service.withdraw(
            db, user_id=uuid.UUID(uid), from_wallet_id=uuid.UUID(w), amount=Decimal("50"),
            currency="KES", idempotency_key=str(uuid.uuid4()), pending=True)
        return uid, w, txn.id


async def test_provider_without_payout_lookup_is_manual(client):
    uid, w, txn_id = await _pending_withdrawal(client, "+254799901707")
    async with SessionLocal() as db:
        a = MpesaRequest(user_id=uuid.UUID(uid), wallet_id=uuid.UUID(w), provider="daraja",
                         kind="payout", phone="+254708374149", amount=Decimal("50"),
                         transaction_id=txn_id, status="needs_review")
        db.add(a)
        await db.commit()
        aid = a.id
    assert await _run(recon.reconcile_payout, aid) == "manual"
    assert await _att_status(aid) == "needs_review"
    assert await _bal(w) == Decimal("450.0000")


async def test_crash_gap_is_reported_not_acted_on(client):
    uid, w, txn_id = await _pending_withdrawal(client, "+254799901708")
    # negative age puts the cutoff in the future, so a fresh row counts as old
    ids = await _run(recon.find_unattempted_withdrawals, -60)
    assert str(txn_id) in ids
    assert await _bal(w) == Decimal("450.0000")


async def test_admin_endpoint_requires_admin(client, monkeypatch):
    uid, _, token = await register_user_and_wallet(client, "+254799901709")
    h = {"Authorization": f"Bearer {token}"}
    assert (await client.post("/admin/reconcile-payments", headers=h)).status_code == 403

    async def stub(db, min_age_seconds=300):
        return {"checked": 0}

    monkeypatch.setattr("app.routers.admin.run_reconciliation", stub)
    async with SessionLocal() as db:
        await db.execute(update(User).where(User.id == uuid.UUID(uid)).values(role="admin"))
        await db.commit()
    r = await client.post("/admin/reconcile-payments", headers=h)
    assert r.status_code == 200 and r.json() == {"checked": 0}
