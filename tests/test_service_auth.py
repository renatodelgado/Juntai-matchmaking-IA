from fastapi.testclient import TestClient
from app.main import app


def test_service_requires_shared_key(monkeypatch):
    monkeypatch.setenv("MATCHMAKING_API_KEY", "isolated-test-key")
    monkeypatch.setenv("MATCHMAKING_REQUIRE_AUTH", "true")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/").status_code == 401
        assert client.get("/", headers={"x-matchmaking-key": "wrong"}).status_code == 401
        assert client.get("/", headers={"x-matchmaking-key": "isolated-test-key"}).status_code == 200
        assert client.post("/match/rules", json={}).status_code == 401


def test_required_auth_fails_closed_without_key(monkeypatch):
    monkeypatch.delenv("MATCHMAKING_API_KEY", raising=False)
    monkeypatch.setenv("MATCHMAKING_REQUIRE_AUTH", "true")
    with TestClient(app) as client:
        assert client.get("/").status_code == 503
