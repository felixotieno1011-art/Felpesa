import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MpesaRequest(Base):
    """One STK push top-up attempt. Credited to the wallet only on a verified callback."""

    __tablename__ = "mpesa_requests"
    __table_args__ = (
        UniqueConstraint("checkout_request_id", name="uq_mpesa_requests_checkout"),
        Index("ix_mpesa_requests_user_id", "user_id"),
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
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    checkout_request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    merchant_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # pending | completed | cancelled | failed | needs_review
    status: Mapped[str] = mapped_column(
        String(15), nullable=False, default="pending", server_default=text("'pending'")
    )
    result_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_desc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mpesa_receipt: Mapped[str | None] = mapped_column(String(20), nullable=True)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
