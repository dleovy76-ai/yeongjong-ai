import httpx
import pytest

from services.external.nts_biz_verify_api import NtsBizVerifyClient, NtsBizVerifyConfigurationError

_FAKE_KEY = "fake-service-key"


def _client() -> NtsBizVerifyClient:
    return NtsBizVerifyClient(service_key=_FAKE_KEY)


def test_verify_returns_true_when_valid_code_01(monkeypatch):
    def fake_post(self, url, *, params, json):
        assert url == "https://api.odcloud.kr/api/nts-businessman/v1/validate"
        assert params == {"serviceKey": _FAKE_KEY}
        assert json == {"businesses": [{"b_no": "1234567890", "start_dt": "20200101", "p_nm": "김사장"}]}
        return httpx.Response(
            200,
            json={"data": [{"b_no": "1234567890", "valid": "01", "valid_msg": "일치"}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = _client().verify(
        business_registration_number="1234567890", representative_name="김사장", start_date="20200101"
    )
    assert result is True


def test_verify_returns_false_when_valid_code_02(monkeypatch):
    def fake_post(self, url, *, params, json):
        return httpx.Response(
            200,
            json={"data": [{"valid": "02", "valid_msg": "확인할 수 없습니다"}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = _client().verify(business_registration_number="0000000000", representative_name="없는사람", start_date="20200101")
    assert result is False


def test_verify_returns_false_when_data_list_is_empty(monkeypatch):
    def fake_post(self, url, *, params, json):
        return httpx.Response(200, json={"data": []}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = _client().verify(business_registration_number="0000000000", representative_name="x", start_date="20200101")
    assert result is False


def test_verify_url_decodes_the_service_key_before_use(monkeypatch):
    """data.go.kr issues the key URL-encoded (%2F, %3D, ...) for pasting into
    a URL directly - passing it through undecoded would get it double-encoded
    by httpx when building the query string."""
    encoded_key = "abc%2Fdef%3D%3D"

    def fake_post(self, url, *, params, json):
        assert params["serviceKey"] == "abc/def=="
        return httpx.Response(200, json={"data": [{"valid": "01"}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    NtsBizVerifyClient(service_key=encoded_key).verify(
        business_registration_number="1234567890", representative_name="김사장", start_date="20200101"
    )


def test_verify_propagates_http_errors(monkeypatch):
    def fake_post(self, url, *, params, json):
        return httpx.Response(500, json={"error": "internal"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    with pytest.raises(httpx.HTTPStatusError):
        _client().verify(business_registration_number="1234567890", representative_name="김사장", start_date="20200101")


def test_raises_configuration_error_when_no_key_available(monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "nts_biz_verify_api_key", "")
    with pytest.raises(NtsBizVerifyConfigurationError):
        NtsBizVerifyClient()
