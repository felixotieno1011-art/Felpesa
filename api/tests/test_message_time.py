"""Confirmation messages use Nairobi time (UTC+3)."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.services.message_service import _text


def test_message_uses_nairobi_time():
    t = SimpleNamespace(
        id=uuid.uuid4(), type="deposit", amount=Decimal("100"), description=None,
        created_at=datetime(2026, 11, 25, 4, 54, tzinfo=timezone.utc),
        from_wallet_id=None, to_wallet_id=None,
    )
    msg = _text(t, uuid.uuid4(), Decimal("445"))
    assert "25/11/26 at 07:54 AM" in msg
