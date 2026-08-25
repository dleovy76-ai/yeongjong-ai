from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ChatHistoryItem(BaseModel):
    """P1-6 - 프론트가 이미 화면에 들고 있는 전체 대화를 매 요청마다 그대로
    실어 보내는 용도. 백엔드는 세션/DB를 따로 두지 않고 이걸로만 대화
    맥락과 예약 정보 추출을 처리한다(docs/P1-6_CONVERSATIONAL_RESERVATION.md)."""

    role: Literal["user", "ai"]
    text: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    business_id: UUID
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatHistoryItem] = []


class MenuImageItem(BaseModel):
    id: UUID
    name: str
    image_url: str


class ReservationDraft(BaseModel):
    """P1-6 - ReservationDraftAgent가 대화 전체를 재분석해 뽑아낸, 아직 확정
    되지 않은 예약 정보. 손님이 말하지 않은 항목은 항상 null(추측 금지) -
    프론트가 빈 항목을 "확인 필요"로 보여주고, 전부 채워졌을 때만 사람이
    [예약 확정]을 눌러 기존 createReservation()으로 실제 Reservation을
    만든다. 이 draft 자체는 DB에 저장되지 않는다."""

    customer_name: str | None = None
    customer_phone: str | None = None
    date: str | None = None
    time: str | None = None
    party_size: int | None = None
    notes: str | None = None


class ChatResponse(BaseModel):
    agent_type: str
    reply: str
    menu_images: list[MenuImageItem] = []
    reservation_draft: ReservationDraft | None = None
