"""Client for NAVER API HUB's local-search endpoint (지역 검색), used only to
verify a business is really registered with Naver before handing the owner a
ready-made 네이버 검색 link to confirm - never to scrape or store review
counts/hours/menus, which this endpoint doesn't return at all.

Endpoint discovered live (not guessed): the classic openapi.naver.com/
X-Naver-Client-Id headers 401'd for a NAVER API HUB (NCP) issued key - the
working combination is naverapihub.apigw.ntruss.com with X-NCP-APIGW-API-KEY*
headers, confirmed against a real business (see commit history).
"""

import re
from dataclasses import dataclass

import httpx

from core.config import settings

_BASE_URL = "https://naverapihub.apigw.ntruss.com/search/v1/local"
_TIMEOUT_SECONDS = 10.0
_TAG_RE = re.compile(r"<.*?>")


class NaverApiConfigurationError(RuntimeError):
    pass


@dataclass
class NaverLocalResult:
    title: str
    road_address: str
    category: str
    lon: float | None
    lat: float | None


def _strip_tags(text: str) -> str:
    return _TAG_RE.sub("", text)


class NaverLocalApiClient:
    def __init__(self, client_id: str | None = None, client_secret: str | None = None) -> None:
        self.client_id = client_id or settings.naver_client_id
        self.client_secret = client_secret or settings.naver_client_secret
        if not self.client_id or not self.client_secret:
            raise NaverApiConfigurationError("NAVER_CLIENT_ID/NAVER_CLIENT_SECRET가 설정되지 않았습니다.")

    def search(self, query: str, display: int = 5) -> list[NaverLocalResult]:
        headers = {
            "X-NCP-APIGW-API-KEY-ID": self.client_id,
            "X-NCP-APIGW-API-KEY": self.client_secret,
        }
        params = {"query": query, "display": display}
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            response = client.get(_BASE_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("items", []):
            road_address = item.get("roadAddress") or item.get("address")
            if not road_address:
                continue
            results.append(
                NaverLocalResult(
                    title=_strip_tags(item.get("title", "")),
                    road_address=road_address,
                    category=item.get("category", ""),
                    lon=_parse_coord(item.get("mapx")),
                    lat=_parse_coord(item.get("mapy")),
                )
            )
        return results


def _parse_coord(raw: object) -> float | None:
    """mapx/mapy come back as integer strings scaled by 1e7 (e.g. "1265785881"
    -> 126.5785881) - confirmed live against a known real address, not
    documented anywhere official that we could find."""
    if raw is None:
        return None
    try:
        return int(raw) / 1e7
    except (TypeError, ValueError):
        return None
