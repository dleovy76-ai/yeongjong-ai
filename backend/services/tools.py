"""Master plan §53: agents don't query the DB directly - they go through Tools,
so what data an agent *can* see is defined in one place, not scattered across
prompts. Each tool returns plain dicts (already JSON-safe) ready to drop into an
LLM prompt."""

import math
from datetime import datetime, timezone
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
    CouponStatus,
    Menu,
    PartnerRelationshipStatus,
    Reservation,
    ReservationStatus,
    TouristPlace,
    TouristPlaceStatus,
    Transaction,
    TransactionAttribution,
)
from services.pilot_analytics import _recommendation_clicks_count, _reservation_counts


def current_month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def distance_meters(lon1: float | None, lat1: float | None, lon2: float | None, lat2: float | None) -> float | None:
    """None when either point is missing coordinates - callers must treat that
    as "unknown", not zero. Equirectangular approximation, fine at a few-km scale."""
    if lon1 is None or lat1 is None or lon2 is None or lat2 is None:
        return None
    lat_rad = math.radians((lat1 + lat2) / 2)
    dx = (lon2 - lon1) * math.cos(lat_rad)
    dy = lat2 - lat1
    return math.sqrt(dx * dx + dy * dy) * 111_320


def is_coupon_currently_claimable(coupon: Coupon) -> bool:
    """Shared by CouponSearchTool (what the AI may mention) and the coupon
    router's /issue endpoint (what a visitor may actually claim) - one
    definition of "live" so an agent can never advertise a coupon that issuing
    would then reject."""
    if coupon.status != CouponStatus.ACTIVE:
        return False
    now = datetime.now(timezone.utc)
    if coupon.start_at is not None and coupon.start_at.replace(tzinfo=timezone.utc) > now:
        return False
    if coupon.end_at is not None and coupon.end_at.replace(tzinfo=timezone.utc) < now:
        return False
    if coupon.usage_limit is not None and len(coupon.issues) >= coupon.usage_limit:
        return False
    return True


class BusinessSearchTool:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_context(self, business_id: UUID) -> dict | None:
        """The approved BusinessContext (§8) an agent may state as fact. Returns
        None if the business doesn't exist or has no profile filled in yet."""
        business = self.db.get(Business, business_id)
        if business is None or business.profile is None:
            return None

        profile = business.profile
        return {
            "name": business.name_ko,
            "category": business.category.value,
            "address": business.address,
            "phone": business.phone,
            "description": profile.description,
            "brand_tone": profile.brand_tone,
            "opening_hours": profile.opening_hours,
            "holiday": profile.holiday,
            "parking": profile.parking,
            "pet_policy": profile.pet_policy,
            "reservation_policy": profile.reservation_policy,
            "takeout_policy": profile.takeout_policy,
            "payment_methods": profile.payment_methods,
            "faq": profile.faq,
        }


class BusinessDirectoryTool:
    """Master plan §14 Recommendation Engine's candidate pool - deliberately scoped
    to businesses actually registered on the platform (real, verified data), never
    general Yeongjong tourism knowledge. Info AI must not invent attractions that
    aren't real registered businesses (§29); a real tourist_places dataset with its
    own sourcing/verification is future work, not something to fabricate here."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active(self, limit: int = 30) -> list[dict]:
        businesses = (
            self.db.query(Business)
            .filter(Business.status == BusinessStatus.ACTIVE)
            .order_by(Business.created_at.desc())
            .limit(limit)
            .all()
        )
        results = []
        for b in businesses:
            signature_menus = [m.name for m in b.menus if m.is_signature]
            results.append(
                {
                    "id": str(b.id),
                    "name": b.name_ko,
                    "category": b.category.value,
                    "address": b.address,
                    "pet_policy": b.profile.pet_policy if b.profile else None,
                    "parking": b.profile.parking if b.profile else None,
                    "signature_menus": signature_menus,
                }
            )
        return results


class TouristPlaceSearchTool:
    """Master plan §12/§28 Info AI's regional-knowledge counterpart to
    BusinessDirectoryTool - only ever returns admin-verified, non-expired
    rows (§29: AI must not invent 관광지 운영 여부). Rows an admin hasn't
    verified, or has let expire/disabled, are invisible here regardless of
    what they contain."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_verified(self, limit: int = 30) -> list[dict]:
        now = datetime.now(timezone.utc)
        candidates = (
            self.db.query(TouristPlace)
            .filter(TouristPlace.status == TouristPlaceStatus.VERIFIED)
            .order_by(TouristPlace.created_at.desc())
            .all()
        )
        # naive-column-vs-aware-now comparison done in Python, matching
        # is_coupon_currently_claimable's convention above.
        places = [
            p for p in candidates if p.expires_at is None or p.expires_at.replace(tzinfo=timezone.utc) > now
        ][:limit]
        return [
            {
                "id": str(p.id),
                "name": p.name,
                "category": p.category,
                "description": p.description,
                "address": p.address,
            }
            for p in places
        ]


class MenuSearchTool:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_menus(self, business_id: UUID) -> list[dict]:
        menus = self.db.query(Menu).filter(Menu.business_id == business_id).all()
        return [
            {
                "name": m.name,
                "description": m.description,
                "price": str(m.price),
                "is_signature": m.is_signature,
                "allergy_info": m.allergy_info,
                "origin_info": m.origin_info,
            }
            for m in menus
        ]

    def list_menus_with_media(self, business_id: UUID) -> list[dict]:
        """Chef AI 답변에 실제 메뉴 사진을 붙이기 위한 전용 조회 - list_menus()와
        분리해두는 이유는, id/image_url을 프롬프트(list_menus의 결과)에 절대
        섞지 않기 위해서다. LLM에게 URL을 보여주면 문장 속에 잘못 베끼거나
        지어낼 여지가 생기므로, 이 메서드의 결과는 LLM 호출 후 답변 문장에
        실제 메뉴 이름이 등장하는지 코드가 직접 대조하는 데만 쓴다."""
        menus = self.db.query(Menu).filter(Menu.business_id == business_id).all()
        return [{"id": str(m.id), "name": m.name, "image_url": m.image_url} for m in menus]


class CouponSearchTool:
    """Master plan §15/§18 - lets Customer/Info AI mention a real, currently
    claimable coupon (never a DRAFT/EXPIRED/exhausted one) so a chat can turn
    into the DIRECT-attribution path: AI 추천 -> 쿠폰 -> 결제."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_claimable(self, business_id: UUID) -> list[dict]:
        coupons = self.db.query(Coupon).filter(Coupon.business_id == business_id).all()
        return [
            {
                "id": str(c.id),
                "title": c.title,
                "description": c.description,
                "discount_type": c.discount_type.value,
                "discount_value": str(c.discount_value),
                "conditions": c.conditions,
            }
            for c in coupons
            if is_coupon_currently_claimable(c)
        ]


class PartnerSearchTool:
    """Master plan §21-23 Expansion AI - candidate pool is every OTHER real
    business already in the DB (claimed or still-unclaimed import rows),
    restricted to a different category (§21's own examples are always
    cross-category: HOTEL->RESTAURANT, RESTAURANT->CAFE, ...). Never invents a
    candidate; distance is only computed when both businesses have real
    coordinates (§29 - no fabricated proximity)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def find_candidates(self, business_id: UUID, limit: int = 20) -> list[dict]:
        target = self.db.get(Business, business_id)
        if target is None:
            return []

        candidates = (
            self.db.query(Business)
            .filter(Business.id != business_id, Business.category != target.category)
            .all()
        )

        scored = []
        for candidate in candidates:
            dist = distance_meters(target.lon, target.lat, candidate.lon, candidate.lat)
            scored.append((dist, candidate))
        # Businesses with known distance come first (nearest first); unknown-distance
        # ones are appended after, in no particular order - still real candidates,
        # just not rankable by proximity.
        scored.sort(key=lambda pair: (pair[0] is None, pair[0]))

        return [
            {
                "id": str(c.id),
                "name": c.name_ko,
                "category": c.category.value,
                "address": c.address,
                "distance_m": round(dist) if dist is not None else None,
                "is_claimed": c.owner_user_id is not None,
            }
            for dist, c in scored[:limit]
        ]

    def decided_relationship_ids(self, business_id: UUID) -> set[UUID]:
        """Pairs the owner has already acted on (invited/accepted/rejected) -
        these should stop being re-suggested. Still-SUGGESTED pairs (no owner
        decision yet) are deliberately NOT included here, so re-running
        analyze can keep refreshing their score/reason as circumstances
        change (§22) instead of going silent after the first run."""
        rows = (
            self.db.query(BusinessRelationship.business_b_id)
            .filter(
                BusinessRelationship.business_a_id == business_id,
                BusinessRelationship.status != PartnerRelationshipStatus.SUGGESTED,
            )
            .all()
        )
        return {row[0] for row in rows}

    def list_accepted_partners(self, business_id: UUID) -> list[dict]:
        """Master plan's "지역 업체" problem (호텔 손님이 카페를 찾는데 연결이
        안 됨) - the fix: Customer/Chef AI may mention these to a VISITOR
        mid-conversation, not just the owner. Only ACCEPTED (mutual, both
        owners agreed - see routers/expansion.py's accept endpoint)
        relationships qualify, in either direction, and only when the other
        business is still ACTIVE - an INVITED-only or now-DISABLED business
        never gets surfaced to someone else's customers."""
        rows = (
            self.db.query(BusinessRelationship)
            .filter(
                BusinessRelationship.status == PartnerRelationshipStatus.ACCEPTED,
                (BusinessRelationship.business_a_id == business_id)
                | (BusinessRelationship.business_b_id == business_id),
            )
            .all()
        )
        partners = []
        for r in rows:
            other = r.business_b if r.business_a_id == business_id else r.business_a
            if other.status != BusinessStatus.ACTIVE:
                continue
            partners.append(
                {
                    "id": str(other.id),
                    "name": other.name_ko,
                    "category": other.category.value,
                    "address": other.address,
                }
            )
        return partners

    # 기획서 16번 - "초기에는 예측치임을 명확히 표시한다"는 마스터플랜 자체의
    # 지시를 따름: 두 상수(관심 전환율/방문 전환율)는 검증된 값이 아니라
    # 업계 평균 수준의 가정일 뿐이고, ESTIMATE_NOTE로 항상 함께 표시된다.
    # 절대 LLM이 만들어내지 않음 - 결정론적 계산이라 재현·검증 가능함
    # (§29/기획서 11번의 "기준을 확인 가능해야 한다"와 동일한 원칙).
    _ESTIMATE_INTEREST_RATE = Decimal("0.20")
    _ESTIMATE_CONVERSION_RATE = Decimal("0.40")
    ESTIMATE_NOTE = (
        "예측치입니다 - 상대 업체가 입력한 월 방문객 수에 관심 전환율 20%, 방문 전환율 40%라는 "
        "업계 평균 수준의 가정을 곱해 계산한 값으로, 검증된 실적이 아닙니다. 실제 제휴 데이터가 "
        "쌓이면 이 가정을 개선할 예정입니다."
    )

    def _average_menu_price(self, business_id: UUID) -> Decimal | None:
        result = self.db.query(func.avg(Menu.price)).filter(Menu.business_id == business_id).scalar()
        return Decimal(result) if result is not None else None

    def estimate_partnership_effect(self, target_business_id: UUID, candidate_business_id: UUID) -> dict | None:
        """None whenever a required real input is missing - the candidate's
        self-reported monthly_visitor_estimate, or the target's own menu
        prices to estimate spend per visit. Never fills a gap with a guess."""
        candidate = self.db.get(Business, candidate_business_id)
        if candidate is None or candidate.profile is None or candidate.profile.monthly_visitor_estimate is None:
            return None
        avg_price = self._average_menu_price(target_business_id)
        if avg_price is None:
            return None

        monthly_visitors = candidate.profile.monthly_visitor_estimate
        interested = int(monthly_visitors * self._ESTIMATE_INTEREST_RATE)
        converted = int(interested * self._ESTIMATE_CONVERSION_RATE)
        revenue = (Decimal(converted) * avg_price).quantize(Decimal("1"))

        return {
            "candidate_monthly_visitors": monthly_visitors,
            "estimated_interested_customers": interested,
            "estimated_converted_visits": converted,
            "estimated_additional_revenue": str(revenue),
            "note": self.ESTIMATE_NOTE,
        }


class PerformanceSummaryTool:
    """§19 - the same real, countable-this-month signals the Performance
    Dashboard endpoint shows, factored out so Manager AI (and the dashboard
    endpoint itself) share one definition instead of two copies of the same
    queries drifting apart."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_summary(self, business_id: UUID) -> dict:
        month_start = current_month_start()

        ai_response_count = (
            self.db.query(AiInteraction)
            .filter(AiInteraction.business_id == business_id, AiInteraction.created_at >= month_start)
            .count()
        )
        coupons_issued = (
            self.db.query(CouponIssue)
            .join(Coupon)
            .filter(Coupon.business_id == business_id, CouponIssue.issued_at >= month_start)
            .count()
        )
        coupons_redeemed = (
            self.db.query(CouponIssue)
            .join(Coupon)
            .filter(
                Coupon.business_id == business_id,
                CouponIssue.status == CouponIssueStatus.REDEEMED,
                CouponIssue.redeemed_at >= month_start,
            )
            .count()
        )
        reservations_this_month = (
            self.db.query(Reservation)
            .filter(Reservation.business_id == business_id, Reservation.created_at >= month_start)
            .count()
        )
        # P1-2 Performance UX - "관심을 보인 횟수"/"방문 확인" 두 숫자는 pilot_
        # analytics.py의 정의를 그대로 재사용한다(직접 다시 계산하지 않는다) -
        # 같은 의미의 숫자가 두 화면에서 서로 다르게 계산되어 어긋나지 않도록.
        recommendation_clicks = _recommendation_clicks_count(self.db, business_id, month_start, None)
        _reservations_created_all, reservations_completed = _reservation_counts(
            self.db, [business_id], month_start, None
        )
        # 기획서 21번 (추천 보상 시스템) - 실제 보상(할인/포인트)을 지급하려면
        # 결제·포인트 인프라가 필요한데 아직 없음(§29 - 지어낼 수 없음).
        # 대신 검증 가능한 실적만: 이 업체가 보낸 초대 링크로 실제 새 업체가
        # 가입한 횟수(전체 기간 누적 - referral_signup_confirmed_at은 §14에서
        # 구축한, 이 업체가 보낸 링크를 통해 실제 claim까지 이어진 것만 기록됨).
        successful_referrals = (
            self.db.query(BusinessRelationship)
            .filter(
                BusinessRelationship.business_a_id == business_id,
                BusinessRelationship.referral_signup_confirmed_at.isnot(None),
            )
            .count()
        )
        # P1-4 - "제안한 업체"는 SUGGESTED(아직 사장님이 아무 결정도 안 한 AI
        # 추천)를 제외한, 실제로 사장님이 [제휴 제안하기]를 눌러 INVITED 이상으로
        # 넘어간 적 있는 업체 수(전체 기간 누적) - PartnerSearchTool.
        # decided_relationship_ids와 동일한 판정 기준(status != SUGGESTED)을
        # 재사용한다.
        partner_invites_sent = (
            self.db.query(BusinessRelationship)
            .filter(
                BusinessRelationship.business_a_id == business_id,
                BusinessRelationship.status != PartnerRelationshipStatus.SUGGESTED,
            )
            .count()
        )
        partner_accepted = (
            self.db.query(BusinessRelationship)
            .filter(
                BusinessRelationship.business_a_id == business_id,
                BusinessRelationship.status == PartnerRelationshipStatus.ACCEPTED,
            )
            .count()
        )
        # 기획서 12번 "가장 성과가 좋았던 기능" - 매출 인과관계까지 증명할 방법은
        # 없으니(§29), 정직하게 "가장 많이 쓰인 기능"(응대 건수 기준)으로 제한한다.
        ai_response_count_by_agent_type = dict(
            self.db.query(AiInteraction.agent_type, func.count())
            .filter(AiInteraction.business_id == business_id, AiInteraction.created_at >= month_start)
            .group_by(AiInteraction.agent_type)
            .all()
        )

        revenue_total = (
            self.db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(Transaction.business_id == business_id, Transaction.occurred_at >= month_start)
            .scalar()
        )
        # §18/기획서 11번 - "AI 연결 매출"이라는 한 숫자로 뭉개지 않고, 어떤
        # 기준(DIRECT/ASSISTED/UNKNOWN)으로 계산했는지 항상 함께 보여준다.
        revenue_rows = (
            self.db.query(Transaction.attribution, func.coalesce(func.sum(Transaction.amount), 0))
            .filter(Transaction.business_id == business_id, Transaction.occurred_at >= month_start)
            .group_by(Transaction.attribution)
            .all()
        )
        revenue_by_attribution = {a.value: Decimal(amt) for a, amt in revenue_rows}
        revenue_direct = revenue_by_attribution.get(TransactionAttribution.DIRECT.value, Decimal(0))
        revenue_assisted = revenue_by_attribution.get(TransactionAttribution.ASSISTED.value, Decimal(0))
        revenue_unknown = revenue_by_attribution.get(TransactionAttribution.UNKNOWN.value, Decimal(0))

        return {
            "period": month_start.strftime("%Y-%m"),
            "ai_response_count": ai_response_count,
            "ai_response_count_by_agent_type": ai_response_count_by_agent_type,
            "coupons_issued": coupons_issued,
            "coupons_redeemed": coupons_redeemed,
            "reservations_this_month": reservations_this_month,
            "recommendation_clicks": recommendation_clicks,
            "visits_confirmed": coupons_redeemed + reservations_completed,
            "successful_referrals": successful_referrals,
            "partner_invites_sent": partner_invites_sent,
            "partner_accepted": partner_accepted,
            # str, not Decimal - this dict also flows straight into
            # ManagerDashboardTool's json.dumps() for the LLM prompt (see
            # coupon_summary's str(discount_value) just below for the same
            # convention); PerformanceResponse coerces the str back to
            # Decimal for the API response.
            "revenue_total": str(Decimal(revenue_total)),
            "revenue_direct": str(revenue_direct),
            "revenue_assisted": str(revenue_assisted),
            "revenue_unknown": str(revenue_unknown),
            "revenue_ai_connected": str(revenue_direct + revenue_assisted),
        }


class ManagerDashboardTool:
    """Master plan §9 Manager AI - Manager doesn't have its own facts, it reads
    everything through the *other* agents'/features' own tools (performance,
    coupons, expansion) and hands the owner one conversational surface instead
    of several separate pages. Every number here is grounded in the exact same
    queries the dedicated pages use - Manager AI never computes its own version
    of a stat (§29 - one source of truth, not two that could disagree)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_dashboard(self, business_id: UUID) -> dict | None:
        business = self.db.get(Business, business_id)
        if business is None:
            return None

        performance = PerformanceSummaryTool(self.db).get_summary(business_id)

        coupons = self.db.query(Coupon).filter(Coupon.business_id == business_id).all()
        coupon_summary = [
            {"title": c.title, "status": c.status.value, "discount_type": c.discount_type.value,
             "discount_value": str(c.discount_value)}
            for c in coupons
        ]

        pending_suggestions = (
            self.db.query(BusinessRelationship)
            .filter(
                BusinessRelationship.business_a_id == business_id,
                BusinessRelationship.status == PartnerRelationshipStatus.SUGGESTED,
            )
            .order_by(BusinessRelationship.score.desc())
            .limit(3)
            .all()
        )

        upcoming_reservations = (
            self.db.query(Reservation)
            .filter(
                Reservation.business_id == business_id,
                Reservation.status.in_([ReservationStatus.REQUESTED, ReservationStatus.CONFIRMED]),
            )
            .order_by(Reservation.reservation_time.asc())
            .limit(10)
            .all()
        )

        return {
            "business_name": business.name_ko,
            "category": business.category.value,
            "status": business.status.value,
            "this_month_performance": performance,
            "coupons": coupon_summary,
            "pending_partner_suggestions": [
                {"name": r.business_b.name_ko, "score": r.score} for r in pending_suggestions
            ],
            "upcoming_reservations": [
                {
                    "customer_name": r.customer_name,
                    "customer_phone": r.customer_phone,
                    "party_size": r.party_size,
                    "reservation_time": r.reservation_time.isoformat(),
                    "status": r.status.value,
                }
                for r in upcoming_reservations
            ],
        }
