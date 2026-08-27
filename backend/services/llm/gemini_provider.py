import base64
import logging

import httpx

from core.config import settings
from services.llm.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

# P1-4 (REORG_DECISIONS.md) - 이전엔 30초였다. httpx 타임아웃 자체는 이미 있었고
# routers/_ai_common.py의 run_agent()가 httpx.HTTPError(TimeoutException 포함)를
# 502로 잡아주는 것도 이미 됐었다 - 진짜 문제는 실시간 채팅 UX에서 30초는
# 사실상 "무한정 기다리는" 것과 체감이 비슷하다는 것. Expansion의 다건 구조화
# 출력(2048 토큰)까지 감안해 너무 짧지 않으면서 채팅 UX에 맞는 값으로 낮춘다.
_TIMEOUT_SECONDS = 20.0


class GeminiConfigurationError(RuntimeError):
    pass


class GeminiResponseError(RuntimeError):
    """P1-4 - 이전엔 맨 RuntimeError를 던져서 run_agent()의
    `except httpx.HTTPError`에 안 걸리고 그대로 500으로 새나갔다(응답 형태가
    이상한 경우 - 안전필터 차단 등). 전용 예외로 만들어 run_agent()가 같이
    잡을 수 있게 한다."""


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model
        if not self.api_key:
            raise GeminiConfigurationError("GEMINI_API_KEY가 설정되지 않았습니다.")

    def generate(
        self,
        *,
        system_prompt: str,
        user_message: str,
        max_output_tokens: int = 1024,
        image_bytes: bytes | None = None,
        image_mime_type: str | None = None,
    ) -> LLMResponse:
        # Key goes in a header, not the ?key= query string - httpx (and any proxy/log
        # in between) logs the request URL at INFO level, which would otherwise leak
        # the key into logs (confirmed live: it showed up in this app's own dev log).
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        parts: list[dict] = []
        if image_bytes is not None:
            parts.append(
                {
                    "inlineData": {
                        "mimeType": image_mime_type or "image/jpeg",
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                    }
                }
            )
        parts.append({"text": user_message})
        payload = {
            "contents": [{"parts": parts}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": max_output_tokens},
        }

        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            response = client.post(url, json=payload, headers={"x-goog-api-key": self.api_key})
        response.raise_for_status()
        data = response.json()

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError) as exc:
            logger.error("Unexpected Gemini response shape: %s", data)
            raise GeminiResponseError("Gemini 응답을 해석할 수 없습니다.") from exc

        usage = data.get("usageMetadata", {})
        return LLMResponse(
            text=text,
            prompt_tokens=usage.get("promptTokenCount"),
            completion_tokens=usage.get("candidatesTokenCount"),
        )
