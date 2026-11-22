import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class LedgerAnomaly(BaseModel):
    """A transaction whose ledger entries do NOT sum to zero."""
    transaction_id: uuid.UUID
    debit_total: Decimal
    credit_total: Decimal
    difference: Decimal


class WalletAnomaly(BaseModel):
    """A wallet whose cached balance != its ledger sum."""
    wallet_id: uuid.UUID
    cached_balance: Decimal
    ledger_balance: Decimal
    difference: Decimal


class ReconciliationReport(BaseModel):
    ok: bool
    checked_transactions: int
    checked_wallets: int
    unbalanced_transactions: list[LedgerAnomaly]
    wallet_mismatches: list[WalletAnomaly]
    checked_at: datetime
