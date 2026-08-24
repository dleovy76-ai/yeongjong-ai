"""Client for 공공데이터포털 소상공인시장진흥공단_상가(상권)정보_API
(https://www.data.go.kr/data/15012005/openapi.do) - real, verified registered-
business data, used to pre-seed claimable listings (see routers/businesses.py
claim flow) rather than fabricating a business directory.

Category mapping below was derived from actually calling largeUpjongList /
middleUpjongList against the live API and reading the real code table, not
guessed:
  I1 (숙박, all mid-categories)                    -> LODGING
  I2 (음식) except I212 (비알코올)                  -> RESTAURANT
  I2 mid-category I212 (비알코올/카페)              -> CAFE
  G2 (소매, all mid-categories)                     -> SHOPPING
  R1 mid-category R103 (스포츠 서비스), R104 (유원지·오락) -> LEISURE
  R1 mid-category R101 (창작·예술), R102 (도서관·사적지), \
or any other/unknown R1 mid-code                    -> EXPERIENCE
Anything else (의료, 교육, 금융...) is out of scope for this platform's
target categories (master plan §3, expanded with SHOPPING/LEISURE) and is
skipped, not force-mapped.
"""

from dataclasses import dataclass

import httpx

from core.config import settings
from models import BusinessCategory

_BASE_URL = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius"
_TIMEOUT_SECONDS = 30.0

_CAFE_MIDDLE_CODE = "I212"
_LODGING_LARGE_CODE = "I1"
_FOOD_LARGE_CODE = "I2"
_SHOPPING_LARGE_CODE = "G2"
_ARTS_SPORTS_LARGE_CODE = "R1"
_LEISURE_MIDDLE_CODES = {"R103", "R104"}


class SanggaApiConfigurationError(RuntimeError):
    pass


class SanggaApiError(RuntimeError):
    pass


def map_category(inds_lcls_cd: str, inds_mcls_cd: str) -> BusinessCategory | None:
    """Returns None for anything outside this platform's target categories -
    callers should skip the row, not force a mapping."""
    if inds_lcls_cd == _LODGING_LARGE_CODE:
        return BusinessCategory.LODGING
    if inds_lcls_cd == _FOOD_LARGE_CODE:
        return BusinessCategory.CAFE if inds_mcls_cd == _CAFE_MIDDLE_CODE else BusinessCategory.RESTAURANT
    if inds_lcls_cd == _SHOPPING_LARGE_CODE:
        return BusinessCategory.SHOPPING
    if inds_lcls_cd == _ARTS_SPORTS_LARGE_CODE:
        return BusinessCategory.LEISURE if inds_mcls_cd in _LEISURE_MIDDLE_CODES else BusinessCategory.EXPERIENCE
    return None


@dataclass
class ImportedStore:
    external_id: str
    name_ko: str
    category: BusinessCategory
    address: str
    lon: float | None
    lat: float | None


def to_imported_store(item: dict) -> ImportedStore | None:
    """None if the row's category is out of scope, or it has no usable address."""
    category = map_category(item.get("indsLclsCd", ""), item.get("indsMclsCd", ""))
    if category is None:
        return None

    address = item.get("rdnmAdr") or item.get("lnoAdr")
    if not address:
        return None

    name = item.get("bizesNm", "").strip()
    branch = (item.get("brchNm") or "").strip()
    if branch:
        name = f"{name} {branch}"
    if not name:
        return None

    return ImportedStore(
        external_id=item["bizesId"],
        name_ko=name,
        category=category,
        address=address,
        lon=item.get("lon"),
        lat=item.get("lat"),
    )


class SanggaApiClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.data_go_kr_api_key
        if not self.api_key:
            raise SanggaApiConfigurationError("DATA_GO_KR_API_KEY가 설정되지 않았습니다.")

    def fetch_page(
        self, *, cx: float, cy: float, radius: int, page_no: int, num_of_rows: int = 1000
    ) -> tuple[list[dict], int]:
        """Returns (items, total_count) for one page. radius is in meters."""
        params = {
            "serviceKey": self.api_key,
            "type": "json",
            "cx": cx,
            "cy": cy,
            "radius": radius,
            "pageNo": page_no,
            "numOfRows": num_of_rows,
        }
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            response = client.get(_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        result_code = data.get("header", {}).get("resultCode")
        if result_code != "00":
            raise SanggaApiError(f"상가업소정보 API 오류: {data.get('header', {})}")

        body = data.get("body", {})
        return body.get("items", []) or [], body.get("totalCount", 0)

    def fetch_all(self, *, cx: float, cy: float, radius: int, num_of_rows: int = 1000) -> list[dict]:
        """Pages through every result for one center point/radius."""
        all_items: list[dict] = []
        page_no = 1
        while True:
            items, total_count = self.fetch_page(
                cx=cx, cy=cy, radius=radius, page_no=page_no, num_of_rows=num_of_rows
            )
            all_items.extend(items)
            if len(all_items) >= total_count or not items:
                break
            page_no += 1
        return all_items
