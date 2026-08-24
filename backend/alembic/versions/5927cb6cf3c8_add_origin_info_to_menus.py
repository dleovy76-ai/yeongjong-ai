"""add origin_info to menus

Revision ID: 5927cb6cf3c8
Revises: 2acd6c22f020
Create Date: 2026-08-25 05:58:15.361225

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5927cb6cf3c8'
down_revision: Union[str, Sequence[str], None] = '2acd6c22f020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('menus', sa.Column('origin_info', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('menus', 'origin_info')
