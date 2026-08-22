import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from services.agents.customer import CustomerAgent
from services.llm import get_llm_provider
from services.llm.gemini_provider import GeminiConfigurationError
from schemas.ai import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    try:
        llm = get_llm_provider()
    except GeminiConfigurationError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "AI 기능이 아직 설정되지 않았습니다.") from exc

    agent = CustomerAgent(db=db, llm=llm)
    try:
        reply = agent.respond(body.business_id, body.message)
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI 응답을 받아오지 못했습니다.") from exc

    return ChatResponse(agent_type=agent.agent_type, reply=reply)
