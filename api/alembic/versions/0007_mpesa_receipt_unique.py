"""unique mpesa receipt + nullable checkout id

Revision ID: 0007
Revises: 0006
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("mpesa_requests", "checkout_request_id", nullable=True)
    op.create_index(
        "uq_mpesa_requests_receipt", "mpesa_requests", ["mpesa_receipt"],
        unique=True, postgresql_where="mpesa_receipt IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_mpesa_requests_receipt", table_name="mpesa_requests")
