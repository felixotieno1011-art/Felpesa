import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import Paginated


class TransferRequest(BaseModel):
    """Input shape for POST /transfers (Session 6 implements the handler)."""
    to_wallet_id: uuid.UUID
    amount: Decimal = Field(..., gt=0, max_digits=19, decimal_places=4)
    currency: str = Field(..., min_length=3, max_length=3)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        v = v.upper()
        if v != "KES":
            # v1 is KES-only. If the user passes "USD", fail clearly,
            # not with a confusing FK violation later.
            raise ValueError("only KES is supported in v1")
        return v


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    status: str
    amount: Decimal
    currency: str
    from_wallet_id: uuid.UUID | None
    to_wallet_id: uuid.UUID | None
    initiated_by: uuid.UUID
    description: str | None
    flagged_fraud: bool
    fraud_reason: str | None
    created_at: datetime
    completed_at: datetime | None
    message: str | None = None


class TransactionListResponse(Paginated[TransactionOut]):
    """Paginated transaction list. `items` + `meta` (total/limit/offset)."""
    pass


class TransactionFilter(BaseModel):
    """Query-string filters for GET /transactions. All optional."""
    type: Literal["transfer", "deposit", "withdrawal", "paybill", "buygoods", "airtime"] | None = None
    status: Literal["pending", "completed", "failed", "reversed"] | None = None
    direction: Literal["in", "out"] | None = None  # in=incoming, out=outgoing
    flagged_fraud: bool | None = None
