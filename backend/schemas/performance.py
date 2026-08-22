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
