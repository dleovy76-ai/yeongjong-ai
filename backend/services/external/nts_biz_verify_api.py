"""Client for 국세청_사업자등록정보 진위확인 및 상태조회 서비스 (공공데이터포털/
odcloud.kr), used at business claim time (routers/businesses.py claim_business)
to confirm the person claiming a business really controls its real, actively
registered 사업자등록번호 - rather than accepting any logged-in owner account's
word for it (claim_business previously had no verification at all).

Request/response contract confirmed by reading the reference client's source
(github.com/WooilJeong/PublicDataReader, PublicDataPortal/nts.py) since the
portal's own page doesn't render a plain-text spec - not guessed."""

import urllib.parse

import httpx

from core.config import settings

_VALIDATE_URL = "https://api.odcloud.kr/api/nts-businessman/v1/validate"
_TIMEOUT_SECONDS = 10.0
_MATCH_CODE = "01"


class NtsBizVerifyConfigurationError(RuntimeError):
    pass


class NtsBizVerifyClient:
    def __init__(self, service_key: str | None = None) -> None:
        self.service_key = service_key or settings.nts_biz_verify_api_key
        if not self.service_key:
            raise NtsBizVerifyConfigurationError("NTS_BIZ_VERIFY_API_KEY가 설정되지 않았습니다.")

    def verify(self, *, business_registration_number: str, representative_name: str, start_date: str) -> bool:
        """business_registration_number: 사업자등록번호(숫자만), representative_name:
        대표자명, start_date: 개업일자(YYYYMMDD). 국세청 등록 정보와 실제로 일치하면
        (valid == "01") True, 그 외(불일치/확인불가)는 False."""
        # data.go.kr issues this key URL-encoded (%2F, %3D, ...) for pasting into a
        # URL directly - decode it first or it gets double-encoded as a query param.
        params = {"serviceKey": urllib.parse.unquote(self.service_key)}
        body = {
            "businesses": [
                {
                    "b_no": business_registration_number,
                    "start_dt": start_date,
                    "p_nm": representative_name,
                }
            ]
        }
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            response = client.post(_VALIDATE_URL, params=params, json=body)
        response.raise_for_status()
        data = response.json().get("data") or []
        if not data:
            return False
        return data[0].get("valid") == _MATCH_CODE
