from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from routers._ai_common import resolve_llm_provider, run_agent
from schemas.chef import ChefChatRequest, ChefChatResponse
from services.agents.chef import ChefAgent

router = APIRouter(prefix="/api/v1/businesses/{business_id}/chef", tags=["chef"])


@router.post("/chat", response_model=ChefChatResponse)
def chef_chat(business_id: UUID, body: ChefChatRequest, db: Session = Depends(get_db)) -> ChefChatResponse:
    """Public - same no-auth pattern as /api/v1/ai/chat (Customer AI), since
    it's the visitor asking what to order, not the owner."""
    llm = resolve_llm_provider()
    agent = ChefAgent(db=db, llm=llm)
    reply = run_agent(agent, {"business_id": business_id}, body.message)
    return ChefChatResponse(agent_type=agent.agent_type, reply=reply, menu_images=agent.last_recommended_menus)
