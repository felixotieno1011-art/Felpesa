import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Paginated


class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_id: uuid.UUID
    wallet_id: uuid.UUID
    direction: str  # 'debit' | 'credit'
    amount: Decimal
    balance_after: Decimal
    created_at: datetime


class LedgerListResponse(Paginated[LedgerEntryOut]):
    pass
