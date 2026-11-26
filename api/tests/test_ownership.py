"""Services enforce wallet ownership and system-wallet rules themselves."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Wallet
from app.services import deposit_service, transfer_service
from tests.conftest import fund_wallet, register_user_and_wallet


async def test_transfer_to_clearing_wallet_forbidden(client):
    _, a, token = await register_user_and_wallet(client, "+254799900900")
    await fund_wallet(a, "500.0000")
    async with SessionLocal() as db:
        clearing = await db.scalar(select(Wallet).where(Wallet.is_system.is_(True)))
        clearing_id = str(clearing.id)
    r = await client.post(
        "/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
        json={"to_wallet_id": clearing_id, "amount": "10.0000", "currency": "KES"},
    )
    assert r.status_code == 403


async def test_service_rejects_foreign_source_wallet(client):
    uid_a, a, _ = await register_user_and_wallet(client, "+254799900901")
    uid_b, b, _ = await register_user_and_wallet(client, "+254799900902")
    await fund_wallet(a, "500.0000")
    async with SessionLocal() as db:
        with pytest.raises(transfer_service.NotWalletOwner):
            await transfer_service.execute_transfer(
                db, initiated_by=uuid.UUID(uid_b), from_wallet_id=uuid.UUID(a),
                to_wallet_id=uuid.UUID(b), amount=Decimal("10"), currency="KES",
                idempotency_key=str(uuid.uuid4()),
            )
    async with SessionLocal() as db:
        assert (await db.get(Wallet, uuid.UUID(a))).balance == Decimal("500.0000")


async def test_service_rejects_foreign_withdrawal(client):
    uid_a, a, _ = await register_user_and_wallet(client, "+254799900903")
    uid_b, _, _ = await register_user_and_wallet(client, "+254799900904")
    await fund_wallet(a, "500.0000")
    async with SessionLocal() as db:
        with pytest.raises(deposit_service.DepositError):
            await deposit_service.withdraw(
                db, user_id=uuid.UUID(uid_b), from_wallet_id=uuid.UUID(a),
                amount=Decimal("10"), currency="KES", idempotency_key=str(uuid.uuid4()),
            )
