from decimal import Decimal

from pydantic import BaseModel


class PerformanceResponse(BaseModel):
    period: str
    ai_response_count: int
    ai_response_count_by_agent_type: dict[str, int]
    coupons_issued: int
    coupons_redeemed: int
    reservations_this_month: int
    successful_referrals: int
    successful_referrals_note: str = (
        "우리 가게가 보낸 초대 링크로 실제 새 업체가 가입한 누적 건수입니다 (전체 기간 기준). "
        "아직 할인/포인트 같은 보상은 없어요 - 결제·포인트 시스템이 생기면 추가될 예정입니다."
    )
    estimated_time_saved_minutes: int
    estimated_time_saved_note: str = (
        "AI 응대 1건당 약 3분 절감을 가정한 추정치입니다 (검증된 값이 아닙니다)."
    )
    revenue_total: Decimal
    revenue_direct: Decimal
    revenue_assisted: Decimal
    revenue_unknown: Decimal
    revenue_ai_connected: Decimal
    revenue_ai_connected_note: str = (
        "DIRECT(AI 추천→쿠폰→결제로 실제 연결 확인)와 ASSISTED(AI가 예약을 지원했고 실제 방문·"
        "거래가 확인됨)만 합산한 값입니다. 링크 없이 기록된 거래(UNKNOWN)는 실제 매출이지만 "
        "AI 연결 여부를 확인할 수 없어 이 합계에서 제외됩니다 - 단순 추천을 매출로 계산하지 않습니다."
    )
