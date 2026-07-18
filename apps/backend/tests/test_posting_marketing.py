"""Posting(코파일럿 어댑터) / Program(가게 단위 생성) API 테스트."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
V1 = "/api/v1"


def test_simulate_revenue_fallback():
    """코파일럿 미설정 시 3-Tier 폴백으로 응답한다."""
    r = client.post(f"{V1}/ai/simulate-revenue", json={"district_id": "lafesta"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "fallback-3tier"
    assert set(body["scenarios"].keys()) == {"premium", "value", "factory"}
    for sc in body["scenarios"].values():
        assert sc["roi_months"] >= 0  # round(invest/net,1)이 0.0일 수 있음(순이익 대비 소액 투자)


def test_simulate_revenue_strategy_filter():
    r = client.post(f"{V1}/ai/simulate-revenue",
                    json={"district_id": "lafesta", "strategy": "value"})
    assert r.status_code == 200
    assert set(r.json()["scenarios"].keys()) == {"value"}


def test_simulate_revenue_unknown_district_404():
    r = client.post(f"{V1}/ai/simulate-revenue", json={"district_id": "nope"})
    assert r.status_code == 404


def test_generate_store_marketing_stub():
    """LLM 키 미설정 시 규칙 기반 스텁이 StoreMarketing 스키마로 응답한다."""
    profile = {
        "name": "가로수 카페",
        "category": "카페",
        "district_id": "gangnam-garosugil",
        "reviews": ["분위기 좋은 카페", "커피 맛집 분위기 최고", "디저트 맛집"],
    }
    r = client.post(f"{V1}/marketing/generate", json=profile)
    assert r.status_code == 200
    body = r.json()
    assert body["store_name"] == "가로수 카페"
    assert body["source"] == "rule-stub"
    assert body["tone_keywords"]  # 리뷰에서 키워드 추출됨
    assert len(body["online"]) >= 1 and len(body["offline"]) >= 1
    assert all(p["kind"] == "online" for p in body["online"])
    assert all(p["kind"] == "offline" for p in body["offline"])


def test_district_marketing_still_served():
    """상권 단위 GET /marketing/{id} 는 기존대로 동작(시드 — Gold 교체 TODO)."""
    r = client.get(f"{V1}/marketing/lafesta")
    assert r.status_code == 200
    assert "events" in r.json()
