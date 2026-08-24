"""add pilot_status to businesses

Revision ID: 2acd6c22f020
Revises: 851d0be65d94
Create Date: 2026-08-25 02:47:54.288946

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2acd6c22f020'
down_revision: Union[str, Sequence[str], None] = '851d0be65d94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_pilot_status_enum = sa.Enum('PILOT_ACTIVE', 'PILOT_PAUSED', 'PILOT_COMPLETED', name='pilot_status')


def upgrade() -> None:
    """Upgrade schema."""
    # autogenerate로 만든 add_column만으로는 새 Postgres enum 타입 자체가
    # 생성되지 않는다(create_table과 묶일 때만 자동 생성됨) - 직접 만든다.
    _pilot_status_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('businesses', sa.Column('pilot_status', _pilot_status_enum, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('businesses', 'pilot_status')
    _pilot_status_enum.drop(op.get_bind(), checkfirst=True)
