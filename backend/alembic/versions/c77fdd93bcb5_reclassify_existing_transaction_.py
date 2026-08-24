"""reclassify existing transaction attributions

Revision ID: c77fdd93bcb5
Revises: 28dd0a4a47a7
Create Date: 2026-08-24 20:41:42.485763

Master plan §18 (기획서 11번): DIRECT is now coupon-only ("AI 추천 -> 쿠폰
-> 결제"), and the reservation-linked case that used to also be labeled
DIRECT is really ASSISTED ("AI가 예약/방문을 지원했고 실제 거래가 확인됨").
The old catch-all NONE value is renamed UNKNOWN ("거래 연결을 확인할 수
없음") to match §18's own term. Must run in a separate migration from the
one that adds the ASSISTED/UNKNOWN enum values - Postgres won't let a
newly-added enum value be used in the same transaction that added it.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c77fdd93bcb5'
down_revision: Union[str, Sequence[str], None] = '28dd0a4a47a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "UPDATE transactions SET attribution = 'ASSISTED' "
        "WHERE attribution = 'DIRECT' AND reservation_id IS NOT NULL"
    )
    op.execute("UPDATE transactions SET attribution = 'UNKNOWN' WHERE attribution = 'NONE'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "UPDATE transactions SET attribution = 'DIRECT' "
        "WHERE attribution = 'ASSISTED' AND reservation_id IS NOT NULL"
    )
    op.execute("UPDATE transactions SET attribution = 'NONE' WHERE attribution = 'UNKNOWN'")
