from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Master plan §4/§52: agents call this interface, never a vendor SDK directly,
    so no agent code is locked to one model."""

    @abstractmethod
    def generate(self, *, system_prompt: str, user_message: str) -> str:
        """Return the model's plain-text reply. Callers are responsible for putting
        every fact the model is allowed to state into system_prompt (§29) - this
        method has no knowledge of what's true, only what it's told."""
