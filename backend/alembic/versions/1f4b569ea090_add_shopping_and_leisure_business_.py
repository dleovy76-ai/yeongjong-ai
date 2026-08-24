"""add shopping and leisure business categories

Revision ID: 1f4b569ea090
Revises: f2e5be237cd4
Create Date: 2026-08-24 17:23:46.789313

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f4b569ea090'
down_revision: Union[str, Sequence[str], None] = 'f2e5be237cd4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE business_category ADD VALUE IF NOT EXISTS 'SHOPPING'")
    op.execute("ALTER TYPE business_category ADD VALUE IF NOT EXISTS 'LEISURE'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no DROP VALUE for enums - removing SHOPPING/LEISURE would
    # require recreating the type and remapping any rows already using them,
    # which isn't safe to do unconditionally in a migration. Not supported.
    raise NotImplementedError("business_category enum values cannot be dropped by this migration")
