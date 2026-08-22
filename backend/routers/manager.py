from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from models import User
from routers._ai_common import resolve_llm_provider, run_agent
from routers._business_common import get_business_or_404, require_owner
from routers.auth import get_current_user
from schemas.ai import ChatResponse
from schemas.manager import ManagerChatRequest
from services.agents.manager import ManagerAgent

router = APIRouter(prefix="/api/v1/businesses/{business_id}/manager", tags=["manager"])


@router.post("/chat", response_model=ChatResponse)
def manager_chat(
    business_id: UUID,
    body: ManagerChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)

    llm = resolve_llm_provider()
    agent = ManagerAgent(db=db, llm=llm)
    reply = run_agent(agent, {"business_id": business_id}, body.message)
    return ChatResponse(agent_type=agent.agent_type, reply=reply)
