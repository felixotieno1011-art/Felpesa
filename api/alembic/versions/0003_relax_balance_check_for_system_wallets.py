"""relax balance CHECK to allow negative system (clearing) wallets

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-23 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old check (user wallets AND system wallets must be >= 0)
    op.execute(text(
        "ALTER TABLE wallets DROP CONSTRAINT IF EXISTS ck_wallets_balance_non_negative"
    ))
    # Add new check: user wallets >= 0; system wallets (clearing) may go negative.
    # The negative balance of the clearing wallet represents the system's
    # liability to users (money we owe, minus money we've received).
    op.execute(text(
        "ALTER TABLE wallets ADD CONSTRAINT ck_wallets_balance_non_negative "
        "CHECK (is_system OR balance >= 0)"
    ))


def downgrade() -> None:
    op.execute(text(
        "ALTER TABLE wallets DROP CONSTRAINT IF EXISTS ck_wallets_balance_non_negative"
    ))
    # Reverting requires no negative balances; fail loudly if any exist.
    op.execute(text(
        "ALTER TABLE wallets ADD CONSTRAINT ck_wallets_balance_non_negative "
        "CHECK (balance >= 0)"
    ))
