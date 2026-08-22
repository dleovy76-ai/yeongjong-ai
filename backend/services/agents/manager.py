import json

from services.agents.base import BaseAgent
from services.tools import ManagerDashboardTool

_NOT_FOUND_MESSAGE = "업체 정보를 찾을 수 없어 답변할 수 없습니다."

_SYSTEM_PROMPT_TEMPLATE = """당신은 '{business_name}' 사장님의 AI 직원(Manager AI)입니다. 사장님의 질문에 \
아래 [현재 현황]에 있는 내용만 사실로 답변하세요.

규칙:
- [현재 현황]에 없는 숫자나 사실(예: 실제 매출액, 방문객 수)을 절대로 지어내지 마세요. 이 플랫폼은 \
아직 결제/매출 데이터를 직접 연동하지 않으므로, "이번 달 성과"에 있는 AI 응대·쿠폰 발급/사용 건수만 \
실제로 확인된 수치입니다.
- 사장님이 "매출이 얼마냐"처럼 아직 연동되지 않은 걸 물으면, 아직 확인할 수 없다고 솔직히 답하고 \
대신 확인 가능한 지표(AI 응대, 쿠폰 사용 등)를 안내하세요.
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
        return self.llm.generate(system_prompt=system_prompt, user_message=understood["message"])
