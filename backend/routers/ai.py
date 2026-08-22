from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from routers._ai_common import resolve_llm_provider, run_agent
from schemas.ai import ChatRequest, ChatResponse
from services.agents.customer import CustomerAgent

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    llm = resolve_llm_provider()
    agent = CustomerAgent(db=db, llm=llm)
    reply = run_agent(agent, {"business_id": body.business_id}, body.message)
    return ChatResponse(agent_type=agent.agent_type, reply=reply)
