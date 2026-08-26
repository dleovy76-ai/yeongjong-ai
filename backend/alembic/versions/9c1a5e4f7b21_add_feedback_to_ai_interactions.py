"""add feedback to ai_interactions

Revision ID: 9c1a5e4f7b21
Revises: 5927cb6cf3c8
Create Date: 2026-08-26 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c1a5e4f7b21'
down_revision: Union[str, Sequence[str], None] = '5927cb6cf3c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ai_interaction_feedback_enum = sa.Enum('UP', 'DOWN', name='ai_interaction_feedback')


def upgrade() -> None:
    """Upgrade schema."""
    # autogenerate로 만든 add_column만으로는 새 Postgres enum 타입 자체가
    # 생성되지 않는다(create_table과 묶일 때만 자동 생성됨) - 직접 만든다.
    _ai_interaction_feedback_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('ai_interactions', sa.Column('feedback', _ai_interaction_feedback_enum, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ai_interactions', 'feedback')
    _ai_interaction_feedback_enum.drop(op.get_bind(), checkfirst=True)
