"""add mpesa_requests

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mpesa_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone", sa.String(length=15), nullable=False),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("checkout_request_id", sa.String(length=64), nullable=False),
        sa.Column("merchant_request_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=15), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("result_code", sa.Integer(), nullable=True),
        sa.Column("result_desc", sa.String(length=255), nullable=True),
        sa.Column("mpesa_receipt", sa.String(length=20), nullable=True),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checkout_request_id", name="uq_mpesa_requests_checkout"),
    )
    op.create_index("ix_mpesa_requests_user_id", "mpesa_requests", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mpesa_requests_user_id", table_name="mpesa_requests")
    op.drop_table("mpesa_requests")
