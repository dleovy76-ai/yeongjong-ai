import json

from services.agents.base import BaseAgent
from services.tools import BusinessSearchTool, PartnerSearchTool

_NO_CANDIDATES_MESSAGE = "[]"

_SYSTEM_PROMPT_TEMPLATE = """당신은 영종 AI의 Expansion AI입니다. 아래 [분석 대상 업체]와 협업(상호 추천, 제휴)하면 \
좋을 만한 곳을 [후보 업체 목록]에서만 최대 5곳 골라 JSON 배열로 응답하세요.

규칙:
- [후보 업체 목록]에 없는 business_id를 만들어내거나 목록 밖의 업체를 언급하지 마세요.
- 같은 카테고리(예: 음식점-음식점)는 이미 후보에서 제외되어 있습니다 - 방문객 동선상 자연스럽게 이어지는 \
조합(숙박-음식점, 음식점-카페, 체험-음식점 등)을 우선하세요.
- distance_m이 가까울수록, is_claimed가 true(이미 활성 사용자가 있는 업체)일수록 실제 제휴가 성사되기 쉬우니 \
가점 요소로 고려하세요. distance_m이 null이면 거리 정보가 없다는 뜻이니 거리로 판단하지 마세요.
- 각 추천에 score(1-100 정수)와 그렇게 판단한 reason(한국어, 100자 이내)을 반드시 포함하세요.
- 다른 설명 없이 JSON 배열만 응답하세요. 형식: [{{"business_id": "...", "score": 85, "reason": "..."}}]

[분석 대상 업체]
{target_json}

[후보 업체 목록]
{candidates_json}
"""


class ExpansionAgent(BaseAgent):
    """Master plan §20-23 - suggests real complementary businesses (already in
    the DB, claimed or still-unclaimed) worth partnering with. Does not send
    invitations itself (§24/25) - this agent only produces ranked, grounded
    suggestions for the router to persist as BusinessRelationship rows.

    context: {"business_id": UUID}
    """

    agent_type = "expansion"

    def retrieve(self, context: dict, understood: dict) -> dict:
        business_id = context["business_id"]
        business_tool = BusinessSearchTool(self.db)
        partner_tool = PartnerSearchTool(self.db)

        target_context = business_tool.get_context(business_id)
        if target_context is None:
            return {"target": None, "candidates": []}

        decided = partner_tool.decided_relationship_ids(business_id)
        candidates = [
            c for c in partner_tool.find_candidates(business_id) if c["id"] not in {str(x) for x in decided}
        ]
        return {"target": target_context, "candidates": candidates}

    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        if decided["target"] is None or not decided["candidates"]:
            return _NO_CANDIDATES_MESSAGE

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            target_json=json.dumps(decided["target"], ensure_ascii=False),
            candidates_json=json.dumps(decided["candidates"], ensure_ascii=False, indent=2),
        )
        # Up to 5 items x Korean reasoning text comfortably exceeds the 1024-token
        # default other (single-answer) agents use - confirmed live that 1024
        # silently truncates this agent's output mid-JSON.
        return self._call_llm(system_prompt=system_prompt, user_message="분석해줘", max_output_tokens=2048)
