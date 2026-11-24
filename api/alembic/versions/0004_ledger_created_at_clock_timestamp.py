"""use clock_timestamp() for ledger_entries.created_at ordering

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-23 22:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # clock_timestamp() returns the actual wall-clock time at each insert,
    # not the transaction start time like now(). After lock waits, now() can
    # produce ledger entries whose created_at is earlier than a subsequent
    # transaction's — breaking chronological ordering for audit purposes.
    op.execute(text(
        "ALTER TABLE ledger_entries ALTER COLUMN created_at "
        "SET DEFAULT clock_timestamp()"
    ))


def downgrade() -> None:
    op.execute(text(
        "ALTER TABLE ledger_entries ALTER COLUMN created_at "
        "SET DEFAULT now()"
    ))
