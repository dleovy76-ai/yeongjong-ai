from uuid import UUID

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class RecommendationItem(BaseModel):
    """PILOT AUDIT TASK 2/3 - InfoAgent가 실제 후보 목록과 대조해 검증한
    추천 결과만 여기 담긴다(services/agents/info.py의 last_recommendations)."""

    id: UUID
    name: str
    category: str
    source: str
    reason: str


class RecommendationResponse(BaseModel):
    agent_type: str
    reply: str
    # PILOT AUDIT TASK 3 - 이 추천 응답을 가리키는 AiInteraction.id. 프론트가
    # 손님의 클릭을 /recommendations/{interaction_id}/click 으로 보낼 때 쓴다.
    interaction_id: UUID | None
    recommendations: list[RecommendationItem]


class RecommendationClickRequest(BaseModel):
    entity_id: UUID
    entity_type: str = Field(pattern="^(business|tourist_place)$")


class RecommendationClickResponse(BaseModel):
    id: UUID
    ai_interaction_id: UUID
    entity_id: UUID
    entity_type: str

    model_config = {"from_attributes": True}
