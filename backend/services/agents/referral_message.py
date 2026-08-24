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
{signup_instruction}
- 다른 설명 없이 메시지 본문만 응답하세요.

[보내는 업체]
이름: {sender_name}
업종: {sender_category}

[받는 업체]
이름: {recipient_name}
업종: {recipient_category}
"""

# §20-23/기획서 13번 - "업체의 AI가 새로운 업체를 모집한다"가 플랫폼의 핵심
# 차별화 포인트인데, [받는 업체]가 아직 영종 AI를 쓰지 않는 미가입 업체라면
# 이 메시지가 사실상 유일한 가입 경로다. 이미 가입해 사용 중인 업체에게는
# 가입 안내가 어색하므로(이미 회원), is_claimed로 분기한다.
_SIGNUP_INSTRUCTION_UNCLAIMED = (
    "- [받는 업체]는 아직 영종 AI를 사용하지 않는 업체입니다 - 메시지 끝에 \"영종 AI\"를 검색해서 "
    "[받는 업체] 이름으로 우리 가게를 찾아 AI를 만들어보라고 자연스럽게 안내하세요. 구체적인 URL은 "
    "모르니 지어내지 말고, \"영종 AI\"라는 이름만 언급하세요."
)
_SIGNUP_INSTRUCTION_CLAIMED = (
    '- [받는 업체]는 이미 영종 AI를 사용 중인 업체입니다 - "[우리 가게 AI 만들기]" 같은 가입 안내나 '
    "링크 문구는 넣지 마세요. 순수 제휴 제안 내용만 작성하세요."
)


class ReferralMessageAgent(BaseAgent):
    """Master plan §25/기획서 13번("AI가 AI를 확장한다") - drafts the outreach
    message an owner can copy and send themselves. Never auto-sends (§25:
    "초기에는 자동 발송하지 않는다") - there's no delivery channel here at all,
    just text for the owner to use however they contact the other business.
    When the recipient is still unclaimed, this message is the platform's
    actual growth mechanism - see _SIGNUP_INSTRUCTION_UNCLAIMED.

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

        signup_instruction = (
            _SIGNUP_INSTRUCTION_UNCLAIMED if recipient.owner_user_id is None else _SIGNUP_INSTRUCTION_CLAIMED
        )
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            signup_instruction=signup_instruction,
            sender_name=sender.name_ko,
            sender_category=sender.category.value,
            recipient_name=recipient.name_ko,
            recipient_category=recipient.category.value,
        )
        return self._call_llm(system_prompt=system_prompt, user_message="메시지 작성해줘")
