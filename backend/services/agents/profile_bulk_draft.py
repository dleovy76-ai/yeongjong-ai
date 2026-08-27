from services.agents.base import BaseAgent

_SYSTEM_PROMPT = """당신은 영종 AI의 업체 정보 일괄 등록 도우미입니다. 사장님이 네이버 플레이스 등에서 \
직접 캡쳐해서 올린 [업체 정보 화면 이미지]를 보고, 아래 항목들을 뽑아 정리해주세요. 사장님은 이 결과를 \
확인하고 필요하면 고친 뒤에만 실제로 저장합니다.

규칙:
- 이미지에 실제로 보이는 내용만 뽑으세요. 안 보이거나 불확실한 항목은 절대 추측해서 채우지 말고 \
null로 두세요.
- 각 항목은 한국어 한 문장 정도로 간결하게 정리하세요(이미지의 표현을 그대로 옮기되 불필요한 기호는 \
정리).
- opening_hours(영업시간)가 요일별로 다르거나 브레이크타임이 있으면 "요일 시작-종료(브레이크타임 \
시작-종료)" 형식으로 요일마다 세미콜론(;)으로 구분해서 정리하세요. 예: "월-토 11:00-21:00(브레이크타임 \
14:00-16:30); 일 휴무". 같은 단어를 문장 끝에 의미 없이 중복해서 쓰지 마세요.
- 리뷰, 별점, 광고 문구처럼 아래 항목에 해당하지 않는 내용은 무시하세요.
- 다른 설명 없이 아래 형식의 JSON 객체 하나만 응답하세요(값을 모르면 null):
{"description": "...", "opening_hours": "...", "holiday": "...", "parking": "...", \
"pet_policy": "...", "reservation_policy": "...", "takeout_policy": "...", "payment_methods": "..."}"""


class ProfileBulkDraftAgent(BaseAgent):
    """사장님이 네이버 플레이스 등에서 직접 캡쳐해 올린 이미지를 보고 업체
    프로필 항목(가게소개/영업시간/휴무일/주차/반려동물/예약안내/포장안내/
    결제수단) 후보를 뽑아주는 도우미. 자동 스크래핑이 아니라 사장님이 직접
    가져온 이미지만 근거로 삼는다(§29, menu_bulk_draft.py와 같은 원칙) - 이
    이미지를 우리가 대신 가져오는 일은 절대 없다. 절대 자동 저장하지 않고,
    사장님이 확인/수정한 뒤 기존 프로필 저장(PATCH /profile) 흐름으로
    저장한다.

    context: {"business_id": UUID, "image_bytes": bytes, "image_mime_type": str}
    """

    agent_type = "profile_bulk_draft"

    def retrieve(self, context: dict, understood: dict) -> dict:
        return {}

    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        return self._call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message="이미지에서 업체 정보를 추출해줘",
            image_bytes=context["image_bytes"],
            image_mime_type=context["image_mime_type"],
        )
