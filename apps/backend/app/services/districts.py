"""거점(commercial district) 도메인 서비스.

공실 집계의 입력은 **Gold 실데이터 우선**이다 (2026-08-01 배선 교체).
- 실측 거점(40곳 — 2026-08-15 실측): 실측 건물을 100m 셀로 집계 (services/gold_vacancy).
  응답의 `vacancy_source == "gold"`.
- 나머지 14곳: 기존 `build_cells()` 합성 그리드로 폴백. `vacancy_source == "synthetic"`.
  → 해당 거점의 대장을 받아 파이프라인을 돌리면 자동으로 실데이터로 바뀐다.

갈림길은 **파일 존재가 아니다.** `page_building_master.geojson` 은 이제 54거점 전부에 있다
(대장 없는 거점도 폴리곤 근사로 만든다 — Tier2). `gold_vacancy.build_cells()` 가 셀을 만들려면
`_COUNTED_METHODS = {"floor_ouln"}` 인 건물이 있어야 하므로, 실질 조건은 **층별개요까지 받았는가**
다. 파일 존재를 실측의 대리지표로 쓰면 Tier2 거점을 실측으로 오분류한다(13거점 시절엔 둘이
일치해서 성립했던 가정).

아직 시드(app/data/seoul_pages.py)에 남아 있는 것: 감성 zones·입점 units·행사 events.
TODO: 감성은 리뷰 감성분석, units 의 rent/prem 은 R-ONE 조인으로 교체.
"""
from __future__ import annotations

import math

from app.data.seoul_pages import DISTRICTS, DISTRICTS_BY_ID
from app.services import gold_vacancy, posting_inputs, vacancy_forecast

# 입점 3-Tier 정의
TIER = {
    "premium": {"nm": "고급화", "sub": "Premium"},
    "value": {"nm": "가성비", "sub": "Value"},
    "factory": {"nm": "공장제", "sub": "Standardized"},
}
_FOOT_K = {"저": 0.8, "중": 1.0, "고": 1.25}


def _dist_m(a: float, b: float, c: float, d: float) -> float:
    dy = (a - c) * 111000
    dx = (b - d) * 88300
    return math.sqrt(dx * dx + dy * dy)


def _seed(i: int, j: int) -> float:
    x = math.sin(i * 12.9898 + j * 78.233) * 43758.5453
    return x - math.floor(x)


def cells_for(d: dict) -> dict:
    """거점의 100m 공실 셀 — Gold 실데이터 우선, 없으면 합성 폴백.

    `vacancy_source` 로 어느 쪽인지 항상 밝힌다(추측 최소화 원칙 — 합성값이 실측처럼
    보이면 안 된다). Gold 경로는 capacity/buildings/precision_pct 메타를 더 얹는다.
    """
    gold = gold_vacancy.build_cells(d["id"], d["grid"])
    if gold is not None:
        return {**gold, "vacancy_source": "gold"}
    return {**build_cells(d["grid"]), "vacancy_source": "synthetic"}


def build_cells(grid: dict) -> dict:
    """100m 그리드 공실 셀 **합성** — Gold 미보유 거점 폴백. 프론트 buildCells와 동일 결과.

    반환: {cells: [...], sum_stores, sum_vac, avg_vacancy}
    """
    bb, dlat, dlng = grid["bb"], grid["dlat"], grid["dlng"]
    core, maxd, hot = grid["core"], grid["maxd"], grid["hot"]
    cells: list[dict] = []
    sum_stores = sum_vac = 0
    i = 0
    lat = bb["s"]
    while lat < bb["n"] - 1e-9:
        j = 0
        lng = bb["w"]
        while lng < bb["e"] - 1e-9:
            c_lat = lat + dlat / 2
            c_lng = lng + dlng / 2
            v = 2.5
            infl = 0.0
            for h in hot:
                dd = _dist_m(c_lat, c_lng, h[0], h[1])
                w = math.exp(-(dd * dd) / (2 * h[2] * h[2]))
                v += h[3] * w
                infl += w
            v += (_seed(i, j) - 0.5) * 4
            dc = _dist_m(c_lat, c_lng, core[0], core[1])
            if infl > 0.12 and dc < maxd:
                v = max(2.0, min(48.0, v))
                stores = round(8 + 22 * min(1.0, infl) + _seed(j, i) * 10)
                vac_n = round(stores * v / 100)
                cells.append({
                    "i": i, "j": j, "lat": lat, "lng": lng,
                    "c_lat": round(c_lat, 6), "c_lng": round(c_lng, 6),
                    "v": round(v, 2), "stores": stores, "vac_n": vac_n,
                    "dlat": dlat, "dlng": dlng,
                })
                sum_stores += stores
                sum_vac += vac_n
            j += 1
            lng += dlng
        i += 1
        lat += dlat
    avg = (sum_vac / sum_stores * 100) if sum_stores else 0.0
    return {"cells": cells, "sum_stores": sum_stores, "sum_vac": sum_vac, "avg_vacancy": round(avg, 2)}


def tier_scenarios(unit: dict) -> dict:
    """공실 유닛의 3-Tier 비용-효용 시나리오(월 단위, 만원/백만원)."""
    f_k = _FOOT_K[unit["foot"]]
    base = unit["area"] * f_k
    rent, area, prem = unit["rent"], unit["area"], unit["prem"]

    def roi(invest_mn: float, cost: float, rev: float) -> float:
        """투자 회수기간(개월). invest 는 **백만원**, cost/rev 는 **만원** 단위다.

        2026-08-01 수정: 이전에는 `invest / net` 이라 단위가 섞여(백만원 ÷ 만원)
        회수기간이 100배 작게 나왔다 — 화면에 "회수 0개월 / 0.1개월"로 찍히고 있었다.
        1백만원 = 100만원 이므로 invest 를 만원으로 맞춘 뒤 나눈다.
        """
        net = rev - cost
        return 99.0 if net <= 0 else round(invest_mn * 100 / net, 1)

    out = {}
    specs = {
        "premium": (round(prem / 100 + area * 0.55 + 4), round(rent + area * 1.8 + 180), round(base * 41 + 1150)),
        "value": (round(prem / 100 + area * 0.32 + 2.2), round(rent + area * 1.1 + 95), round(base * 30 + 760)),
        "factory": (round(prem / 100 + area * 0.2 + 1.1), round(rent + area * 0.45 + 25), round(base * 18 + 430)),
    }
    for k, (inv, cost, rev) in specs.items():
        out[k] = {
            "tier": k, "name": TIER[k]["nm"], "sub": TIER[k]["sub"],
            "invest_mn": inv, "month_cost": cost, "month_rev": rev,
            "month_net": rev - cost, "roi_months": roi(inv, cost, rev),
            "recommended": k == unit["rec"],
        }
    return out


def _predicted(district_id: str, current_rate: float) -> dict:
    """LSTM forecast 의 vac_proxy delta(%p 근사)를 현재 공실률에 가산한 다음 분기 근사.

    forecast json 부재/미지원 거점이면 세 필드 모두 None (프론트는 배지 숨김).
    """
    f = vacancy_forecast.all_forecasts().get(district_id)
    if not f:
        return {"predicted_rate": None, "predicted_delta": None, "predicted_direction": None}
    delta = float(f.get("delta", 0.0))
    return {
        "predicted_rate": round(max(0.0, min(100.0, current_rate + delta)), 2),
        "predicted_delta": round(delta, 2),
        "predicted_direction": f.get("direction"),
    }


def _summary(d: dict) -> dict:
    sum_r = sum(z["r"] for z in d["zones"])
    sent = sum(z["s"] * z["r"] for z in d["zones"]) / sum_r
    risk = sum(1 for z in d["zones"] if z["s"] < 40)
    ci = cells_for(d)
    tiers = {k: sum(1 for u in d["units"] if u["rec"] == k) for k in TIER}
    rec_top = TIER[d["units"][0]["rec"]]["nm"] if d["units"] else ""
    return {
        "id": d["id"], "name": d["name"], "gu": d["gu"], "type": d["type"],
        "center": d["center"], "note": d["sub"], "rec_top": rec_top,
        "sentiment": round(sent, 1), "reviews": sum_r, "risk_zones": risk,
        "vacancy_rate": ci["avg_vacancy"], "vacant_units": ci["sum_vac"],
        "cell_count": len(ci["cells"]), "store_count": ci["sum_stores"],
        "tier_mix": tiers,
        "vacancy_source": ci["vacancy_source"],
        "building_count": ci.get("buildings"),
        "precision_pct": ci.get("precision_pct"),
        "anchor_pct": ci.get("anchor_pct"),
        "anchor_gap_pp": ci.get("anchor_gap_pp"),
        **_predicted(d["id"], ci["avg_vacancy"]),
    }


def list_summaries() -> list[dict]:
    """거점 요약(감성·공실·리뷰·Tier) 목록 — City Dashboard 용."""
    return [_summary(d) for d in DISTRICTS]


def get_summary(district_id: str) -> dict | None:
    d = DISTRICTS_BY_ID.get(district_id)
    return _summary(d) if d else None


def get_district(district_id: str) -> dict | None:
    """거점 전체 원천 데이터(zones/units/events/poi/grid)."""
    return DISTRICTS_BY_ID.get(district_id)


def get_sentiment(district_id: str) -> list[dict] | None:
    d = DISTRICTS_BY_ID.get(district_id)
    return d["zones"] if d else None


def get_vacancy_heatmap(district_id: str) -> dict | None:
    d = DISTRICTS_BY_ID.get(district_id)
    if not d:
        return None
    ci = cells_for(d)
    return {"district_id": district_id, "resolution_m": 100, **ci,
            **_predicted(district_id, ci["avg_vacancy"])}


def resolved_units(district_id: str) -> list[dict] | None:
    """거점의 공실 유닛 — rent·foot 은 실데이터로 덮어쓴 뒤 돌려준다.

    시드 원본(seoul_pages.DISTRICTS)은 건드리지 않는다(프로세스 전역 공유 dict 다).
    각 유닛의 `inputs_source` 가 필드별 출처(seed/rone/flpop)를 밝힌다.
    """
    d = DISTRICTS_BY_ID.get(district_id)
    if not d:
        return None
    return posting_inputs.resolve_units(district_id, d["units"])


def get_postings(district_id: str) -> list[dict] | None:
    units = resolved_units(district_id)
    if units is None:
        return None
    return [{**u, "scenarios": tier_scenarios(u)} for u in units]


def get_marketing(district_id: str) -> dict | None:
    d = DISTRICTS_BY_ID.get(district_id)
    if not d:
        return None
    return {"district_id": district_id, "events": d["events"], "online_contents": d["insta"]}
