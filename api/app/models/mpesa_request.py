import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MpesaRequest(Base):
    """One provider payment attempt (table: payment_attempts).

    The Python attribute names are kept for now; the columns are provider-neutral.
    checkout_request_id -> provider_ref, merchant_request_id -> provider_ref2,
    mpesa_receipt -> provider_receipt.
    """

    __tablename__ = "payment_attempts"
    __table_args__ = (
        UniqueConstraint("provider_ref", name="uq_payment_attempts_provider_ref"),
        Index("ix_payment_attempts_user_id", "user_id"),
        Index("uq_payment_attempts_txn_kind", "transaction_id", "kind", unique=True,
              postgresql_where=text("transaction_id IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default="daraja", server_default=text("'daraja'")
    )
    kind: Mapped[str] = mapped_column(
        String(12), nullable=False, default="collection", server_default=text("'collection'")
    )
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    checkout_request_id: Mapped[str | None] = mapped_column("provider_ref", String(64), nullable=True)
    merchant_request_id: Mapped[str | None] = mapped_column("provider_ref2", String(64), nullable=True)
    # pending | completed | cancelled | failed | needs_review
    status: Mapped[str] = mapped_column(
        String(15), nullable=False, default="pending", server_default=text("'pending'")
    )
    result_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_desc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mpesa_receipt: Mapped[str | None] = mapped_column("provider_receipt", String(20), nullable=True)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
