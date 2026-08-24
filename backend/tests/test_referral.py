def test_referral_join_returns_404_for_unknown_token(client):
    response = client.get("/api/v1/referral/does-not-exist")
    assert response.status_code == 404
