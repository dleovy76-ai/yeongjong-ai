import base64

import httpx
import pytest

from services.llm.gemini_provider import GeminiProvider, GeminiResponseError

_FAKE_KEY = "fake-key-for-tests"


def _provider() -> GeminiProvider:
    return GeminiProvider(api_key=_FAKE_KEY, model="gemini-test")


def test_generate_parses_text_and_token_usage(monkeypatch):
    def fake_post(self, url, *, json, headers):
        assert headers["x-goog-api-key"] == _FAKE_KEY
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": " 안녕하세요 "}]}}],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    response = _provider().generate(system_prompt="시스템", user_message="질문")

    assert response.text == "안녕하세요"  # strip() 적용 확인
    assert response.prompt_tokens == 10
    assert response.completion_tokens == 5


def test_generate_raises_gemini_response_error_on_malformed_body(monkeypatch):
    """P1-4 - 200 응답인데 candidates가 없는 경우(안전필터 차단 등) 맨
    RuntimeError가 아니라 전용 예외를 던져야 run_agent()가 502로 잡을 수
    있다."""

    def fake_post(self, url, *, json, headers):
        return httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    with pytest.raises(GeminiResponseError):
        _provider().generate(system_prompt="시스템", user_message="질문")


def test_generate_propagates_http_errors_for_non_2xx_status(monkeypatch):
    def fake_post(self, url, *, json, headers):
        return httpx.Response(500, json={"error": "internal"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    with pytest.raises(httpx.HTTPStatusError):
        _provider().generate(system_prompt="시스템", user_message="질문")


def test_generate_propagates_timeout_as_httpx_error(monkeypatch):
    def fake_post(self, url, *, json, headers):
        raise httpx.TimeoutException("timed out", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    with pytest.raises(httpx.HTTPError):
        _provider().generate(system_prompt="시스템", user_message="질문")


def test_generate_without_image_sends_only_a_text_part(monkeypatch):
    captured = {}

    def fake_post(self, url, *, json, headers):
        captured["payload"] = json
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "답변"}]}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    _provider().generate(system_prompt="시스템", user_message="질문")

    assert captured["payload"]["contents"] == [{"parts": [{"text": "질문"}]}]


def test_generate_with_image_sends_inline_data_part_alongside_text(monkeypatch):
    captured = {}

    def fake_post(self, url, *, json, headers):
        captured["payload"] = json
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "답변"}]}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    _provider().generate(
        system_prompt="시스템",
        user_message="이미지에서 뽑아줘",
        image_bytes=b"fake-image-bytes",
        image_mime_type="image/png",
    )

    parts = captured["payload"]["contents"][0]["parts"]
    assert parts[0] == {
        "inlineData": {
            "mimeType": "image/png",
            "data": base64.b64encode(b"fake-image-bytes").decode("ascii"),
        }
    }
    assert parts[1] == {"text": "이미지에서 뽑아줘"}
