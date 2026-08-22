from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class RecommendationResponse(BaseModel):
    agent_type: str
    reply: str
