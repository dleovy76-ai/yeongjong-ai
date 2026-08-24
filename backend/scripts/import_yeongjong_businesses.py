"""One-off/rerunnable import of real registered businesses in Yeongjong-do from
공공데이터포털 소상공인시장진흥공단_상가(상권)정보_API, as pre-seeded "unclaimed"
listings (see routers/businesses.py claim flow / models.Business.owner_user_id
nullable + data_source/external_id).

Usage (from backend/):
    venv/Scripts/python.exe scripts/import_yeongjong_businesses.py [--dry-run]
        [--cx 126.5419] [--cy 37.4936] [--radius 5000]
        [--restaurant-n 10] [--cafe-n 10] [--lodging-n 5] [--experience-n 5]
        [--shopping-n 0] [--leisure-n 0]

Defaults to master plan §39's exact pilot composition (10 음식점/10 카페/
5 숙박/5 체험·관광 = 30), picking the N closest-to-center stores per category
rather than importing everything in range - real data (never fabricated), but
pilot-sized rather than dumping thousands of rows.

Safe to rerun: tops up each category to its target count rather than always
inserting N more - existing rows (claimed or not) are never touched. This
matters because the underlying API's result ordering isn't stable across
calls (confirmed live: two back-to-back runs with identical parameters
returned different specific items, though the same total count) - re-running
naively re-picked a different "closest N" each time and just kept adding more
rows. Counting what's already imported per category before deciding how many
more to fetch avoids that regardless of the API's ordering behavior.
"""

import argparse
import math
import sys

from core.database import SessionLocal
from models import Business, BusinessCategory
from services.external.sangga_api import ImportedStore, SanggaApiClient, to_imported_store

DATA_SOURCE = "공공데이터포털_소상공인시장진흥공단_상가업소정보"

# Central Yeongjong-do point (운서/중산동 인근), verified live to return real
# results in "영종구" - see commit history for the discovery session.
_DEFAULT_CX = 126.5419
_DEFAULT_CY = 37.4936
_DEFAULT_RADIUS = 5000


def _distance_meters(cx: float, cy: float, lon: float | None, lat: float | None) -> float:
    if lon is None or lat is None:
        return math.inf
    # Equirectangular approximation - plenty accurate at a few-km scale and
    # avoids pulling in a geo library for a one-off ranking script.
    lat_rad = math.radians((cy + lat) / 2)
    dx = (lon - cx) * math.cos(lat_rad)
    dy = lat - cy
    return math.sqrt(dx * dx + dy * dy) * 111_320


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cx", type=float, default=_DEFAULT_CX, help="중심 경도")
    parser.add_argument("--cy", type=float, default=_DEFAULT_CY, help="중심 위도")
    parser.add_argument("--radius", type=int, default=_DEFAULT_RADIUS, help="반경(m)")
    parser.add_argument("--restaurant-n", type=int, default=10)
    parser.add_argument("--cafe-n", type=int, default=10)
    parser.add_argument("--lodging-n", type=int, default=5)
    parser.add_argument("--experience-n", type=int, default=5)
    parser.add_argument("--shopping-n", type=int, default=0, help="§3 확장: 소매(G2) - 기본값 0(옵트인)")
    parser.add_argument(
        "--leisure-n", type=int, default=0, help="§3 확장: 스포츠서비스·유원지오락(R103/R104) - 기본값 0(옵트인)"
    )
    parser.add_argument("--dry-run", action="store_true", help="DB에 저장하지 않고 결과만 출력")
    args = parser.parse_args()

    sample_size = {
        BusinessCategory.RESTAURANT: args.restaurant_n,
        BusinessCategory.CAFE: args.cafe_n,
        BusinessCategory.LODGING: args.lodging_n,
        BusinessCategory.EXPERIENCE: args.experience_n,
        BusinessCategory.SHOPPING: args.shopping_n,
        BusinessCategory.LEISURE: args.leisure_n,
    }

    client = SanggaApiClient()
    print(f"조회 중... cx={args.cx} cy={args.cy} radius={args.radius}m", file=sys.stderr)
    raw_items = client.fetch_all(cx=args.cx, cy=args.cy, radius=args.radius)
    print(f"API 응답 {len(raw_items)}건", file=sys.stderr)

    by_category: dict[BusinessCategory, list[ImportedStore]] = {c: [] for c in sample_size}
    out_of_scope = 0
    for item in raw_items:
        store = to_imported_store(item)
        if store is None:
            out_of_scope += 1
        else:
            by_category[store.category].append(store)

    db = SessionLocal()
    try:
        existing_ids = {
            row[0] for row in db.query(Business.external_id).filter(Business.external_id.isnot(None)).all()
        }
        already_imported_count = {
            category: db.query(Business)
            .filter(Business.data_source == DATA_SOURCE, Business.category == category)
            .count()
            for category in sample_size
        }

        to_insert: list[ImportedStore] = []
        for category, stores in by_category.items():
            needed = max(0, sample_size[category] - already_imported_count[category])
            stores.sort(key=lambda s: _distance_meters(args.cx, args.cy, s.lon, s.lat))
            picked = 0
            for store in stores:
                if picked >= needed:
                    break
                if store.external_id in existing_ids:
                    continue
                to_insert.append(store)
                picked += 1

        print(f"범위 밖 업종 제외: {out_of_scope}건", file=sys.stderr)
        print(f"임포트 대상 (기존 보유분 제외, 목표까지 부족한 만큼만): {len(to_insert)}건", file=sys.stderr)
        for category in sample_size:
            count = sum(1 for s in to_insert if s.category == category)
            already = already_imported_count[category]
            print(
                f"  - {category.value}: 기존 {already}건 + 신규 {count}건 "
                f"= {already + count}/{sample_size[category]}건",
                file=sys.stderr,
            )

        if args.dry_run:
            for store in to_insert:
                print(f"  [dry-run] {store.category.value}: {store.name_ko} ({store.address})")
            print("dry-run: DB에 저장하지 않았습니다.", file=sys.stderr)
            return

        for store in to_insert:
            db.add(
                Business(
                    owner_user_id=None,
                    name_ko=store.name_ko,
                    category=store.category,
                    address=store.address,
                    data_source=DATA_SOURCE,
                    external_id=store.external_id,
                    lon=store.lon,
                    lat=store.lat,
                )
            )
        db.commit()
        print(f"완료: {len(to_insert)}건 저장", file=sys.stderr)
    finally:
        db.close()


if __name__ == "__main__":
    main()
