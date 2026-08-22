"""Shared plumbing for routers/ai.py and routers/recommendations.py - both wrap
an agent's respond() with the same "LLM not configured -> 503" / "LLM call
failed -> 502" translation, so it's factored out rather than duplicated."""

import httpx
from fastapi import HTTPException, status

from services.agents.base import BaseAgent
from services.llm import get_llm_provider
from services.llm.base import LLMProvider
from services.llm.gemini_provider import GeminiConfigurationError


def resolve_llm_provider() -> LLMProvider:
    try:
        return get_llm_provider()
    except GeminiConfigurationError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "AI 기능이 아직 설정되지 않았습니다.") from exc


def run_agent(agent: BaseAgent, context: dict, message: str) -> str:
    try:
        return agent.respond(context, message)
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI 응답을 받아오지 못했습니다.") from exc
