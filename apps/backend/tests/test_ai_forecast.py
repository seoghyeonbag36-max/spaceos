"""AI 공실 예측 API 테스트 — platform_vacancy_forecast.json 서빙 검증 (C단계)."""
from fastapi.testclient import TestClient

from app.main import app
from tests.test_districts import SEOUL_13_IDS

client = TestClient(app)
V1 = "/api/v1"


def test_predict_vacancy_all_13_districts():
    for did in SEOUL_13_IDS:
        r = client.post(f"{V1}/ai/predict-vacancy", json={"district_id": did})
        assert r.status_code == 200, did
        body = r.json()
        assert body["district_id"] == did
        assert isinstance(body["forecast_vac_proxy"], (int, float)), did
        assert body["direction"] in ("up", "down"), did
        assert body["model"].startswith("vacancy-lstm-pooled")
        assert body["metrics"]["holdout_direction_acc"] >= 0.70  # PPPP Phase1 목표


def test_predict_vacancy_unknown_district_404():
    r = client.post(f"{V1}/ai/predict-vacancy", json={"district_id": "nope"})
    assert r.status_code == 404


def test_district_summaries_carry_predicted_rate():
    """D단계 — 대시보드 응답에 다음 분기 예측 필드가 실려야 한다."""
    r = client.get(f"{V1}/commercial-districts")
    assert r.status_code == 200
    for d in r.json():
        assert d["predicted_rate"] is not None, d["id"]
        assert 0 <= d["predicted_rate"] <= 100
        assert d["predicted_direction"] in ("up", "down")


def test_heatmap_carries_predicted_rate():
    r = client.get(f"{V1}/heatmap/vacancy", params={"district": "garosugil"})
    assert r.status_code == 200
    hm = r.json()
    assert hm["predicted_rate"] is not None
    assert hm["predicted_direction"] in ("up", "down")
