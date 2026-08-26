import httpx
import pytest
from fastapi import HTTPException

from routers._ai_common import run_agent
from services.llm.gemini_provider import GeminiResponseError


class _StubAgent:
    """P1-4 - run_agent()은 BaseAgent.respond()만 호출하므로, 실제 DB/LLM
    없이 예외 변환 로직만 독립적으로 검증한다."""

    def __init__(self, to_raise: Exception) -> None:
        self._to_raise = to_raise

    def respond(self, context: dict, message: str) -> str:
        raise self._to_raise


def test_run_agent_translates_httpx_timeout_to_502():
    agent = _StubAgent(httpx.TimeoutException("timed out", request=httpx.Request("POST", "https://example.com")))

    with pytest.raises(HTTPException) as exc_info:
        run_agent(agent, {}, "질문")

    assert exc_info.value.status_code == 502
    assert "AI 응답을 받아오지 못했습니다" in exc_info.value.detail


def test_run_agent_translates_gemini_response_error_to_502():
    """P1-4 핵심 - 이전엔 이 예외가 GeminiResponseError가 아니라 맨
    RuntimeError였어서 여기서 안 잡히고 500으로 새나갔다."""
    agent = _StubAgent(GeminiResponseError("Gemini 응답을 해석할 수 없습니다."))

    with pytest.raises(HTTPException) as exc_info:
        run_agent(agent, {}, "질문")

    assert exc_info.value.status_code == 502
    assert "AI 응답을 받아오지 못했습니다" in exc_info.value.detail


def test_run_agent_does_not_swallow_unrelated_errors():
    """AI 응답 실패와 무관한 버그(예: 진짜 프로그래밍 오류)까지 502로
    뭉개버리면 안 된다 - 관련 없는 예외는 그대로 전파돼야 한다."""
    agent = _StubAgent(ValueError("이건 AI 실패가 아니라 진짜 버그"))

    with pytest.raises(ValueError):
        run_agent(agent, {}, "질문")
