"""Pay bill / buy goods tests."""
import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import LedgerEntry, Merchant, Transaction, Wallet
from tests.conftest import fund_wallet, register_user_and_wallet


async def make_merchant(client: AsyncClient, phone: str, kind: str, number: str) -> str:
    _, wallet_id, _ = await register_user_and_wallet(client, phone)
    async with SessionLocal() as db:
        db.add(
            Merchant(
                kind=kind,
                number=number,
                name="Test Merchant",
                wallet_id=uuid.UUID(wallet_id),
            )
        )
        await db.commit()
    return wallet_id


def _headers(token: str, key: str | None = None) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": key or str(uuid.uuid4()),
    }


async def test_paybill_happy_path(client: AsyncClient):
    m_wallet = await make_merchant(client, "+254799900300", "paybill", "770001")
    _, u_wallet, token = await register_user_and_wallet(client, "+254799900301")
    await fund_wallet(u_wallet, "1000.0000")

    r = await client.post(
        "/payments/paybill",
        headers=_headers(token),
        json={"number": "770001", "account_ref": "ACC123", "amount": "300.0000", "currency": "KES"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "completed"

    async with SessionLocal() as db:
        u = await db.get(Wallet, uuid.UUID(u_wallet))
        m = await db.get(Wallet, uuid.UUID(m_wallet))
        assert u.balance == Decimal("700.0000")
        assert m.balance == Decimal("300.0000")
        txn = await db.scalar(select(Transaction).where(Transaction.id == uuid.UUID(r.json()["id"])))
        assert txn.type == "paybill"
        assert "ACC123" in txn.description


async def test_till_happy_path(client: AsyncClient):
    m_wallet = await make_merchant(client, "+254799900302", "buygoods", "770002")
    _, u_wallet, token = await register_user_and_wallet(client, "+254799900303")
    await fund_wallet(u_wallet, "500.0000")

    r = await client.post(
        "/payments/till",
        headers=_headers(token),
        json={"number": "770002", "amount": "120.0000", "currency": "KES"},
    )
    assert r.status_code == 201, r.text

    async with SessionLocal() as db:
        u = await db.get(Wallet, uuid.UUID(u_wallet))
        m = await db.get(Wallet, uuid.UUID(m_wallet))
        assert u.balance == Decimal("380.0000")
        assert m.balance == Decimal("120.0000")
        txn = await db.scalar(select(Transaction).where(Transaction.id == uuid.UUID(r.json()["id"])))
        assert txn.type == "buygoods"


async def test_payment_insufficient_funds(client: AsyncClient):
    await make_merchant(client, "+254799900304", "buygoods", "770003")
    _, u_wallet, token = await register_user_and_wallet(client, "+254799900305")
    await fund_wallet(u_wallet, "50.0000")

    r = await client.post(
        "/payments/till",
        headers=_headers(token),
        json={"number": "770003", "amount": "100.0000", "currency": "KES"},
    )
    assert r.status_code == 422
    assert r.json()["detail"] == "Insufficient funds"


async def test_payment_unknown_merchant(client: AsyncClient):
    _, u_wallet, token = await register_user_and_wallet(client, "+254799900306")
    await fund_wallet(u_wallet, "500.0000")

    r = await client.post(
        "/payments/till",
        headers=_headers(token),
        json={"number": "770999", "amount": "10.0000", "currency": "KES"},
    )
    assert r.status_code == 404


async def test_paybill_requires_account_ref(client: AsyncClient):
    await make_merchant(client, "+254799900307", "paybill", "770004")
    _, u_wallet, token = await register_user_and_wallet(client, "+254799900308")
    await fund_wallet(u_wallet, "500.0000")

    r = await client.post(
        "/payments/paybill",
        headers=_headers(token),
        json={"number": "770004", "amount": "10.0000", "currency": "KES"},
    )
    assert r.status_code == 422


async def test_payment_idempotent_replay(client: AsyncClient):
    m_wallet = await make_merchant(client, "+254799900309", "buygoods", "770005")
    _, u_wallet, token = await register_user_and_wallet(client, "+254799900310")
    await fund_wallet(u_wallet, "1000.0000")
    key = str(uuid.uuid4())
    body = {"number": "770005", "amount": "200.0000", "currency": "KES"}

    r1 = await client.post("/payments/till", headers=_headers(token, key), json=body)
    r2 = await client.post("/payments/till", headers=_headers(token, key), json=body)
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]

    async with SessionLocal() as db:
        u = await db.get(Wallet, uuid.UUID(u_wallet))
        m = await db.get(Wallet, uuid.UUID(m_wallet))
        assert u.balance == Decimal("800.0000")
        assert m.balance == Decimal("200.0000")


async def test_payment_ledger_balances_to_zero(client: AsyncClient):
    await make_merchant(client, "+254799900311", "paybill", "770006")
    _, u_wallet, token = await register_user_and_wallet(client, "+254799900312")
    await fund_wallet(u_wallet, "1000.0000")

    r = await client.post(
        "/payments/paybill",
        headers=_headers(token),
        json={"number": "770006", "account_ref": "X1", "amount": "250.0000", "currency": "KES"},
    )
    assert r.status_code == 201, r.text

    async with SessionLocal() as db:
        entries = (
            await db.scalars(
                select(LedgerEntry).where(LedgerEntry.transaction_id == uuid.UUID(r.json()["id"]))
            )
        ).all()
        assert len(entries) == 2
        debit = sum(e.amount for e in entries if e.direction == "debit")
        credit = sum(e.amount for e in entries if e.direction == "credit")
        assert debit == credit == Decimal("250.0000")
