"""PILOT OPERATIONS DASHBOARD - 실제 파일럿 업체/손님을 대상으로 AI가 얼마나
쓰이고 실제 매출로 이어지는지 측정한다.

원칙(§29와 동일):
- 새 이벤트 테이블을 만들지 않는다. 전부 기존 AiInteraction/CouponIssue/
  Reservation/Transaction/BusinessRelationship/RecommendationClick를 그대로
  집계한다.
- Transaction.attribution(DIRECT/ASSISTED/UNKNOWN)만이 "AI가 만든 매출"의
  유일한 근거다. 단순 AI 응대 건수를 매출로 둔갑시키지 않는다.
- Info AI(services/agents/info.py)는 특정 업체에 종속되지 않는 agent라서
  (context={}, AiInteraction.business_id가 항상 None) 업체별 "질문 수"나
  "노출 수"는 원래 계산할 수 없다 - 이 업체로 실제로 연결된 추천 클릭
  (RecommendationClick.entity_id)만 업체별로 잡을 수 있다. 없는 걸 있는
  것처럼 보여주지 않는다.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import (
    AiInteraction,
    Business,
    BusinessRelationship,
    BusinessStatus,
    Coupon,
    CouponIssue,
    CouponIssueStatus,
    PartnerRelationshipStatus,
    RecommendationClick,
    Reservation,
    ReservationStatus,
    Transaction,
    TransactionAttribution,
)

_KST = timezone(timedelta(hours=9))
VALID_PERIODS = ("today", "yesterday", "7d", "30d", "all")

# 실제 추천이 있었던 응답과, "지금 등록된 곳 중에는 마땅한 곳이 없어요" 같은
# 무응답을 구분하기 위한 기준 - services/agents/info.py의 상수와 반드시
# 같은 문자열을 써야 한다(그쪽이 실제로 만드는 문자열이므로 여기서 재정의).
_INFO_NO_MATCH_MESSAGE = "지금 등록된 곳 중에는 마땅한 곳이 없어요."


def resolve_period(period: str) -> tuple[datetime | None, datetime | None]:
    """(start, end) UTC 반환. end가 None이면 "지금까지"라는 뜻. start가
    None이면 "전체 기간"이라는 뜻."""
    if period not in VALID_PERIODS:
        raise ValueError(f"알 수 없는 기간입니다: {period}")

    now = datetime.now(timezone.utc)
    if period == "all":
        return None, None
    if period == "7d":
        return now - timedelta(days=7), None
    if period == "30d":
        return now - timedelta(days=30), None

    # "오늘"/"어제"는 실제 파일럿 업체/사장님이 체감하는 한국 시간 기준 자정.
    now_kst = now.astimezone(_KST)
    today_start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start_kst.astimezone(timezone.utc)
    if period == "today":
        return today_start_utc, None
    # yesterday
    yesterday_start_utc = (today_start_kst - timedelta(days=1)).astimezone(timezone.utc)
    return yesterday_start_utc, today_start_utc


def _range_filters(column, start: datetime | None, end: datetime | None) -> list:
    conds = []
    if start is not None:
        conds.append(column >= start)
    if end is not None:
        conds.append(column < end)
    return conds


@dataclass
class FunnelStep:
    key: str
    label: str
    count: int
    conversion_rate_from_previous: float | None = None


@dataclass
class RevenueBreakdown:
    total_revenue: Decimal
    ai_connected_revenue: Decimal
    direct_revenue: Decimal
    assisted_revenue: Decimal
    unknown_revenue: Decimal
    ai_connected_transaction_count: int


@dataclass
class AgentBreakdownRow:
    agent_type: str
    interactions: int | None
    recommendation_clicks: int | None = None
    note: str | None = None


@dataclass
class BusinessDashboard:
    business_id: UUID
    business_name: str
    period: str
    ai_interactions_total: int
    ai_interactions_by_agent: dict[str, int]
    coupons_issued: int
    coupons_redeemed: int
    reservations_created: int
    reservations_completed: int
    visits_confirmed: int
    recommendation_clicks: int
    funnel: list[FunnelStep]
    revenue: RevenueBreakdown
    agents: list[AgentBreakdownRow]


@dataclass
class BusinessComparisonRow:
    business_id: UUID
    business_name: str
    pilot_status: str | None
    ai_interactions: int
    recommendation_clicks: int
    coupons_issued: int
    reservations_created: int
    visits_confirmed: int
    transactions: int
    direct_revenue: Decimal
    assisted_revenue: Decimal
    unknown_revenue: Decimal
    ai_connected_revenue: Decimal


@dataclass
class PilotOverview:
    period: str
    pilot_business_count: int
    active_business_count: int
    daily_active_businesses: int
    weekly_active_businesses: int
    businesses_using_ai: int
    customer_ai_questions: int
    chef_ai_questions: int
    info_ai_questions: int
    recommendation_impressions: int
    recommendation_clicks: int
    coupons_issued: int
    coupons_redeemed: int
    reservations_created: int
    reservations_completed: int
    visits_confirmed: int
    transactions_created: int
    revenue: RevenueBreakdown
    revenue_by_business: dict[str, Decimal]
    expansion_runs: int
    partner_candidates: int
    partner_invites: int
    referral_clicks: int
    new_businesses_via_referral: int
    funnel: list[FunnelStep]
    businesses: list[BusinessComparisonRow]


def _pilot_business_ids(db: Session) -> list[UUID]:
    rows = db.query(Business.id).filter(Business.pilot_status.isnot(None)).all()
    return [r[0] for r in rows]


def _ai_interactions_by_agent(
    db: Session, business_ids: list[UUID] | None, start: datetime | None, end: datetime | None
) -> dict[str, int]:
    q = db.query(AiInteraction.agent_type, func.count(AiInteraction.id))
    q = q.filter(*_range_filters(AiInteraction.created_at, start, end))
    if business_ids is not None:
        q = q.filter(AiInteraction.business_id.in_(business_ids))
    return {agent_type: count for agent_type, count in q.group_by(AiInteraction.agent_type).all()}


def _recommendation_impressions(db: Session, start: datetime | None, end: datetime | None) -> int:
    """추천이 실제로 1건 이상 있었던 Info AI 응답 수 - 업체에 종속되지
    않으므로 항상 플랫폼 전체 값이다(위 모듈 docstring 참고)."""
    q = db.query(func.count(AiInteraction.id)).filter(
        AiInteraction.agent_type == "info", AiInteraction.reply != _INFO_NO_MATCH_MESSAGE
    )
    q = q.filter(*_range_filters(AiInteraction.created_at, start, end))
    return q.scalar() or 0


def _recommendation_clicks_count(
    db: Session, business_id: UUID | None, start: datetime | None, end: datetime | None
) -> int:
    q = db.query(func.count(RecommendationClick.id))
    q = q.filter(*_range_filters(RecommendationClick.created_at, start, end))
    if business_id is not None:
        q = q.filter(RecommendationClick.entity_id == business_id, RecommendationClick.entity_type == "business")
    else:
        q = q.filter(RecommendationClick.entity_type == "business")
    return q.scalar() or 0


def _coupon_counts(
    db: Session, business_ids: list[UUID] | None, start: datetime | None, end: datetime | None
) -> tuple[int, int]:
    issued_q = db.query(func.count(CouponIssue.id)).join(Coupon)
    issued_q = issued_q.filter(*_range_filters(CouponIssue.issued_at, start, end))
    redeemed_q = db.query(func.count(CouponIssue.id)).join(Coupon)
    redeemed_q = redeemed_q.filter(
        CouponIssue.status == CouponIssueStatus.REDEEMED, *_range_filters(CouponIssue.redeemed_at, start, end)
    )
    if business_ids is not None:
        issued_q = issued_q.filter(Coupon.business_id.in_(business_ids))
        redeemed_q = redeemed_q.filter(Coupon.business_id.in_(business_ids))
    return issued_q.scalar() or 0, redeemed_q.scalar() or 0


def _reservation_counts(
    db: Session, business_ids: list[UUID] | None, start: datetime | None, end: datetime | None
) -> tuple[int, int]:
    created_q = db.query(func.count(Reservation.id)).filter(
        *_range_filters(Reservation.created_at, start, end)
    )
    completed_q = db.query(func.count(Reservation.id)).filter(
        Reservation.status == ReservationStatus.COMPLETED, *_range_filters(Reservation.updated_at, start, end)
    )
    if business_ids is not None:
        created_q = created_q.filter(Reservation.business_id.in_(business_ids))
        completed_q = completed_q.filter(Reservation.business_id.in_(business_ids))
    return created_q.scalar() or 0, completed_q.scalar() or 0


def _revenue_breakdown(
    db: Session, business_ids: list[UUID] | None, start: datetime | None, end: datetime | None
) -> RevenueBreakdown:
    q = db.query(Transaction.attribution, func.coalesce(func.sum(Transaction.amount), 0), func.count(Transaction.id))
    q = q.filter(*_range_filters(Transaction.occurred_at, start, end))
    if business_ids is not None:
        q = q.filter(Transaction.business_id.in_(business_ids))
    rows = q.group_by(Transaction.attribution).all()

    by_attribution: dict[TransactionAttribution, tuple[Decimal, int]] = {
        attribution: (Decimal(amount), count) for attribution, amount, count in rows
    }
    direct_amount, direct_count = by_attribution.get(TransactionAttribution.DIRECT, (Decimal(0), 0))
    assisted_amount, assisted_count = by_attribution.get(TransactionAttribution.ASSISTED, (Decimal(0), 0))
    unknown_amount, _unknown_count = by_attribution.get(TransactionAttribution.UNKNOWN, (Decimal(0), 0))

    return RevenueBreakdown(
        total_revenue=direct_amount + assisted_amount + unknown_amount,
        ai_connected_revenue=direct_amount + assisted_amount,
        direct_revenue=direct_amount,
        assisted_revenue=assisted_amount,
        unknown_revenue=unknown_amount,
        ai_connected_transaction_count=direct_count + assisted_count,
    )


def _transaction_count(
    db: Session, business_ids: list[UUID] | None, start: datetime | None, end: datetime | None
) -> int:
    q = db.query(func.count(Transaction.id)).filter(*_range_filters(Transaction.occurred_at, start, end))
    if business_ids is not None:
        q = q.filter(Transaction.business_id.in_(business_ids))
    return q.scalar() or 0


def _build_funnel(
    *,
    ai_questions: int,
    impressions: int,
    clicks: int,
    coupons_or_reservations: int,
    visits: int,
    transactions: int,
    ai_connected_revenue: Decimal,
) -> list[FunnelStep]:
    steps_raw = [
        ("ai_questions", "AI 질문", ai_questions),
        ("impressions", "추천 노출", impressions),
        ("clicks", "추천 클릭", clicks),
        ("coupon_or_reservation", "쿠폰/예약", coupons_or_reservations),
        ("visits", "방문", visits),
        ("transactions", "거래", transactions),
    ]
    steps: list[FunnelStep] = []
    previous_count: int | None = None
    for key, label, count in steps_raw:
        rate = None
        if previous_count is not None and previous_count > 0:
            rate = round(count / previous_count, 4)
        steps.append(FunnelStep(key=key, label=label, count=count, conversion_rate_from_previous=rate))
        previous_count = count
    # 매출은 count 퍼널의 마지막 단계가 아니라 별도 표시(§4 - "AI 연결
    # 매출"을 퍼널의 count처럼 섞으면 오해를 부른다. amount 필드가 없는
    # FunnelStep에 억지로 넣지 않고, 호출부에서 revenue를 같이 반환한다).
    return steps


def compute_business_dashboard(
    db: Session, business: Business, period: str
) -> BusinessDashboard:
    start, end = resolve_period(period)
    business_ids = [business.id]

    interactions_by_agent = _ai_interactions_by_agent(db, business_ids, start, end)
    total_interactions = sum(interactions_by_agent.values())

    coupons_issued, coupons_redeemed = _coupon_counts(db, business_ids, start, end)
    reservations_created, reservations_completed = _reservation_counts(db, business_ids, start, end)
    visits_confirmed = coupons_redeemed + reservations_completed
    clicks = _recommendation_clicks_count(db, business.id, start, end)
    revenue = _revenue_breakdown(db, business_ids, start, end)
    transactions = _transaction_count(db, business_ids, start, end)

    # 이 업체가 이번 기간에 실제로 몇 번 추천에 노출됐는지는 계산할 수 없다
    # (모듈 docstring 참고) - 퍼널의 "추천 노출" 단계는 업체 단위에서는
    # 클릭 수와 동일하게 둔다(과대표시 방지 - 클릭보다 큰 노출수를 지어내지
    # 않는다는 뜻에서 최소값인 클릭 수를 그대로 쓴다).
    impressions_for_business = clicks

    funnel = _build_funnel(
        ai_questions=total_interactions,
        impressions=impressions_for_business,
        clicks=clicks,
        coupons_or_reservations=coupons_issued + reservations_created,
        visits=visits_confirmed,
        transactions=transactions,
        ai_connected_revenue=revenue.ai_connected_revenue,
    )

    agents = [
        AgentBreakdownRow(agent_type="manager", interactions=interactions_by_agent.get("manager", 0)),
        AgentBreakdownRow(agent_type="customer", interactions=interactions_by_agent.get("customer", 0)),
        AgentBreakdownRow(agent_type="chef", interactions=interactions_by_agent.get("chef", 0)),
        AgentBreakdownRow(
            agent_type="info",
            interactions=None,
            recommendation_clicks=clicks,
            note="Info AI는 특정 업체에 종속되지 않는 전체 방문객 대상 agent라 "
            "이 업체에 대한 질문 수·노출 수는 집계할 수 없습니다. 이 업체로 "
            "실제로 연결된 추천 클릭 수만 표시합니다.",
        ),
        AgentBreakdownRow(agent_type="expansion", interactions=interactions_by_agent.get("expansion", 0)),
    ]

    return BusinessDashboard(
        business_id=business.id,
        business_name=business.name_ko,
        period=period,
        ai_interactions_total=total_interactions,
        ai_interactions_by_agent=interactions_by_agent,
        coupons_issued=coupons_issued,
        coupons_redeemed=coupons_redeemed,
        reservations_created=reservations_created,
        reservations_completed=reservations_completed,
        visits_confirmed=visits_confirmed,
        recommendation_clicks=clicks,
        funnel=funnel,
        revenue=revenue,
        agents=agents,
    )


def compute_pilot_overview(db: Session, period: str) -> PilotOverview:
    start, end = resolve_period(period)
    pilot_ids = _pilot_business_ids(db)

    active_business_count = (
        db.query(func.count(Business.id))
        .filter(Business.id.in_(pilot_ids), Business.status == BusinessStatus.ACTIVE)
        .scalar()
        or 0
    )

    def _distinct_active_businesses(since: datetime) -> int:
        return (
            db.query(func.count(func.distinct(AiInteraction.business_id)))
            .filter(AiInteraction.business_id.in_(pilot_ids), AiInteraction.created_at >= since)
            .scalar()
            or 0
        )

    now = datetime.now(timezone.utc)
    daily_active = _distinct_active_businesses(now - timedelta(days=1))
    weekly_active = _distinct_active_businesses(now - timedelta(days=7))

    # pilot_ids가 빈 리스트여도 SQLAlchemy의 in_([])는 안전하게 "결과 없음"을
    # 뜻하므로 별도 무결과 처리를 만들 필요가 없다.
    interactions_by_agent = _ai_interactions_by_agent(db, pilot_ids, start, end)
    businesses_using_ai = (
        db.query(func.count(func.distinct(AiInteraction.business_id)))
        .filter(AiInteraction.business_id.in_(pilot_ids), *_range_filters(AiInteraction.created_at, start, end))
        .scalar()
        or 0
    )

    impressions = _recommendation_impressions(db, start, end)
    clicks = _recommendation_clicks_count(db, None, start, end)

    coupons_issued, coupons_redeemed = _coupon_counts(db, pilot_ids, start, end)
    reservations_created, reservations_completed = _reservation_counts(db, pilot_ids, start, end)
    visits_confirmed = coupons_redeemed + reservations_completed
    revenue = _revenue_breakdown(db, pilot_ids, start, end)
    transactions = _transaction_count(db, pilot_ids, start, end)

    # Info AI는 특정 업체에 종속되지 않는 agent라서(AiInteraction.business_id가
    # 항상 None) 위 interactions_by_agent(pilot_ids로 필터링)에는 절대 안
    # 잡힌다 - 파일럿 업체 필터와 무관하게 플랫폼 전체 값으로 따로 센다.
    info_ai_questions = (
        db.query(func.count(AiInteraction.id))
        .filter(AiInteraction.agent_type == "info", *_range_filters(AiInteraction.created_at, start, end))
        .scalar()
        or 0
    )

    revenue_by_business_rows = (
        db.query(Transaction.business_id, func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.business_id.in_(pilot_ids),
            Transaction.attribution.in_([TransactionAttribution.DIRECT, TransactionAttribution.ASSISTED]),
            *_range_filters(Transaction.occurred_at, start, end),
        )
        .group_by(Transaction.business_id)
        .all()
        if pilot_ids
        else []
    )
    revenue_by_business = {str(bid): Decimal(amount) for bid, amount in revenue_by_business_rows}

    expansion_runs = interactions_by_agent.get("expansion", 0)
    partner_candidates = (
        db.query(func.count(BusinessRelationship.id))
        .filter(
            BusinessRelationship.business_a_id.in_(pilot_ids), *_range_filters(BusinessRelationship.created_at, start, end)
        )
        .scalar()
        or 0
    )

    # 제휴 제안(INVITED) 건수는 상태 전이 시각을 별도로 기록하지 않아
    # created_at(=제안 후보가 처음 생성된 시각)으로 근사한다 - 정확한 "언제
    # INVITED로 바뀌었는지"가 아니라 "그 후보가 이 기간에 생성됐고 지금은
    # INVITED 상태다"라는 근사치임을 명시한다.
    partner_invites = (
        db.query(func.count(BusinessRelationship.id))
        .filter(
            BusinessRelationship.business_a_id.in_(pilot_ids),
            BusinessRelationship.status == PartnerRelationshipStatus.INVITED,
            *_range_filters(BusinessRelationship.created_at, start, end),
        )
        .scalar()
        or 0
    )

    referral_clicks = (
        db.query(func.count(BusinessRelationship.id))
        .filter(
            BusinessRelationship.business_a_id.in_(pilot_ids),
            *_range_filters(BusinessRelationship.referral_clicked_at, start, end),
        )
        .scalar()
        or 0
    )

    new_businesses_via_referral = (
        db.query(func.count(BusinessRelationship.id))
        .filter(
            BusinessRelationship.business_a_id.in_(pilot_ids),
            *_range_filters(BusinessRelationship.referral_signup_confirmed_at, start, end),
        )
        .scalar()
        or 0
    )

    funnel = _build_funnel(
        ai_questions=sum(interactions_by_agent.values()),
        impressions=impressions,
        clicks=clicks,
        coupons_or_reservations=coupons_issued + reservations_created,
        visits=visits_confirmed,
        transactions=transactions,
        ai_connected_revenue=revenue.ai_connected_revenue,
    )

    comparison_rows: list[BusinessComparisonRow] = []
    if pilot_ids:
        pilot_businesses = db.query(Business).filter(Business.id.in_(pilot_ids)).all()
        for b in pilot_businesses:
            b_interactions = sum(_ai_interactions_by_agent(db, [b.id], start, end).values())
            b_clicks = _recommendation_clicks_count(db, b.id, start, end)
            b_coupons_issued, b_coupons_redeemed = _coupon_counts(db, [b.id], start, end)
            b_reservations_created, b_reservations_completed = _reservation_counts(db, [b.id], start, end)
            b_revenue = _revenue_breakdown(db, [b.id], start, end)
            b_transaction_count = _transaction_count(db, [b.id], start, end)
            comparison_rows.append(
                BusinessComparisonRow(
                    business_id=b.id,
                    business_name=b.name_ko,
                    pilot_status=b.pilot_status.value if b.pilot_status else None,
                    ai_interactions=b_interactions,
                    recommendation_clicks=b_clicks,
                    coupons_issued=b_coupons_issued,
                    reservations_created=b_reservations_created,
                    visits_confirmed=b_coupons_redeemed + b_reservations_completed,
                    transactions=b_transaction_count,
                    direct_revenue=b_revenue.direct_revenue,
                    assisted_revenue=b_revenue.assisted_revenue,
                    unknown_revenue=b_revenue.unknown_revenue,
                    ai_connected_revenue=b_revenue.ai_connected_revenue,
                )
            )
        comparison_rows.sort(key=lambda r: r.ai_connected_revenue, reverse=True)

    return PilotOverview(
        period=period,
        pilot_business_count=len(pilot_ids),
        active_business_count=active_business_count,
        daily_active_businesses=daily_active,
        weekly_active_businesses=weekly_active,
        businesses_using_ai=businesses_using_ai,
        customer_ai_questions=interactions_by_agent.get("customer", 0),
        chef_ai_questions=interactions_by_agent.get("chef", 0),
        info_ai_questions=info_ai_questions,
        recommendation_impressions=impressions,
        recommendation_clicks=clicks,
        coupons_issued=coupons_issued,
        coupons_redeemed=coupons_redeemed,
        reservations_created=reservations_created,
        reservations_completed=reservations_completed,
        visits_confirmed=visits_confirmed,
        transactions_created=transactions,
        revenue=revenue,
        revenue_by_business=revenue_by_business,
        expansion_runs=expansion_runs,
        partner_candidates=partner_candidates,
        partner_invites=partner_invites,
        referral_clicks=referral_clicks,
        new_businesses_via_referral=new_businesses_via_referral,
        funnel=funnel,
        businesses=comparison_rows,
    )
