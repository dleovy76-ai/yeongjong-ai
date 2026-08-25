from services.llm.base import LLMProvider, LLMResponse


class FakeLLMProvider(LLMProvider):
    """Deterministic stand-in for tests - no network call, no API key needed.
    Records every call so tests can assert what grounding context an agent
    actually sent, not just what it returned.

    P1-6 - a single chat turn can now trigger two different agents sharing
    one provider instance (CustomerAgent's reply, then ReservationDraftAgent's
    JSON extraction) - `responses` lets a test give each call its own answer
    in order, without breaking every existing single-`response` caller."""

    def __init__(self, response: str = "테스트 응답입니다.", responses: list[str] | None = None) -> None:
        self.response = response
        self._responses = list(responses) if responses is not None else None
        self.calls: list[dict[str, str]] = []

    def generate(self, *, system_prompt: str, user_message: str, max_output_tokens: int = 1024) -> LLMResponse:
        self.calls.append({"system_prompt": system_prompt, "user_message": user_message})
        if self._responses:
            text = self._responses.pop(0)
        else:
            text = self.response
        return LLMResponse(text=text, prompt_tokens=10, completion_tokens=5)
