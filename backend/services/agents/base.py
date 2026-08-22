"""Master plan §52: every agent follows initialize -> understand -> retrieve ->
decide -> execute -> respond -> log. Defaults here are no-ops/pass-through so a
simple agent (Customer AI) only needs to implement retrieve() and execute();
richer agents (Manager AI, calling other agents as tools) override more.

`context` is a plain dict rather than a fixed field like business_id, because not
every agent scopes to one business - Customer AI needs {"business_id": ...},
Info AI (recommends across the whole directory) needs none at all. Each agent
subclass documents what keys it reads from context."""

import logging
from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from services.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    agent_type: str

    def __init__(self, db: Session, llm: LLMProvider) -> None:
        self.db = db
        self.llm = llm

    def initialize(self, context: dict) -> None:
        """Per-conversation setup hook. Default: nothing to do."""

    def understand(self, message: str) -> dict:
        """Parse the raw user message. Default: pass it through unchanged -
        agents that need real intent classification override this."""
        return {"message": message}

    @abstractmethod
    def retrieve(self, context: dict, understood: dict) -> dict:
        """Fetch grounded facts via Tools (services/tools.py) - never query the
        DB directly here-on-down. This is the only source of truth execute() may
        state as fact (§29)."""

    def decide(self, retrieved: dict) -> dict:
        """Default: no extra decision logic, retrieved facts pass straight to
        execute()."""
        return retrieved

    @abstractmethod
    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        """Produce the actual reply, grounded only in `decided`."""

    def respond(self, context: dict, message: str) -> str:
        self.initialize(context)
        understood = self.understand(message)
        retrieved = self.retrieve(context, understood)
        decided = self.decide(retrieved)
        reply = self.execute(context, understood, decided)
        self.log(context=context, message=message, reply=reply)
        return reply

    def log(self, **fields: object) -> None:
        """§42 observability groundwork - structured log per AI request. Full
        ai_sessions/ai_messages persistence lands with STEP14 (Performance
        Engine); this is the minimum useful before that exists."""
        logger.info("agent_response agent_type=%s %s", self.agent_type, fields)
