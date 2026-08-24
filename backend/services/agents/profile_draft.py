from services.agents.base import BaseAgent
from services.tools import BusinessSearchTool, MenuSearchTool

_NOT_FOUND_REPLY = '{"description": "", "brand_tone": ""}'

_SYSTEM_PROMPT_TEMPLATE = """당신은 영종 AI의 업체 소개글 초안 작성 도우미입니다. 사장님이 처음부터 \
직접 쓰지 않아도 되도록, 아래 [업체 정보]만 근거로 소개글(description)과 AI 말투 가이드(brand_tone) \
초안을 만들어주세요. 사장님은 이 초안을 확인하고 자유롭게 고쳐서 저장합니다.

규칙:
- description은 손님에게 보여줄 가게 소개 문장입니다. [업체 정보]에 있는 이름·업종·대표 메뉴만 \
사용하세요. 영업시간, 주차, 반려동물 동반, "전통", "1위", "최고" 같은 [업체 정보]에 없는 사실이나 \
과장된 주장은 절대 지어내지 마세요. 2~4문장, 친근한 한국어로 작성하세요.
- brand_tone은 AI 직원이 손님과 대화할 때 쓸 말투를 짧은 한국어 구절로 제안하세요 \
(예: "친근하고 정겨운 존댓말", "차분하고 정중한 존댓말"). 업종과 메뉴 분위기에 맞게 고르세요.
- 다른 설명 없이 아래 형식의 JSON 객체 하나만 응답하세요: \
{{"description": "...", "brand_tone": "..."}}

[업체 정보]
이름: {name}
업종: {category}
대표 메뉴: {signature_menus}
"""


class ProfileDraftAgent(BaseAgent):
    """사장님이 소개글/브랜드톤을 빈 칸에서부터 쓰지 않아도 되도록, 실제 업체
    이름·업종·대표 메뉴만 근거로 초안을 만들어주는 도우미. 절대 자동 저장하지
    않음 - 사장님이 확인 후 직접 수정/저장(§29, 네이버 링크 기능과 같은
    "AI가 초안을 만들고 사장님이 확인" 패턴).

    context: {"business_id": UUID}
    """

    agent_type = "profile_draft"

    def retrieve(self, context: dict, understood: dict) -> dict:
        business_id = context["business_id"]
        business_context = BusinessSearchTool(self.db).get_context(business_id)
        menus = MenuSearchTool(self.db).list_menus(business_id)
        return {"business": business_context, "menus": menus}

    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        business = decided["business"]
        if business is None:
            return _NOT_FOUND_REPLY

        signature = [m["name"] for m in decided["menus"] if m["is_signature"]]
        if not signature:
            signature = [m["name"] for m in decided["menus"][:5]]
        signature_text = ", ".join(signature) if signature else "(등록된 메뉴 없음)"

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            name=business["name"],
            category=business["category"],
            signature_menus=signature_text,
        )
        return self._call_llm(system_prompt=system_prompt, user_message="초안 작성해줘")
