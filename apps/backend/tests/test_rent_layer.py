"""Page 임대시세 레이어 — 격자 색이 아니라 **층·면적별 금액**을 내는가.

2026-09-13 에 응답을 100m 격자(`cells`)에서 층 표(`floors`) + 층 단위 매물 금액
(`listings`)으로 바꿨다(services/rent_layer 독스트링). 여기서 못 박는 것:
  1. 금액이 Posting `rent` 와 같은 식에서 나오는가 — 두 화면이 다른 금액을 내면 안 된다
  2. 층 계수가 금액에 실제로 들어가는가 — 2층이 1층보다 평당 싸야 한다
  3. R-ONE 이 없으면 0 이나 이웃 값으로 채우지 않고 404 인가
"""
from fastapi.testclient import TestClient

from app.main import app
from app.services import posting_inputs

client = TestClient(app)
V1 = "/api/v1"


def _get(district: str = "garosugil"):
    return client.get(f"{V1}/heatmap/rent", params={"district": district})


def test_rent_layer_uses_rone_source():
    r = _get()
    assert r.status_code == 200
    body = r.json()
    assert body["rent_source"] in ("rone", "rone-shared")
    assert body["unit"] == "만원/평"
    assert body["monthly_unit"] == "만원/월"
    # 격자는 더 이상 내지 않는다 — 금액이 없는 색 칸이 되돌아오면 이 테스트가 운다.
    assert "cells" not in body


def test_rent_layer_omits_districts_without_rone(monkeypatch):
    from app.services import rent_layer

    monkeypatch.setattr(rent_layer.posting_inputs, "for_district", lambda district_id: None)
    r = _get()
    assert r.status_code == 404
    assert "listings" not in r.json()


def test_listing_monthly_rent_matches_posting_formula():
    """월임대료 = R-ONE(천원/㎡·월) × 층 면적(㎡) × 층 계수 ÷ 10 — Posting `rent` 와 같은 식."""
    body = _get().json()
    base = body["base_rent_per_m2_krw_thousand"]
    assert body["listings"], "가로수길은 층 단위 공실 매물이 있다(vacant_floor_units.json)"
    for x in body["listings"]:
        factor = posting_inputs.floor_factor(x["floor_label"])
        assert x["factor"] == factor
        assert x["monthly_rent"] == max(1, round(base * x["area_m2"] * factor / 10))
        assert x["monthly_rent"] > 0
    assert body["listing_count"] == len(body["listings"])
    assert body["monthly_min"] == min(x["monthly_rent"] for x in body["listings"])
    assert body["monthly_max"] == max(x["monthly_rent"] for x in body["listings"])


def test_floor_table_applies_floor_factor():
    body = _get().json()
    per = {row["floor"]: row["rent_per_pyeong"] for row in body["floors"]}
    assert per["1F"] == body["base_rent_per_pyeong"]
    # 상층은 1층보다 싸다 — 계수가 금액에 안 들어가면 전부 같은 값이 된다.
    assert per["2F"] < per["1F"]
    assert per["4F+"] < per["2F"]


def test_listings_carry_certainty_and_exclusions():
    """확정/추정 공실을 섞지 않고, 금액에 빠진 항목(보증금·권리금)을 밝힌다."""
    body = _get().json()
    assert {x["certainty"] for x in body["listings"]} <= {"confirmed", "probable"}
    assert "보증금" in body["excludes"] and "권리금" in body["excludes"]
