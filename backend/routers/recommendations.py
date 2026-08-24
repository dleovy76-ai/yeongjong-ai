from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from models import AiInteraction, Business, RecommendationClick, TouristPlace
from routers._ai_common import resolve_llm_provider, run_agent
from schemas.recommendations import (
    RecommendationClickRequest,
    RecommendationClickResponse,
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
)
from services.agents.info import InfoAgent

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])


@router.post("", response_model=RecommendationResponse)
def recommend(body: RecommendationRequest, db: Session = Depends(get_db)) -> RecommendationResponse:
    llm = resolve_llm_provider()
    agent = InfoAgent(db=db, llm=llm)
    reply = run_agent(agent, {}, body.query)
    return RecommendationResponse(
        agent_type=agent.agent_type,
        reply=reply,
        interaction_id=agent.last_interaction_id,
        recommendations=[RecommendationItem(**item) for item in agent.last_recommendations],
    )


@router.post("/{interaction_id}/click", response_model=RecommendationClickResponse, status_code=status.HTTP_201_CREATED)
def record_recommendation_click(
    interaction_id: UUID, body: RecommendationClickRequest, db: Session = Depends(get_db)
) -> RecommendationClickResponse:
    """PILOT AUDIT TASK 3 - 추천→클릭 연결의 최소 기반. 공개(비로그인)
    엔드포인트다 - 추천 자체가 로그인 없이 이뤄지므로, 그 응답을 보고 실제로
    클릭했는지도 같은 조건(비로그인)에서 기록할 수 있어야 한다."""
    interaction = db.get(AiInteraction, interaction_id)
    if interaction is None or interaction.agent_type != "info":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "해당 추천 응답을 찾을 수 없습니다.")

    if body.entity_type == "business":
        exists = db.get(Business, body.entity_id) is not None
    else:
        exists = db.get(TouristPlace, body.entity_id) is not None
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "클릭한 업체/관광지를 찾을 수 없습니다.")

    click = RecommendationClick(
        ai_interaction_id=interaction_id, entity_id=body.entity_id, entity_type=body.entity_type
    )
    db.add(click)
    db.commit()
    db.refresh(click)
    return RecommendationClickResponse.model_validate(click)
