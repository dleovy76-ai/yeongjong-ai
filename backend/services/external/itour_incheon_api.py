"""Client for 인천광역시 관광사업체 현황정보 OPEN API (itour.incheon.go.kr).

No API key required - confirmed in the official 활용가이드(서비스 명세): 서비스
Key [없음], WS-Security 없음, 전송 레벨만 SSL. Confirmed live: GET
https://itour.incheon.go.kr/bizapi/rest/search/xml/cityId=04 (영종구) returned
637건 with no auth header at all.

Unlike services/external/sangga_api.py, this API's response has no lon/lat and
no unique business id (only regst_org/busi_mid_lvl_nm/company_nm/tel_no/
road_addr/addr) - confirmed by reading the real XML response, not guessed.
So imported rows never get coordinates, and external_id is synthesized (hash
of name+address) purely for idempotent re-import, not a real external key.

Category mapping below was derived from the real 업종중분류명 values actually
returned for 영종구(cityId=04), not the full company_id code table - 여행사/
카지노/국제회의 같은 B2B 또는 이 플랫폼 목적에 안 맞는 업종은 sangga_api.py의
"범위 밖은 강제 매핑하지 않는다" 원칙과 동일하게 건너뛴다(None 반환)."""

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

from models import BusinessCategory

_BASE_URL = "https://itour.incheon.go.kr/bizapi/rest/search/xml"
_TIMEOUT_SECONDS = 30.0
_EXTERNAL_ID_PREFIX = "itour_incheon"

YEONGJONG_CITY_ID = "04"

_CATEGORY_MAP: dict[str, BusinessCategory] = {
    "외국인관광도시민박업": BusinessCategory.LODGING,
    "호스텔업": BusinessCategory.LODGING,
    "관광호텔업": BusinessCategory.LODGING,
    "가족호텔업": BusinessCategory.LODGING,
    "관광펜션업": BusinessCategory.LODGING,
    "한옥체험업": BusinessCategory.LODGING,
    "휴양콘도미니엄업": BusinessCategory.LODGING,
    "한국전통호텔업": BusinessCategory.LODGING,
    "관광식당업": BusinessCategory.RESTAURANT,
    "일반야영장업": BusinessCategory.EXPERIENCE,
    "자동차야영장업": BusinessCategory.EXPERIENCE,
    "일반관광유람선업": BusinessCategory.EXPERIENCE,
    "전문휴양업": BusinessCategory.EXPERIENCE,
    "기타유원시설업(기타테마파크업)": BusinessCategory.LEISURE,
    "일반유원시설업(일반테마파크업)": BusinessCategory.LEISURE,
    # 관광면세업은 의도적으로 매핑하지 않는다 - 실제로 조회해보니 "풍림명품물산㈜"
    # 등 손님이 찾아갈 수 있는 매장이 아니라 면세품 도매/유통 법인 이름이 나와서
    # (라이브 dry-run으로 확인, 추측 아님), 추천 후보로 쓰면 안 되는 데이터다.
}


class ItourIncheonApiError(RuntimeError):
    pass


@dataclass
class ImportedTourBusiness:
    external_id: str
    name_ko: str
    category: BusinessCategory
    address: str


def _make_external_id(name: str, address: str) -> str:
    digest = hashlib.sha1(f"{name}|{address}".encode("utf-8")).hexdigest()[:16]
    return f"{_EXTERNAL_ID_PREFIX}:{digest}"


def to_imported_business(
    busi_mid_lvl_nm: str, company_nm: str, road_addr: str, addr: str
) -> ImportedTourBusiness | None:
    """None if the row's category is out of scope, or it has no usable name/address."""
    category = _CATEGORY_MAP.get(busi_mid_lvl_nm)
    if category is None:
        return None

    name = company_nm.strip()
    if not name:
        return None

    address = road_addr.strip() or addr.strip()
    if not address:
        return None

    return ImportedTourBusiness(
        external_id=_make_external_id(name, address),
        name_ko=name,
        category=category,
        address=address,
    )


class ItourIncheonApiClient:
    def fetch_by_city(self, city_id: str = YEONGJONG_CITY_ID) -> list[ImportedTourBusiness]:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            response = client.get(f"{_BASE_URL}/cityId={city_id}")
        response.raise_for_status()

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise ItourIncheonApiError(f"인천투어 API 응답 파싱 실패: {exc}") from exc

        results: list[ImportedTourBusiness] = []
        for row in root.findall("TourStatistics"):
            imported = to_imported_business(
                busi_mid_lvl_nm=(row.findtext("busi_mid_lvl_nm") or "").strip(),
                company_nm=(row.findtext("company_nm") or "").strip(),
                road_addr=(row.findtext("road_addr") or "").strip(),
                addr=(row.findtext("addr") or "").strip(),
            )
            if imported is not None:
                results.append(imported)
        return results
