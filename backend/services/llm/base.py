from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Master plan §4/§52: agents call this interface, never a vendor SDK directly,
    so no agent code is locked to one model."""

    @abstractmethod
    def generate(self, *, system_prompt: str, user_message: str, max_output_tokens: int = 1024) -> str:
        """Return the model's plain-text reply. Callers are responsible for putting
        every fact the model is allowed to state into system_prompt (§29) - this
        method has no knowledge of what's true, only what it's told.

        max_output_tokens: chat-style single-answer agents (Customer/Info) are
        fine with the 1024 default; agents producing multi-item structured
        output (Expansion's JSON array) must pass a higher value - confirmed
        live that 1024 silently truncates a 5-item Korean-language response
        mid-JSON, which then fails to parse and looks like "the model
        suggested nothing" instead of the token-limit problem it actually is."""
