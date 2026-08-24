import json

import routers._ai_common as ai_common_module
from services.llm.fake_provider import FakeLLMProvider


def _register_and_activate_business(client, email="reco-owner@example.com"):
    register = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": "사장", "role": "BUSINESS_OWNER"},
    )
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    business = client.post(
        "/api/v1/businesses",
        headers=headers,
        json={"name_ko": "영종 카페", "category": "CAFE", "address": "인천 중구 1"},
    ).json()
    client.patch(f"/api/v1/businesses/{business['id']}", headers=headers, json={"status": "ACTIVE"})
    return business


def test_recommendations_endpoint_returns_validated_structured_picks(client, monkeypatch):
    business = _register_and_activate_business(client)
    fake = FakeLLMProvider(
        response=json.dumps({"picks": [{"id": business["id"], "reason": "분위기가 좋아요"}]})
    )
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    response = client.post("/api/v1/recommendations", json={"query": "카페 추천해줘"})

    assert response.status_code == 200
    body = response.json()
    assert body["agent_type"] == "info"
    assert "영종 카페" in body["reply"]
    assert body["interaction_id"] is not None
    assert body["recommendations"] == [
        {
            "id": business["id"],
            "name": "영종 카페",
            "category": "CAFE",
            "source": "business",
            "reason": "분위기가 좋아요",
        }
    ]


def test_recommendations_endpoint_never_returns_hallucinated_entity(client, monkeypatch):
    """PILOT AUDIT TASK 2 - LLM이 후보 목록에 없는 id를 지목해도, API 응답의
    reply/recommendations 어디에도 그 항목이 나타나면 안 된다."""
    import uuid

    _register_and_activate_business(client)
    fake_id = str(uuid.uuid4())
    fake = FakeLLMProvider(response=json.dumps({"picks": [{"id": fake_id, "reason": "지어낸 이유"}]}))
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    response = client.post("/api/v1/recommendations", json={"query": "카페 추천해줘"})

    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"] == []
    assert fake_id not in body["reply"]
    assert "지어낸 이유" not in body["reply"]


def test_recommendations_endpoint_503_when_llm_not_configured(client, monkeypatch):
    from services.llm.gemini_provider import GeminiConfigurationError

    def _raise():
        raise GeminiConfigurationError("no key")

    monkeypatch.setattr(ai_common_module, "get_llm_provider", _raise)

    response = client.post("/api/v1/recommendations", json={"query": "카페 추천해줘"})
    assert response.status_code == 503


def test_recommendation_click_records_and_returns_row(client, monkeypatch):
    business = _register_and_activate_business(client)
    fake = FakeLLMProvider(response=json.dumps({"picks": [{"id": business["id"], "reason": "좋아요"}]}))
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    reco = client.post("/api/v1/recommendations", json={"query": "카페"}).json()

    response = client.post(
        f"/api/v1/recommendations/{reco['interaction_id']}/click",
        json={"entity_id": business["id"], "entity_type": "business"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["ai_interaction_id"] == reco["interaction_id"]
    assert body["entity_id"] == business["id"]
    assert body["entity_type"] == "business"


def test_recommendation_click_404s_for_unknown_interaction(client):
    import uuid

    response = client.post(
        f"/api/v1/recommendations/{uuid.uuid4()}/click",
        json={"entity_id": str(uuid.uuid4()), "entity_type": "business"},
    )
    assert response.status_code == 404


def test_recommendation_click_404s_for_unknown_entity(client, monkeypatch):
    import uuid

    business = _register_and_activate_business(client)
    fake = FakeLLMProvider(response=json.dumps({"picks": [{"id": business["id"], "reason": "좋아요"}]}))
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)
    reco = client.post("/api/v1/recommendations", json={"query": "카페"}).json()

    response = client.post(
        f"/api/v1/recommendations/{reco['interaction_id']}/click",
        json={"entity_id": str(uuid.uuid4()), "entity_type": "business"},
    )
    assert response.status_code == 404


def test_recommendation_click_rejects_malformed_interaction_id(client):
    """FRONTEND-TRACKING TASK 3 - path의 interaction_id가 UUID 형식조차 아니면
    FastAPI가 라우터 코드에 닿기 전에 422로 거부해야 한다."""
    response = client.post(
        "/api/v1/recommendations/not-a-uuid/click",
        json={"entity_id": "also-not-a-uuid", "entity_type": "business"},
    )
    assert response.status_code == 422


def test_recommendation_click_rejects_malformed_entity_id(client, monkeypatch):
    business = _register_and_activate_business(client)
    fake = FakeLLMProvider(response=json.dumps({"picks": [{"id": business["id"], "reason": "좋아요"}]}))
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)
    reco = client.post("/api/v1/recommendations", json={"query": "카페"}).json()

    response = client.post(
        f"/api/v1/recommendations/{reco['interaction_id']}/click",
        json={"entity_id": "not-a-uuid", "entity_type": "business"},
    )
    assert response.status_code == 422


def test_recommendation_click_rejects_invalid_entity_type(client, monkeypatch):
    import uuid

    business = _register_and_activate_business(client)
    fake = FakeLLMProvider(response=json.dumps({"picks": [{"id": business["id"], "reason": "좋아요"}]}))
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)
    reco = client.post("/api/v1/recommendations", json={"query": "카페"}).json()

    response = client.post(
        f"/api/v1/recommendations/{reco['interaction_id']}/click",
        json={"entity_id": str(uuid.uuid4()), "entity_type": "not_a_real_type"},
    )
    assert response.status_code == 422


def test_recommendation_click_allows_repeated_clicks(client, monkeypatch):
    """중복 클릭 방지는 의도적으로 frontend 책임(debounce)이다 - 백엔드는
    같은 interaction/entity 조합의 반복 클릭 자체를 막지 않는다(방문 의사
    신호를 여러 번 기록하는 것 자체는 무해함, Transaction 중복 집계와는
    다른 문제). 이 테스트는 그 설계를 문서화한다."""
    business = _register_and_activate_business(client)
    fake = FakeLLMProvider(response=json.dumps({"picks": [{"id": business["id"], "reason": "좋아요"}]}))
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)
    reco = client.post("/api/v1/recommendations", json={"query": "카페"}).json()

    first = client.post(
        f"/api/v1/recommendations/{reco['interaction_id']}/click",
        json={"entity_id": business["id"], "entity_type": "business"},
    )
    second = client.post(
        f"/api/v1/recommendations/{reco['interaction_id']}/click",
        json={"entity_id": business["id"], "entity_type": "business"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


def test_recommendation_click_requires_no_auth_by_design(client, monkeypatch):
    """FRONTEND-TRACKING TASK 3 보안 확인 - InfoAgent 추천은 로그인 없는
    공개 기능이라 AiInteraction 자체가 애초에 특정 사용자 소유가 아니다.
    "다른 사용자의 interaction_id를 조작"이라는 표현이 성립하려면 먼저
    interaction에 소유자가 있어야 하는데, 없다 - interaction_id를 아는
    누구나 같은 조건(비로그인)으로 클릭을 기록할 수 있는 게 의도된
    설계다. 클릭이 노출하거나 바꿀 수 있는 사적 데이터는 없다 - entity_id는
    이미 공개 목록 API(GET /businesses)로 조회 가능한 정보다. 이 테스트는
    Authorization 헤더를 전혀 보내지 않고도 정상 동작함을 명시적으로
    확인한다(다른 클릭 테스트들도 전부 헤더 없이 통과하지만, 여기서 그
    설계 의도를 이름 붙여 문서화한다)."""
    business = _register_and_activate_business(client)
    fake = FakeLLMProvider(response=json.dumps({"picks": [{"id": business["id"], "reason": "좋아요"}]}))
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)
    reco = client.post("/api/v1/recommendations", json={"query": "카페"}).json()

    response = client.post(
        f"/api/v1/recommendations/{reco['interaction_id']}/click",
        json={"entity_id": business["id"], "entity_type": "business"},
        headers={},
    )
    assert response.status_code == 201
