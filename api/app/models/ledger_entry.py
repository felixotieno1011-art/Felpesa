import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class LedgerEntry(Base, TimestampMixin):
    """One side of a double-entry bookkeeping transaction.

    Every Transaction has >= 1 debit and >= 1 credit; all entries for a
    Transaction must sum to zero (debits == credits). Enforced in the
    transfer service and verified by /reconciliation.
    """
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_ledger_entries_amount_positive"),
        Index("ix_ledger_entries_wallet_created", "wallet_id", "created_at"),
        Index("ix_ledger_entries_transaction", "transaction_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(String(6), nullable=False)  # 'debit' | 'credit'
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)

    transaction: Mapped["Transaction"] = relationship(back_populates="ledger_entries")  # noqa: F821

    # Override created_at from TimestampMixin to use clock_timestamp() instead
    # of now(). See migration 0004 for rationale.
    created_at: Mapped["datetime"] = mapped_column(  # type: ignore[assignment]
        DateTime(timezone=True),
        server_default=text("clock_timestamp()"),
        nullable=False,
    )
