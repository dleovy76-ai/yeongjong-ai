import routers.businesses as businesses_router
from services.external.naver_local_api import NaverLocalResult


def _register(client, email, role="BUSINESS_OWNER"):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": "테스트", "role": role},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_business(client, headers):
    response = client.post(
        "/api/v1/businesses",
        headers=headers,
        json={"name_ko": "영종면옥", "category": "RESTAURANT", "address": "인천광역시 영종구 영종진광장로 45"},
    )
    assert response.status_code == 201, response.text
    return response.json()


class _FakeClient:
    def __init__(self, results):
        self._results = results

    def search(self, query, display=5):
        return self._results


def test_naver_lookup_marks_verified_on_matching_address(client, monkeypatch):
    headers = _register(client, "naver-lookup1@example.com")
    business = _create_business(client, headers)

    monkeypatch.setattr(
        businesses_router,
        "NaverLocalApiClient",
        lambda: _FakeClient(
            [NaverLocalResult(title="영종면옥 칼국수", road_address="인천광역시 영종구 영종진광장로 45 101호", category="한식")]
        ),
    )

    response = client.get(f"/api/v1/businesses/{business['id']}/naver-lookup", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["title"] == "영종면옥 칼국수"
    assert "map.naver.com" in body["map_url"]


def test_naver_lookup_falls_back_unverified_when_no_match(client, monkeypatch):
    headers = _register(client, "naver-lookup2@example.com")
    business = _create_business(client, headers)

    monkeypatch.setattr(
        businesses_router,
        "NaverLocalApiClient",
        lambda: _FakeClient(
            [NaverLocalResult(title="전혀 다른 가게", road_address="서울특별시 강남구 어딘가 1", category="카페")]
        ),
    )

    response = client.get(f"/api/v1/businesses/{business['id']}/naver-lookup", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is False
    assert body["title"] == "영종면옥"


def test_naver_lookup_requires_owner(client, monkeypatch):
    headers = _register(client, "naver-lookup3@example.com")
    business = _create_business(client, headers)
    other_headers = _register(client, "naver-lookup4@example.com")

    monkeypatch.setattr(businesses_router, "NaverLocalApiClient", lambda: _FakeClient([]))

    response = client.get(f"/api/v1/businesses/{business['id']}/naver-lookup", headers=other_headers)
    assert response.status_code == 403


def test_naver_lookup_requires_auth(client):
    headers = _register(client, "naver-lookup5@example.com")
    business = _create_business(client, headers)

    response = client.get(f"/api/v1/businesses/{business['id']}/naver-lookup")
    assert response.status_code == 401
