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
        assert body["model"] == "vacancy-lstm-pooled-v1"
        assert body["metrics"]["holdout_direction_acc"] >= 0.70  # PPPP Phase1 목표


def test_predict_vacancy_unknown_district_404():
    r = client.post(f"{V1}/ai/predict-vacancy", json={"district_id": "nope"})
    assert r.status_code == 404
