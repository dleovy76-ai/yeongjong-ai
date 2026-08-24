import routers.businesses as businesses_router
from models import Business
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
            [
                NaverLocalResult(
                    title="영종면옥 칼국수",
                    road_address="인천광역시 영종구 영종진광장로 45 101호",
                    category="한식",
                    lon=126.5785881,
                    lat=37.4956827,
                )
            ]
        ),
    )

    response = client.get(f"/api/v1/businesses/{business['id']}/naver-lookup", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["title"] == "영종면옥 칼국수"
    # owner-facing verification link: coordinate-anchored map pin
    assert body["map_url"] == "https://map.naver.com/?lng=126.5785881&lat=37.4956827&title=%EC%98%81%EC%A2%85%EB%A9%B4%EC%98%A5%20%EC%B9%BC%EA%B5%AD%EC%88%98"
    # customer-facing link: the real search results page (reviews/hours), not a bare map pin
    assert body["naver_url"] == "https://search.naver.com/search.naver?where=nexearch&query=%EC%98%81%EC%A2%85%EB%A9%B4%EC%98%A5%20%EC%B9%BC%EA%B5%AD%EC%88%98"


def test_naver_lookup_falls_back_unverified_when_no_match(client, monkeypatch):
    headers = _register(client, "naver-lookup2@example.com")
    business = _create_business(client, headers)

    monkeypatch.setattr(
        businesses_router,
        "NaverLocalApiClient",
        lambda: _FakeClient(
            [
                NaverLocalResult(
                    title="전혀 다른 가게",
                    road_address="서울특별시 강남구 어딘가 1",
                    category="카페",
                    lon=127.0276,
                    lat=37.4979,
                )
            ]
        ),
    )

    response = client.get(f"/api/v1/businesses/{business['id']}/naver-lookup", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is False
    assert body["title"] == "영종면옥"
    assert "search.naver.com" in body["naver_url"]
    # business has no lon/lat on record yet, so the pin link falls back to text search
    assert "map.naver.com/p/search/" in body["map_url"]


def test_naver_lookup_falls_back_to_coordinates_when_business_has_them(client, monkeypatch, db_session):
    headers = _register(client, "naver-lookup-fallback@example.com")
    business = _create_business(client, headers)
    db_session.query(Business).filter(Business.id == business["id"]).update(
        {"lon": 126.578574, "lat": 37.49567}
    )
    db_session.commit()

    monkeypatch.setattr(businesses_router, "NaverLocalApiClient", lambda: _FakeClient([]))

    response = client.get(f"/api/v1/businesses/{business['id']}/naver-lookup", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is False
    assert "map.naver.com" in body["map_url"]
    assert "lng=126.578574" in body["map_url"]
    assert "lat=37.49567" in body["map_url"]


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
