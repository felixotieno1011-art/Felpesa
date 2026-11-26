"""payment_attempts table: renamed columns map correctly, defaults apply."""
from decimal import Decimal
import uuid

from sqlalchemy import text

from app.core.db import SessionLocal
from app.models import MpesaRequest
from tests.conftest import register_user_and_wallet


async def test_defaults_and_column_mapping(client):
    uid, wid, _ = await register_user_and_wallet(client, "+254799901500")
    async with SessionLocal() as db:
        db.add(MpesaRequest(user_id=uuid.UUID(uid), wallet_id=uuid.UUID(wid),
                            phone="+254708374149", amount=Decimal("10"),
                            checkout_request_id="ws_CO_mapping_test"))
        await db.commit()
        row = (await db.execute(text(
            "select provider, kind, provider_ref from payment_attempts "
            "where provider_ref = 'ws_CO_mapping_test'"))).one()
    assert tuple(row) == ("daraja", "collection", "ws_CO_mapping_test")
