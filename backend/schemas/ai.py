from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    business_id: UUID
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    agent_type: str
    reply: str
