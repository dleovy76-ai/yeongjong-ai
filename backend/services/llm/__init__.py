from core.config import settings
from services.llm.base import LLMProvider
from services.llm.gemini_provider import GeminiProvider

__all__ = ["LLMProvider", "GeminiProvider", "get_llm_provider"]


def get_llm_provider() -> LLMProvider:
    """Single place that decides which concrete provider backs the app. Adding
    OpenAIProvider/ClaudeProvider later is a one-line change here, not a change
    to any agent (§4)."""
    return GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
