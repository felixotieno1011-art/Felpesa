"""generalise mpesa_requests into payment_attempts

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("mpesa_requests", "payment_attempts")
    op.alter_column("payment_attempts", "checkout_request_id", new_column_name="provider_ref")
    op.alter_column("payment_attempts", "merchant_request_id", new_column_name="provider_ref2")
    op.alter_column("payment_attempts", "mpesa_receipt", new_column_name="provider_receipt")
    op.add_column("payment_attempts", sa.Column(
        "provider", sa.String(length=20), server_default=sa.text("'daraja'"), nullable=False))
    op.add_column("payment_attempts", sa.Column(
        "kind", sa.String(length=12), server_default=sa.text("'collection'"), nullable=False))
    op.execute("ALTER TABLE payment_attempts RENAME CONSTRAINT "
               "uq_mpesa_requests_checkout TO uq_payment_attempts_provider_ref")
    op.execute("ALTER INDEX ix_mpesa_requests_user_id RENAME TO ix_payment_attempts_user_id")
    op.execute("ALTER INDEX uq_mpesa_requests_receipt RENAME TO uq_payment_attempts_receipt")


def downgrade() -> None:
    op.execute("ALTER INDEX uq_payment_attempts_receipt RENAME TO uq_mpesa_requests_receipt")
    op.execute("ALTER INDEX ix_payment_attempts_user_id RENAME TO ix_mpesa_requests_user_id")
    op.execute("ALTER TABLE payment_attempts RENAME CONSTRAINT "
               "uq_payment_attempts_provider_ref TO uq_mpesa_requests_checkout")
    op.drop_column("payment_attempts", "kind")
    op.drop_column("payment_attempts", "provider")
    op.alter_column("payment_attempts", "provider_receipt", new_column_name="mpesa_receipt")
    op.alter_column("payment_attempts", "provider_ref2", new_column_name="merchant_request_id")
    op.alter_column("payment_attempts", "provider_ref", new_column_name="checkout_request_id")
    op.rename_table("payment_attempts", "mpesa_requests")
