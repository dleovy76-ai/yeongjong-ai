"""add ASSISTED and UNKNOWN to transaction_attribution

Revision ID: 28dd0a4a47a7
Revises: f85fcf8302f6
Create Date: 2026-08-24 20:41:24.525513

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28dd0a4a47a7'
down_revision: Union[str, Sequence[str], None] = 'f85fcf8302f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE transaction_attribution ADD VALUE IF NOT EXISTS 'ASSISTED'")
    op.execute("ALTER TYPE transaction_attribution ADD VALUE IF NOT EXISTS 'UNKNOWN'")


def downgrade() -> None:
    """Downgrade schema."""
    raise NotImplementedError("transaction_attribution enum values cannot be dropped by this migration")
