import json
import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from routers._ai_common import resolve_llm_provider, run_agent
from schemas.ai import ChatRequest, ChatResponse, ReservationDraft
from services.agents.customer import CustomerAgent
from services.agents.reservation_draft import ReservationDraftAgent

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
# P1-6 - 매 요청마다 추출 LLM을 또 부르면 비용도 늘고 일반 대화에 draft가
# 뜰 위험도 커진다. history+message 전체에 "예약"이 한 번이라도 있을 때만
# ReservationDraftAgent를 부른다(1차 방어). 정정 발화("아 4명이요")처럼 그
# 메시지 자체엔 없어도 같은 대화 앞부분에 이미 있었으면 전체 텍스트를 보는
# 게이트라 정상적으로 다시 걸린다. has_reservation_intent(2차 방어, 아래
# _parse_reservation_draft)까지 통과해야 실제로 draft가 나간다.
_RESERVATION_KEYWORD = "예약"


def _parse_reservation_draft(raw_reply: str) -> ReservationDraft | None:
    cleaned = _JSON_FENCE_RE.sub("", raw_reply).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or not parsed.get("has_reservation_intent"):
        return None

    def _clean_str(value: object) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    party_size = parsed.get("party_size")
    if not isinstance(party_size, int):
        party_size = None

    return ReservationDraft(
        customer_name=_clean_str(parsed.get("customer_name")),
        customer_phone=_clean_str(parsed.get("customer_phone")),
        date=_clean_str(parsed.get("date")),
        time=_clean_str(parsed.get("time")),
        party_size=party_size,
        notes=_clean_str(parsed.get("notes")),
    )


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    llm = resolve_llm_provider()
    history = [h.model_dump() for h in body.history]

    agent = CustomerAgent(db=db, llm=llm)
    reply = run_agent(agent, {"business_id": body.business_id, "history": history}, body.message)

    reservation_draft = None
    combined_text = " ".join(h["text"] for h in history) + " " + body.message
    if _RESERVATION_KEYWORD in combined_text:
        draft_agent = ReservationDraftAgent(db=db, llm=llm)
        # business_id를 의도적으로 안 넣는다 - Performance의 ai_response_count가
        # 이 업체 기준으로 손님의 한 턴을 AI 상담 2건으로 부풀리지 않도록.
        raw_draft = run_agent(draft_agent, {"history": history}, body.message)
        reservation_draft = _parse_reservation_draft(raw_draft)

    return ChatResponse(
        agent_type=agent.agent_type,
        reply=reply,
        menu_images=agent.last_recommended_menus,
        reservation_draft=reservation_draft,
    )
