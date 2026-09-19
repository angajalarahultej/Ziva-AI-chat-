from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_conversation_crud():
    r = client.post("/api/conversations", json={"title": "t"})
    assert r.status_code == 200
    cid = r.json()["id"]
    r = client.get(f"/api/conversations/{cid}/messages")
    assert r.status_code == 200
