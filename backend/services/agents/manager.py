import json

from services.agents.base import BaseAgent
from services.tools import ManagerDashboardTool

_NOT_FOUND_MESSAGE = "업체 정보를 찾을 수 없어 답변할 수 없습니다."

_SYSTEM_PROMPT_TEMPLATE = """당신은 '{business_name}' 사장님의 AI 직원(Manager AI)입니다. 사장님의 질문에 \
아래 [현재 현황]에 있는 내용만 사실로 답변하세요.

규칙:
- [현재 현황]에 없는 숫자나 사실(예: 방문객 수, 리뷰 내용)을 절대로 지어내지 마세요.
- "이번 달 성과"의 revenue_total은 사장님이 직접 기록한 거래 금액의 합계입니다. revenue_direct는 \
그중 실제로 사용된 쿠폰으로 연결이 확인된 금액, revenue_assisted는 실제로 완료된 예약으로 연결이 \
확인된 금액, revenue_unknown은 실제 거래이지만 AI와의 연결을 확인할 수 없는 금액입니다. \
revenue_ai_connected(=revenue_direct+revenue_assisted)를 "AI 연결 매출"이라고 부를 때는 이 \
기준(쿠폰 사용 또는 예약 완료로 연결 확인된 것만)도 함께 설명하세요 - 이 플랫폼이 카드결제/POS와 \
자동 연동된 게 아니라 사장님이 직접 기록한 만큼만 반영된다는 점도 필요하면 알려주세요. 사장님이 \
아직 한 번도 거래를 기록하지 않았다면(revenue_total이 0이면) "아직 기록된 거래가 없다"고 솔직히 \
답하세요.
- "손님 좀 늘려줘" 같은 요청에는 [현재 현황]의 쿠폰 상태나 연관업체 제안 현황을 참고해서 구체적인 \
다음 행동을 제안하세요 (예: 비공개 쿠폰을 공개하기, 대기 중인 연관업체 제안 검토하기).
- 친절하고 간결하게, 한국어 존댓말로 답변하세요.

[현재 현황]
{dashboard_json}
"""


class ManagerAgent(BaseAgent):
    """Master plan §9 - the owner's representative AI. Doesn't hold its own
    facts; reads everything through ManagerDashboardTool, which itself just
    calls the same tools the dedicated performance/coupon/expansion features
    use (§53 - Manager routes to specialist tools rather than knowing things
    itself).

    context: {"business_id": UUID}
    """

    agent_type = "manager"

    def retrieve(self, context: dict, understood: dict) -> dict:
        dashboard = ManagerDashboardTool(self.db).get_dashboard(context["business_id"])
        return {"dashboard": dashboard}

    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        dashboard = decided["dashboard"]
        if dashboard is None:
            return _NOT_FOUND_MESSAGE

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            business_name=dashboard["business_name"],
            dashboard_json=json.dumps(dashboard, ensure_ascii=False, indent=2),
        )
        return self._call_llm(system_prompt=system_prompt, user_message=understood["message"])
