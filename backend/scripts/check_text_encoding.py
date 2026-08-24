"""읽기 전용 데이터 품질 점검 - Business/BusinessProfile/Menu의 텍스트
필드에 lone surrogate 등 손상된 인코딩이 있는지 스캔한다.

PILOT AUDIT TASK 1의 결과물 - 최초 감사에서 "영종면옥 텍스트가 깨졌다"고
지적한 건 실제로는 로컬 터미널 codepage 표시 오류였고(2026-08-25
railway ssh로 DB 원본을 직접 확인해 전부 정상임을 확인), 진짜 손상은
없었다. 하지만 앞으로 재발하지 않는지 주기적으로 확인할 수 있는 도구는
필요해서 만든다 - Pydantic 입력 검증(core/text_validation.py)은 새로
들어오는 값만 막고, 이미 DB에 있는 값은 못 본다.

절대 데이터를 수정하지 않는다 - 순수 조회/리포트 전용.

사용법 (backend/에서):
    venv/Scripts/python.exe scripts/check_text_encoding.py
"""

import sys

from core.database import SessionLocal
from models import Business, BusinessProfile, Menu

_SURROGATE_RANGE = range(0xD800, 0xE000)


def _bad_reason(value: str) -> str | None:
    for ch in value:
        if ord(ch) in _SURROGATE_RANGE:
            return f"lone surrogate U+{ord(ch):04X}"
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        return f"not utf-8 encodable ({exc})"
    return None


def main() -> None:
    db = SessionLocal()
    problems: list[str] = []
    try:
        for business in db.query(Business).all():
            for field in ("name_ko", "name_en", "name_zh", "address", "phone"):
                value = getattr(business, field)
                if isinstance(value, str):
                    reason = _bad_reason(value)
                    if reason:
                        problems.append(f"Business {business.id}.{field}: {reason}")

        for profile in db.query(BusinessProfile).all():
            for field in (
                "description",
                "brand_tone",
                "holiday",
                "parking",
                "pet_policy",
                "reservation_policy",
                "takeout_policy",
            ):
                value = getattr(profile, field)
                if isinstance(value, str):
                    reason = _bad_reason(value)
                    if reason:
                        problems.append(f"BusinessProfile {profile.business_id}.{field}: {reason}")

        for menu in db.query(Menu).all():
            for field in ("name", "description", "allergy_info"):
                value = getattr(menu, field)
                if isinstance(value, str):
                    reason = _bad_reason(value)
                    if reason:
                        problems.append(f"Menu {menu.id}.{field}: {reason}")
    finally:
        db.close()

    if problems:
        print(f"손상된 텍스트 {len(problems)}건 발견:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(1)

    print("이상 없음 - 손상된 텍스트를 찾지 못했습니다.", file=sys.stderr)


if __name__ == "__main__":
    main()
