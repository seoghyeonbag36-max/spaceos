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


def test_predict_vacancy_horizon_selection():
    """horizon_months → 분기 환산(올림, 1~4 클램프) + horizons 재귀 예측 선택."""
    r1 = client.post(f"{V1}/ai/predict-vacancy", json={"district_id": "garosugil"})
    r6 = client.post(f"{V1}/ai/predict-vacancy",
                     json={"district_id": "garosugil", "horizon_months": 6})
    b1, b6 = r1.json(), r6.json()
    assert b1["horizon_quarters"] == 1
    assert b6["horizon_quarters"] == 2
    assert len(b1["horizons"]) == 4
    assert b6["forecast_vac_proxy"] == b1["horizons"][1]["forecast_vac_proxy"]
    # 12개월(4분기) 초과분은 4로 클램프
    b24 = client.post(f"{V1}/ai/predict-vacancy",
                      json={"district_id": "garosugil", "horizon_months": 24}).json()
    assert b24["horizon_quarters"] == 4


def test_predict_vacancy_garosugil_ground_anchor():
    """garosugil 은 PoC 지상검증 실측 앵커가 응답에 부착돼야 한다."""
    body = client.post(f"{V1}/ai/predict-vacancy", json={"district_id": "garosugil"}).json()
    anchor = body.get("ground_anchor")
    assert anchor and anchor["estimated_vacancy_pct"] == 39.1
    # 앵커 미보유 거점에는 없어야 한다
    body2 = client.post(f"{V1}/ai/predict-vacancy", json={"district_id": "hongdae"}).json()
    assert "ground_anchor" not in body2


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
