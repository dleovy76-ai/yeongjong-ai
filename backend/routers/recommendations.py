from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from routers._ai_common import resolve_llm_provider, run_agent
from schemas.recommendations import RecommendationRequest, RecommendationResponse
from services.agents.info import InfoAgent

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])


@router.post("", response_model=RecommendationResponse)
def recommend(body: RecommendationRequest, db: Session = Depends(get_db)) -> RecommendationResponse:
    llm = resolve_llm_provider()
    agent = InfoAgent(db=db, llm=llm)
    reply = run_agent(agent, {}, body.query)
    return RecommendationResponse(agent_type=agent.agent_type, reply=reply)
