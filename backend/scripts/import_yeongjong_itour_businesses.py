"""One-off/rerunnable import of real registered tourism businesses (숙박/체험/
식당 등) for Yeongjong-gu from 인천광역시 관광사업체 현황정보 OPEN API, as
pre-seeded "unclaimed" listings - same pattern as
scripts/import_yeongjong_businesses.py (소상공인 상가정보 API).

Unlike that script, this source has no lon/lat and no unique business id (see
services/external/itour_incheon_api.py) - external_id is a synthesized hash of
name+address, and rows never get coordinates. Also unlike that script, there's
no "closest N by distance" ranking possible (no coordinates to rank by), so
this caps each category at --limit-per-category by simple list order instead -
still pilot-sized rather than dumping all ~450 matching rows at once.

Usage (from backend/):
    venv/Scripts/python.exe scripts/import_yeongjong_itour_businesses.py [--dry-run]
        [--limit-per-category 15]

Safe to rerun: external_id is stable (hash of name+address), so re-running
just tops up each category toward its limit rather than duplicating rows.
"""

import argparse
import sys

from core.database import SessionLocal
from models import Business, BusinessCategory
from services.external.itour_incheon_api import ImportedTourBusiness, ItourIncheonApiClient

DATA_SOURCE = "인천투어_관광사업체현황정보"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit-per-category", type=int, default=15, help="카테고리별 최대 임포트 건수(파일럿 규모 유지용)"
    )
    parser.add_argument("--dry-run", action="store_true", help="DB에 저장하지 않고 결과만 출력")
    args = parser.parse_args()

    client = ItourIncheonApiClient()
    print("조회 중... (영종구)", file=sys.stderr)
    imported = client.fetch_by_city()
    print(f"카테고리 매핑 대상 {len(imported)}건 (여행사/카지노 등 범위 밖 업종 제외)", file=sys.stderr)

    db = SessionLocal()
    try:
        existing_ids = {
            row[0] for row in db.query(Business.external_id).filter(Business.external_id.isnot(None)).all()
        }
        already_imported_count = {
            category: db.query(Business)
            .filter(Business.data_source == DATA_SOURCE, Business.category == category)
            .count()
            for category in BusinessCategory
        }

        by_category: dict[BusinessCategory, list[ImportedTourBusiness]] = {c: [] for c in BusinessCategory}
        for item in imported:
            by_category[item.category].append(item)

        to_insert: list[ImportedTourBusiness] = []
        seen_in_this_run: set[str] = set()
        for category, items in by_category.items():
            needed = max(0, args.limit_per_category - already_imported_count[category])
            picked = 0
            for item in items:
                if picked >= needed:
                    break
                if item.external_id in existing_ids or item.external_id in seen_in_this_run:
                    continue
                to_insert.append(item)
                seen_in_this_run.add(item.external_id)
                picked += 1

        print(f"신규 임포트 대상 (기존 보유분·카테고리별 상한 반영): {len(to_insert)}건", file=sys.stderr)
        for category in BusinessCategory:
            count = sum(1 for i in to_insert if i.category == category)
            already = already_imported_count[category]
            if count or already:
                print(
                    f"  - {category.value}: 기존 {already}건 + 신규 {count}건 "
                    f"= {already + count}/{args.limit_per_category}건",
                    file=sys.stderr,
                )

        if args.dry_run:
            for item in to_insert:
                print(f"  [dry-run] {item.category.value}: {item.name_ko} ({item.address})")
            print("dry-run: DB에 저장하지 않았습니다.", file=sys.stderr)
            return

        for item in to_insert:
            db.add(
                Business(
                    owner_user_id=None,
                    name_ko=item.name_ko,
                    category=item.category,
                    address=item.address,
                    data_source=DATA_SOURCE,
                    external_id=item.external_id,
                )
            )
        db.commit()
        print(f"완료: {len(to_insert)}건 저장", file=sys.stderr)
    finally:
        db.close()


if __name__ == "__main__":
    main()
