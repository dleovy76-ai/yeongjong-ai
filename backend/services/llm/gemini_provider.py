import logging

import httpx

from core.config import settings
from services.llm.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 30.0


class GeminiConfigurationError(RuntimeError):
    pass


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model
        if not self.api_key:
            raise GeminiConfigurationError("GEMINI_API_KEY가 설정되지 않았습니다.")

    def generate(self, *, system_prompt: str, user_message: str, max_output_tokens: int = 1024) -> LLMResponse:
        # Key goes in a header, not the ?key= query string - httpx (and any proxy/log
        # in between) logs the request URL at INFO level, which would otherwise leak
        # the key into logs (confirmed live: it showed up in this app's own dev log).
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": user_message}]}],
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
            raise RuntimeError("Gemini 응답을 해석할 수 없습니다.") from exc

        usage = data.get("usageMetadata", {})
        return LLMResponse(
            text=text,
            prompt_tokens=usage.get("promptTokenCount"),
            completion_tokens=usage.get("candidatesTokenCount"),
        )
