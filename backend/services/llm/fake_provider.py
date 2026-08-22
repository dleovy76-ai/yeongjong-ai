from services.llm.base import LLMProvider


class FakeLLMProvider(LLMProvider):
    """Deterministic stand-in for tests - no network call, no API key needed.
    Records every call so tests can assert what grounding context an agent
    actually sent, not just what it returned."""

    def __init__(self, response: str = "테스트 응답입니다.") -> None:
        self.response = response
        self.calls: list[dict[str, str]] = []

    def generate(self, *, system_prompt: str, user_message: str, max_output_tokens: int = 1024) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_message": user_message})
        return self.response
