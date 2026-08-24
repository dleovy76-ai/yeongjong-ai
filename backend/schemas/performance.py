from decimal import Decimal

from pydantic import BaseModel


class PerformanceResponse(BaseModel):
    period: str
    ai_response_count: int
    coupons_issued: int
    coupons_redeemed: int
    estimated_time_saved_minutes: int
    estimated_time_saved_note: str = (
        "AI 응대 1건당 약 3분 절감을 가정한 추정치입니다 (검증된 값이 아닙니다)."
    )
    revenue_total: Decimal
    revenue_direct_ai_attributed: Decimal
    revenue_direct_ai_attributed_note: str = (
        "AI가 추천한 쿠폰이 실제 사용되었거나, AI로 예약이 실제 완료된 거래만 집계한 값입니다 - "
        "매장에 다녀갔지만 링크가 없는 거래는 포함되지 않습니다."
    )
