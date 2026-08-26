"""Shared plumbing for routers/ai.py and routers/recommendations.py - both wrap
an agent's respond() with the same "LLM not configured -> 503" / "LLM call
failed -> 502" translation, so it's factored out rather than duplicated."""

import httpx
from fastapi import HTTPException, status

from services.agents.base import BaseAgent
from services.llm import get_llm_provider
from services.llm.base import LLMProvider
from services.llm.gemini_provider import GeminiConfigurationError, GeminiResponseError


def resolve_llm_provider() -> LLMProvider:
    try:
        return get_llm_provider()
    except GeminiConfigurationError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "AI 기능이 아직 설정되지 않았습니다.") from exc


def run_agent(agent: BaseAgent, context: dict, message: str) -> str:
    try:
        return agent.respond(context, message)
    except (httpx.HTTPError, GeminiResponseError) as exc:
        # P1-4 - httpx.HTTPError는 타임아웃/네트워크 실패, GeminiResponseError는
        # 200 응답인데 형태가 이상한 경우(안전필터 차단 등) - 둘 다 손님에게는
        # 같은 "AI가 지금 응답을 못 받아왔다"는 사실이라 동일하게 502로 안내한다.
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI 응답을 받아오지 못했습니다.") from exc
