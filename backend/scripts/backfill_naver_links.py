"""One-off: for every business with a profile.naver_place_url already saved
in the OLD single-URL format (map.naver.com pin), re-run the real Naver
Local API lookup and populate BOTH naver_place_url (customer-facing search
results link) and naver_map_url (owner-facing verification pin) using the
current dual-URL logic in routers/businesses.py - so already-connected
owners don't have to redo the "다시 찾기" flow by hand.

Safe to rerun: only touches rows where naver_place_url still contains
"map.naver.com" (the tell-tale sign it predates the naver_url/map_url
split); rows already migrated are left untouched.

Usage (from backend/, via Railway Console or locally):
    PYTHONPATH=. venv/Scripts/python.exe scripts/backfill_naver_links.py
"""

import sys

import httpx

from core.database import SessionLocal
from models import Business, BusinessProfile
from routers.businesses import _map_url, _naver_search_url, _normalize_address
from services.external.naver_local_api import NaverApiConfigurationError, NaverLocalApiClient


def main() -> None:
    db = SessionLocal()
    try:
        client = NaverLocalApiClient()
    except NaverApiConfigurationError as exc:
        print(f"네이버 API 설정이 없습니다: {exc}", file=sys.stderr)
        raise SystemExit(1)

    try:
        rows = (
            db.query(BusinessProfile)
            .join(Business, Business.id == BusinessProfile.business_id)
            .filter(BusinessProfile.naver_place_url.ilike("%map.naver.com%"))
            .all()
        )
        print(f"옛날 형식 링크 {len(rows)}건 발견", file=sys.stderr)

        for profile in rows:
            business = profile.business
            normalized_address = _normalize_address(business.address)
            try:
                results = client.search(f"{business.name_ko} {business.address}")
            except httpx.HTTPError as exc:
                print(f"- {business.name_ko}: 네이버 검색 실패, 건너뜀 ({exc})", file=sys.stderr)
                continue

            match = None
            for result in results:
                normalized_result = _normalize_address(result.road_address)
                if normalized_address in normalized_result or normalized_result in normalized_address:
                    match = result
                    break

            if match is not None:
                profile.naver_place_url = _naver_search_url(match.title)
                profile.naver_map_url = _map_url(match.title, match.lon, match.lat, match.road_address)
                print(f"- {business.name_ko}: 네이버에서 재확인됨, 갱신", file=sys.stderr)
            else:
                profile.naver_place_url = _naver_search_url(business.name_ko)
                profile.naver_map_url = _map_url(business.name_ko, business.lon, business.lat, business.address)
                print(f"- {business.name_ko}: 네이버에서 재확인 안 됨, 업체 정보 기준으로 갱신", file=sys.stderr)

        db.commit()
        print("완료", file=sys.stderr)
    finally:
        db.close()


if __name__ == "__main__":
    main()
