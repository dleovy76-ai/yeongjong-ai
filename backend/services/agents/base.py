"""Master plan §52: every agent follows initialize -> understand -> retrieve ->
decide -> execute -> respond -> log. Defaults here are no-ops/pass-through so a
simple agent (Customer AI) only needs to implement retrieve() and execute();
richer agents (Manager AI, calling other agents as tools) override more.

`context` is a plain dict rather than a fixed field like business_id, because not
every agent scopes to one business - Customer AI needs {"business_id": ...},
Info AI (recommends across the whole directory) needs none at all. Each agent
subclass documents what keys it reads from context."""

import logging
import uuid
from abc import ABC, abstractmethod
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import settings
from models import AiInteraction
from services.llm.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    agent_type: str
    prompt_version: str = "v1"

    def __init__(self, db: Session, llm: LLMProvider) -> None:
        self.db = db
        self.llm = llm
        self._last_usage: LLMResponse | None = None
        # PILOT AUDIT TASK 3 - the AiInteraction row this respond() call just
        # logged, so a caller (e.g. the recommendations router) can hand the
        # id back to the frontend as a stable reference for a later
        # "recommendation was clicked" event. None until log() runs once.
        self.last_interaction_id: uuid.UUID | None = None

    def _call_llm(self, *, system_prompt: str, user_message: str, max_output_tokens: int = 1024) -> str:
        """Every agent's execute() should call this instead of self.llm.generate()
        directly - same signature/return type (plain str), but also records
        token usage on self so log() can persist it (STEP14)."""
        response = self.llm.generate(
            system_prompt=system_prompt, user_message=user_message, max_output_tokens=max_output_tokens
        )
        self._last_usage = response
        return response.text

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

    def _estimate_cost(self) -> Decimal | None:
        if self._last_usage is None:
            return None
        input_rate = settings.gemini_input_cost_per_1k_tokens
        output_rate = settings.gemini_output_cost_per_1k_tokens
        if input_rate <= 0 and output_rate <= 0:
            return None
        prompt_tokens = self._last_usage.prompt_tokens or 0
        completion_tokens = self._last_usage.completion_tokens or 0
        cost = (prompt_tokens / 1000) * input_rate + (completion_tokens / 1000) * output_rate
        return Decimal(str(round(cost, 6)))

    def log(self, **fields: object) -> None:
        """§42 observability groundwork - structured log per AI request, plus a
        full AiInteraction row (STEP14): message/reply content, token usage,
        an estimated cost (only when the operator has configured real rates -
        see _estimate_cost), and the agent's prompt_version."""
        logger.info("agent_response agent_type=%s %s", self.agent_type, fields)

        context = fields.get("context")
        business_id = context.get("business_id") if isinstance(context, dict) else None
        row_kwargs = dict(
            agent_type=self.agent_type,
            user_message=str(fields.get("message")) if fields.get("message") is not None else None,
            reply=str(fields.get("reply")) if fields.get("reply") is not None else None,
            prompt_tokens=self._last_usage.prompt_tokens if self._last_usage else None,
            completion_tokens=self._last_usage.completion_tokens if self._last_usage else None,
            estimated_cost_usd=self._estimate_cost(),
            prompt_version=self.prompt_version,
        )
        interaction = AiInteraction(business_id=business_id, **row_kwargs)
        self.db.add(interaction)
        try:
            self.db.commit()
        except IntegrityError:
            # business_id in context didn't reference a real business (e.g. the
            # "not found" reply path) - don't let a logging side-effect crash the
            # actual response. Record it without the business association instead
            # of dropping the interaction entirely.
            self.db.rollback()
            interaction = AiInteraction(business_id=None, **row_kwargs)
            self.db.add(interaction)
            self.db.commit()
        self.db.refresh(interaction)
        self.last_interaction_id = interaction.id
