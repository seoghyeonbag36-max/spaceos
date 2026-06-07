"""기본 헬스체크 / API 골격 검증 테스트."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_building_history():
    resp = client.get("/api/v1/buildings/B001/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["building_id"] == "B001"
    assert isinstance(body["history"], list)
