"""Import every model here so Base.metadata sees all tables.

Alembic's autogenerate uses Base.metadata to diff against the live DB;
if a model isn't imported by the time env.py runs, its table is invisible
to autogenerate and won't be created. This file is load-bearing.
"""
from app.models.audit_log import AuditLog
from app.models.base import Base, TimestampMixin
from app.models.ledger_entry import LedgerEntry
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet

__all__ = [
    "AuditLog",
    "Base",
    "LedgerEntry",
    "TimestampMixin",
    "Transaction",
    "User",
    "Wallet",
]
from app.models.merchant import Merchant  # noqa: F401
from app.models.mpesa_request import MpesaRequest  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.notification import Notification  # noqa: F401
