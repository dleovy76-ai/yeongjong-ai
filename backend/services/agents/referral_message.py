from models import Business
from services.agents.base import BaseAgent

_NOT_FOUND_MESSAGE = "업체 정보를 찾을 수 없어 메시지를 만들 수 없습니다."

_SYSTEM_PROMPT_TEMPLATE = """당신은 영종 AI의 제휴 제안 메시지 작성 도우미입니다. [보내는 업체]가 \
[받는 업체]에게 보낼 제휴 제안 메시지를 한국어로 작성하세요.

규칙:
- [보내는 업체]와 [받는 업체]의 실제 이름·업종만 사용하세요. 할인율, 구체적 조건, 매출 수치 등 \
[보내는 업체]/[받는 업체] 정보에 없는 내용을 지어내지 마세요 - "상호 혜택을 제공하는 제휴" 같은 \
일반적인 표현으로 남겨두세요.
- 정중하고 친근한 톤으로, 3~5문장 이내로 짧게 작성하세요.
- 영종 AI를 통해 발견된 제휴 제안이라는 점을 자연스럽게 언급하세요.
- 마지막에 "[우리 가게 AI 만들기]" 같은 인사말이나 링크 문구는 넣지 마세요 - 순수 메시지 본문만 \
작성하세요.
- 다른 설명 없이 메시지 본문만 응답하세요.

[보내는 업체]
이름: {sender_name}
업종: {sender_category}

[받는 업체]
이름: {recipient_name}
업종: {recipient_category}
"""


class ReferralMessageAgent(BaseAgent):
    """Master plan §25 - drafts the outreach message an owner can copy and send
    themselves. Never auto-sends (§25: "초기에는 자동 발송하지 않는다") - there's
    no delivery channel here at all, just text for the owner to use however
    they contact the other business.

    context: {"business_a_id": UUID, "business_b_id": UUID}
    """

    agent_type = "referral_message"

    def retrieve(self, context: dict, understood: dict) -> dict:
        sender = self.db.get(Business, context["business_a_id"])
        recipient = self.db.get(Business, context["business_b_id"])
        return {"sender": sender, "recipient": recipient}

    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        sender, recipient = decided["sender"], decided["recipient"]
        if sender is None or recipient is None:
            return _NOT_FOUND_MESSAGE

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            sender_name=sender.name_ko,
            sender_category=sender.category.value,
            recipient_name=recipient.name_ko,
            recipient_category=recipient.category.value,
        )
        return self._call_llm(system_prompt=system_prompt, user_message="메시지 작성해줘")
