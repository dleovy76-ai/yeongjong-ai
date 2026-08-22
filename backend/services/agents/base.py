"""Master plan §52: every agent follows initialize -> understand -> retrieve ->
decide -> execute -> respond -> log. Defaults here are no-ops/pass-through so a
simple agent (Customer AI) only needs to implement retrieve() and execute();
richer agents (Manager AI, calling other agents as tools) override more."""

import logging
from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy.orm import Session

from services.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    agent_type: str

    def __init__(self, db: Session, llm: LLMProvider) -> None:
        self.db = db
        self.llm = llm

    def initialize(self, business_id: UUID) -> None:
        """Per-conversation setup hook. Default: nothing to do."""

    def understand(self, message: str) -> dict:
        """Parse the raw user message. Default: pass it through unchanged -
        agents that need real intent classification override this."""
        return {"message": message}

    @abstractmethod
    def retrieve(self, business_id: UUID, understood: dict) -> dict:
        """Fetch grounded facts via Tools (services/tools.py) - never query the
        DB directly here-on-down. This is the only source of truth execute() may
        state as fact (§29)."""

    def decide(self, retrieved: dict) -> dict:
        """Default: no extra decision logic, retrieved facts pass straight to
        execute()."""
        return retrieved

    @abstractmethod
    def execute(self, business_id: UUID, understood: dict, decided: dict) -> str:
        """Produce the actual reply, grounded only in `decided`."""

    def respond(self, business_id: UUID, message: str) -> str:
        self.initialize(business_id)
        understood = self.understand(message)
        retrieved = self.retrieve(business_id, understood)
        decided = self.decide(retrieved)
        reply = self.execute(business_id, understood, decided)
        self.log(business_id=business_id, message=message, reply=reply)
        return reply

    def log(self, **fields: object) -> None:
        """§42 observability groundwork - structured log per AI request. Full
        ai_sessions/ai_messages persistence lands with STEP14 (Performance
        Engine); this is the minimum useful before that exists."""
        logger.info("agent_response agent_type=%s %s", self.agent_type, fields)
