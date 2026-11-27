"""one attempt per transaction and kind

Revision ID: 0010
Revises: 0009
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_payment_attempts_txn_kind", "payment_attempts", ["transaction_id", "kind"],
        unique=True, postgresql_where="transaction_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_payment_attempts_txn_kind", table_name="payment_attempts")
