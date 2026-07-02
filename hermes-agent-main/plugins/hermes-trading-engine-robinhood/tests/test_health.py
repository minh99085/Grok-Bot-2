from fastapi.testclient import TestClient

from engine.app import app


def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["plugin"] == "hermes-trading-engine-robinhood"