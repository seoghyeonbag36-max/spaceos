"""거점(commercial district) 도메인 서비스.

정적 시드 데이터(app/data/seoul_pages.py — 서울 13 Page 거점)를 기반으로
공실 그리드 합성·집계를 수행한다.
TODO: Gold 레이어(매출·공실·감성) 적재 후 이 서비스의 입력을 DB 조회로 교체.
"""
from __future__ import annotations

import math

from app.data.seoul_pages import DISTRICTS, DISTRICTS_BY_ID

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


def build_cells(grid: dict) -> dict:
    """100m 그리드 공실 셀 합성. 프론트 buildCells와 동일 결과.

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

    def roi(invest: float, cost: float, rev: float) -> float:
        net = rev - cost
        return 99.0 if net <= 0 else round(invest / net, 1)

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


def _summary(d: dict) -> dict:
    sum_r = sum(z["r"] for z in d["zones"])
    sent = sum(z["s"] * z["r"] for z in d["zones"]) / sum_r
    risk = sum(1 for z in d["zones"] if z["s"] < 40)
    ci = build_cells(d["grid"])
    tiers = {k: sum(1 for u in d["units"] if u["rec"] == k) for k in TIER}
    rec_top = TIER[d["units"][0]["rec"]]["nm"] if d["units"] else ""
    return {
        "id": d["id"], "name": d["name"], "gu": d["gu"], "type": d["type"],
        "center": d["center"], "note": d["sub"], "rec_top": rec_top,
        "sentiment": round(sent, 1), "reviews": sum_r, "risk_zones": risk,
        "vacancy_rate": ci["avg_vacancy"], "vacant_units": ci["sum_vac"],
        "cell_count": len(ci["cells"]), "store_count": ci["sum_stores"],
        "tier_mix": tiers,
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
    ci = build_cells(d["grid"])
    return {"district_id": district_id, "resolution_m": 100, **ci}


def get_postings(district_id: str) -> list[dict] | None:
    d = DISTRICTS_BY_ID.get(district_id)
    if not d:
        return None
    return [{**u, "scenarios": tier_scenarios(u)} for u in d["units"]]


def get_marketing(district_id: str) -> dict | None:
    d = DISTRICTS_BY_ID.get(district_id)
    if not d:
        return None
    return {"district_id": district_id, "events": d["events"], "online_contents": d["insta"]}
