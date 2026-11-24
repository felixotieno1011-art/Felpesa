"""add is_system to wallets + seed clearing wallet

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-23 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add is_system column
    op.add_column(
        'wallets',
        sa.Column('is_system', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )

    # 2. Seed the system user (inactive, role='system' — can't log in)
    op.execute(
        text("""
            INSERT INTO users (phone, full_name, password_hash, role, is_active)
            VALUES (
                '+000000000000',
                'Felpesa Clearing',
                '!',  -- invalid hash — this account can never authenticate
                'admin',  -- only role value available in CHECK; use is_active to prevent login
                false
            )
            ON CONFLICT (phone) DO NOTHING
        """)
    )

    # 3. Seed the clearing wallet for the system user
    op.execute(
        text("""
            INSERT INTO wallets (user_id, currency, balance, status, is_system)
            SELECT id, 'KES', 0, 'active', true
            FROM users
            WHERE phone = '+000000000000'
            ON CONFLICT (user_id, currency) DO NOTHING
        """)
    )


def downgrade() -> None:
    # Remove clearing wallet and system user first (FK constraints)
    op.execute(
        text("""
            DELETE FROM wallets
            WHERE is_system = true
              AND user_id IN (SELECT id FROM users WHERE phone = '+000000000000')
        """)
    )
    op.execute(text("DELETE FROM users WHERE phone = '+000000000000'"))
    op.drop_column('wallets', 'is_system')
