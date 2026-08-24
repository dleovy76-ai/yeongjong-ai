"""로컬/스테이징 전용 데모 파일럿 시드 스크립트.

실제 파일럿 업체를 확보하기 전에, 전체 루프(가입 → AI 직원 → 고객 응대 →
추천 → 쿠폰/예약 → 방문 → 거래 → 성과측정 → 확장AI → 업체 간 제휴)가
기술적으로 잘 도는지 미리 점검하기 위한 것.

절대로 실제 파일럿 실적처럼 취급하거나 프로덕션 KPI/업체 수에 반영해서는
안 된다(§29 - 지어낸 사실 금지. 기획서 30번의 "실제 숫자로 증명" 원칙과
정면으로 충돌하는 사용법이다).

안전장치:
- ENVIRONMENT=production이면(core.config.settings.is_production) 즉시 종료.
- 모든 데이터에 data_source="DEMO_SEED"를 남겨 실제 데이터와 절대 섞이지
  않게 하고, --wipe로 한 번에 지울 수 있게 한다.
- 소유자/손님 계정 이메일은 전부 @demo.yeongjong-ai.local 고정 도메인.

사용법 (backend/에서, 반드시 로컬 DB를 보고 있는 상태에서 실행):
    venv/Scripts/python.exe scripts/seed_demo_pilot.py
    venv/Scripts/python.exe scripts/seed_demo_pilot.py --wipe   # 데모 데이터만 전부 삭제

재실행 안전: external_id가 이미 있으면 새로 만들지 않고 건너뛴다.
"""

import argparse
import secrets
import string
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from core.config import settings
from core.database import SessionLocal
from core.security import hash_password
from models import (
    AiInteraction,
    Business,
    BusinessCategory,
    BusinessProfile,
    BusinessRelationship,
    BusinessStatus,
    Coupon,
    CouponDiscountType,
    CouponIssue,
    CouponIssueStatus,
    CouponStatus,
    Menu,
    PartnerRelationshipStatus,
    Reservation,
    ReservationStatus,
    Transaction,
    TransactionAttribution,
    User,
    UserRole,
)

DATA_SOURCE = "DEMO_SEED"
EMAIL_DOMAIN = "demo.yeongjong-ai.local"
DEMO_PASSWORD = "demopassword123"

# 영종도 중심점(import_yeongjong_businesses.py와 동일) 근처에 클러스터를
# 만든다 - A/B/C는 서로 300m 이내(admin.py의 NEAR 임계값)라 그래프에서
# NEAR로 뜨고, D/E는 멀리 떨어뜨려 대조군으로 둔다.
_CX, _CY = 126.5419, 37.4936

_BUSINESSES = [
    {
        "external_id": "demo-0001",
        "name_ko": "데모식당A",
        "category": BusinessCategory.RESTAURANT,
        "lon": _CX,
        "lat": _CY,
        "menu": ("대표 정식", Decimal("12000"), "이 가게의 대표 메뉴"),
        "coupon": ("첫 방문 10% 할인", CouponDiscountType.PERCENTAGE, Decimal("10")),
    },
    {
        "external_id": "demo-0002",
        "name_ko": "데모식당B",
        "category": BusinessCategory.RESTAURANT,
        "lon": _CX + 0.0017,
        "lat": _CY,
        "menu": ("해물찜", Decimal("35000"), "2인 기준"),
        "coupon": ("점심 특선 2천원 할인", CouponDiscountType.FIXED_AMOUNT, Decimal("2000")),
    },
    {
        "external_id": "demo-0003",
        "name_ko": "데모카페C",
        "category": BusinessCategory.CAFE,
        "lon": _CX,
        "lat": _CY + 0.0018,
        "menu": ("바다전망 아메리카노", Decimal("5500"), None),
        "coupon": ("음료 15% 할인", CouponDiscountType.PERCENTAGE, Decimal("15")),
    },
    {
        "external_id": "demo-0004",
        "name_ko": "데모숙소D",
        "category": BusinessCategory.LODGING,
        "lon": _CX + 0.017,
        "lat": _CY,
        "menu": None,
        "coupon": None,
    },
    {
        "external_id": "demo-0005",
        "name_ko": "데모체험E",
        "category": BusinessCategory.EXPERIENCE,
        "lon": _CX,
        "lat": _CY - 0.018,
        "menu": None,
        "coupon": None,
    },
]

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))


def _get_or_create_owner(db, index: int) -> User:
    email = f"demo-owner-{index}@{EMAIL_DOMAIN}"
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            role=UserRole.BUSINESS_OWNER,
            name=f"데모사장{index}",
        )
        db.add(user)
        db.flush()
    return user


def _get_or_create_customer(db) -> User:
    email = f"demo-customer@{EMAIL_DOMAIN}"
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            role=UserRole.CUSTOMER,
            name="데모손님",
        )
        db.add(user)
        db.flush()
    return user


def seed(db) -> None:
    customer = _get_or_create_customer(db)
    db.flush()

    created = []
    for i, spec in enumerate(_BUSINESSES, start=1):
        existing = db.query(Business).filter(Business.external_id == spec["external_id"]).first()
        if existing is not None:
            created.append(existing)
            print(f"이미 존재, 건너뜀: {spec['name_ko']}", file=sys.stderr)
            continue

        owner = _get_or_create_owner(db, i)
        business = Business(
            owner_user_id=owner.id,
            name_ko=spec["name_ko"],
            category=spec["category"],
            address="인천 중구 영종동 (데모 주소)",
            status=BusinessStatus.ACTIVE,
            data_source=DATA_SOURCE,
            external_id=spec["external_id"],
            lon=spec["lon"],
            lat=spec["lat"],
        )
        db.add(business)
        db.flush()

        db.add(
            BusinessProfile(
                business_id=business.id,
                description=f"{spec['name_ko']}는 데모 시드로 생성된 가상 업체입니다 (실제 업체 아님).",
                brand_tone="친근하고 편안한 말투",
                monthly_visitor_estimate=500,
            )
        )

        if spec["menu"] is not None:
            name, price, description = spec["menu"]
            db.add(
                Menu(
                    business_id=business.id,
                    name=name,
                    price=price,
                    description=description,
                    is_signature=True,
                )
            )

        coupon = None
        if spec["coupon"] is not None:
            title, discount_type, discount_value = spec["coupon"]
            coupon = Coupon(
                business_id=business.id,
                title=title,
                discount_type=discount_type,
                discount_value=discount_value,
                status=CouponStatus.ACTIVE,
            )
            db.add(coupon)
            db.flush()

        db.add(
            AiInteraction(
                business_id=business.id,
                agent_type="customer",
                user_message="영업시간이 어떻게 되나요?",
                reply="데모 응답입니다 (실제 AI 호출 아님).",
            )
        )

        if coupon is not None:
            # demo-0001(데모식당A) 쿠폰만 데모 손님 계정에 연결 - 기획서
            # 28번 "내 이력"이 실제로 채워지는지 함께 점검하기 위함.
            issue = CouponIssue(
                coupon_id=coupon.id,
                code=_generate_code(),
                status=CouponIssueStatus.REDEEMED,
                customer_user_id=customer.id if spec["external_id"] == "demo-0001" else None,
            )
            issue.redeemed_at = datetime.now(timezone.utc)
            db.add(issue)
            db.flush()
            db.add(
                Transaction(
                    business_id=business.id,
                    coupon_issue_id=issue.id,
                    amount=Decimal("15000"),
                    attribution=TransactionAttribution.DIRECT,
                    occurred_at=datetime.now(timezone.utc),
                    memo="데모 시드 거래",
                )
            )

        reservation = Reservation(
            business_id=business.id,
            customer_name="데모손님",
            customer_phone="010-0000-0000",
            reservation_time=datetime.now(timezone.utc) + timedelta(days=1),
            party_size=2,
            status=ReservationStatus.CONFIRMED,
            customer_user_id=customer.id if spec["external_id"] == "demo-0003" else None,
        )
        db.add(reservation)

        created.append(business)
        print(f"생성됨: {spec['name_ko']}", file=sys.stderr)

    db.flush()

    # 데모숙소D -> 데모카페C 로 ACCEPTED 파트너 관계 하나 (§13-18 예시와 동일한
    # 모양) - 실제 ExpansionAgent 분석을 거치지 않고 그래프/프론트 렌더링을
    # 점검하기 위한 하드코딩. score/reason에 데모임을 명시해 실제 분석 결과와
    # 혼동되지 않게 한다.
    lodging = next((b for b in created if b.external_id == "demo-0004"), None)
    cafe = next((b for b in created if b.external_id == "demo-0003"), None)
    if lodging is not None and cafe is not None:
        existing_rel = (
            db.query(BusinessRelationship)
            .filter(
                BusinessRelationship.business_a_id == lodging.id,
                BusinessRelationship.business_b_id == cafe.id,
            )
            .first()
        )
        if existing_rel is None:
            db.add(
                BusinessRelationship(
                    business_a_id=lodging.id,
                    business_b_id=cafe.id,
                    score=90,
                    reason="데모 시드 데이터 - 실제 ExpansionAI 분석 결과 아님",
                    status=PartnerRelationshipStatus.ACCEPTED,
                )
            )

    print(f"\n완료. 데모 사장님 로그인: demo-owner-1@{EMAIL_DOMAIN} / {DEMO_PASSWORD}", file=sys.stderr)
    print(f"데모 손님 로그인: demo-customer@{EMAIL_DOMAIN} / {DEMO_PASSWORD}", file=sys.stderr)
    print("정리하려면: python scripts/seed_demo_pilot.py --wipe", file=sys.stderr)


def wipe(db) -> None:
    business_ids = [b.id for b in db.query(Business).filter(Business.data_source == DATA_SOURCE).all()]
    if business_ids:
        # Query.delete()는 벌크 SQL이라 모델의 cascade="all, delete-orphan"이
        # 적용되지 않는다 - FK를 가진 자식 테이블을 참조 순서 역순으로 직접
        # 지워야 한다 (Transaction/AiInteraction/BusinessRelationship은 이미
        # business_id를 직접 갖고 있어 그대로 두고, CouponIssue는 coupon_id를
        # 통해서만 business에 연결되므로 서브쿼리로 찾는다).
        coupon_ids = [
            c.id for c in db.query(Coupon.id).filter(Coupon.business_id.in_(business_ids)).all()
        ]
        db.query(Transaction).filter(Transaction.business_id.in_(business_ids)).delete(synchronize_session=False)
        db.query(AiInteraction).filter(AiInteraction.business_id.in_(business_ids)).delete(
            synchronize_session=False
        )
        db.query(BusinessRelationship).filter(
            BusinessRelationship.business_a_id.in_(business_ids)
            | BusinessRelationship.business_b_id.in_(business_ids)
        ).delete(synchronize_session=False)
        if coupon_ids:
            db.query(CouponIssue).filter(CouponIssue.coupon_id.in_(coupon_ids)).delete(synchronize_session=False)
        db.query(Coupon).filter(Coupon.business_id.in_(business_ids)).delete(synchronize_session=False)
        db.query(Reservation).filter(Reservation.business_id.in_(business_ids)).delete(synchronize_session=False)
        db.query(Menu).filter(Menu.business_id.in_(business_ids)).delete(synchronize_session=False)
        db.query(BusinessProfile).filter(BusinessProfile.business_id.in_(business_ids)).delete(
            synchronize_session=False
        )
        db.query(Business).filter(Business.id.in_(business_ids)).delete(synchronize_session=False)

    db.query(User).filter(User.email.like(f"%@{EMAIL_DOMAIN}")).delete(synchronize_session=False)
    print(f"데모 데이터 {len(business_ids)}개 업체 및 관련 데이터 삭제 완료.", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wipe", action="store_true", help="데모 데이터를 생성하지 않고 전부 삭제")
    args = parser.parse_args()

    if settings.is_production:
        print(
            "ENVIRONMENT=production 입니다. 데모 시드는 로컬/스테이징에서만 실행하세요.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    db = SessionLocal()
    try:
        if args.wipe:
            wipe(db)
        else:
            seed(db)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
