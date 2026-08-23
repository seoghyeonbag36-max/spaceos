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
from app.services import (gold_vacancy, posting_inputs, posting_revenue,
                          vacancy_forecast)

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


def recommend_tier(scenarios: dict) -> str | None:
    """추천 전략 = **회수 최단**. 순익이 0 이하인(회수 불가) 전략은 후보에서 뺀다.

    ## 기준을 이것으로 정한 이유 (2026-08-16 제품 정의)

    `rec` 은 여태 시드에 손으로 적혀 있었고 기준이 정의된 적이 없었다. 그 값이
    54거점 카드의 `tier_mix`·`rec_top` 으로 그대로 노출되고 있었다.

    후보는 셋이었다 — 회수 최단 / 순익 최대 / 리스크 최소. **회수 최단**을 고른 것은
    `roi_months` 가 이미 계산돼 추가 데이터가 필요 없고, 공실에 새로 들어가는 기업에게
    "언제 본전을 찾는가"가 가장 직결되는 질문이기 때문이다. 리스크 최소는 리스크를
    잴 지표가 없고, 순익 최대는 투자 규모를 무시해 항상 최상위 전략을 고른다.

    동률이면 순익이 큰 쪽을 고른다 — 같은 기간에 회수한다면 더 버는 쪽이 낫다.

    ## ⚠ 이 값이 기대는 계산은 아직 보정되지 않았다

    `tier_scenarios` 의 `month_cost` 에 **원가·인건비가 없다.** 2026-08-22 실 유닛
    270건 전수 재측정: 마진 중앙 70.1%(premium) / 63.5%(value) / 45.9%(factory),
    회수 중앙 1.8개월, `factory` 1위 **0건**. 37,800 조합 스윕에서도 factory 는 8건
    (0.02%)만 이기고 그나마 전부 `prem=0` · `rent≤150만원` 이라 실 인벤토리(최저
    임대료 195만원) 밖이다. 즉 추천이 셋 중 둘로만 갈린다 — 기준이 아니라 **비용
    모델이 병목**이다.

    그럼에도 손으로 적은 값보다는 낫다: 계산이 드러나 있고 재현되며, 비용 모델이
    보정되면 추천이 자동으로 따라온다. 한계는 각 시나리오의 `basis` 가 함께 내려간다.

    ## 비교는 반올림 전 값으로 한다 (2026-08-22)

    예전에는 `roi_months`(소수 1자리)와 `invest_mn`(정수)을 **반올림한 뒤** 비교했다.
    반올림이 인위적 동률을 만들고, 동률이면 순익 큰 쪽으로 가므로 그 표가 전부
    premium 에 쏠렸다 — 실 유닛 270건 중 **14건(5.2%)이 반올림 때문에** premium 으로
    넘어가 있었다(199/71 → 185/85). `invest_mn` 은 백만원 단위 정수라 factory 의
    9백만원에서는 눈금이 11% 나 된다. 그래서 `_raw` 원값으로 고르고 표시만 반올림한다.
    """
    def raw(s: dict) -> dict:
        # `_raw` 는 tier_scenarios 가 반환 직전에 떼어 낸다. 밖에서 이미 완성된
        # 시나리오를 넘겨 온 경우(표시값만 남은 dict)에도 동작하도록 되돌린다.
        return s.get("_raw") or {"roi": s["roi_months"], "net": s["month_net"]}

    viable = [s for s in scenarios.values() if raw(s)["net"] > 0]
    if not viable:
        return None
    return min(viable, key=lambda s: (raw(s)["roi"], -raw(s)["net"]))["tier"]


# 계산에 실제로 들어간 비용 항목. 마진·회수기간을 읽는 쪽이 무엇이 빠졌는지 알아야
# 한다 — 이 문자열이 응답의 `basis` 로 내려간다(예전 docstring 이 `roi_basis` 라는
# 필드가 있다고 적어 뒀으나 그런 필드는 구현된 적이 없다. 2026-08-22 실제로 만든다).
# 계산에 실제로 들어간 항목을 밝히는 문자열. 응답의 `basis` 로 내려간다.
# 두 모델이 공존한다 — 실측 재료가 있는 거점은 measured, 없으면 legacy 로 폴백하고
# **어느 쪽이 돌았는지 카드가 구분할 수 있어야 한다.** 조용히 폴백하면 근거 없는 값이
# 실측처럼 읽힌다(calibration.json 이 40거점에서 None 이던 것과 같은 실패 양식).
COST_BASIS = "kosis-opex+measured-revenue"
COST_BASIS_NOTE = ("월비용 = 임대료(R-ONE 실측) + 매출 × 비임차 영업비용률"
                   "(KOSIS 서울 2024). 매출은 거점별 실측 평당매출 × 면적 — 고정항 "
                   "없이 면적에 비례한다. ⚠ 평균 점포 면적 A 가 **하한**이라 마진이 "
                   "낙관 쪽으로 치우친다(docs/feature-posting.md §0-H).")

COST_BASIS_LEGACY = "rent+fitout"
COST_BASIS_LEGACY_NOTE = ("월비용 = 임대료 + 면적비례 관리비 + 고정비. **원가(매출비례)와 "
                          "인건비가 빠져 있어 마진이 과대, 회수기간이 과소하게 나온다.** "
                          "실측 재료(거점 매출·KOSIS 비용률)가 없어 폴백한 결과다.")


def basis_note(basis: str) -> str:
    """`basis` 문자열에 맞는 한계 설명. 카드가 두 모델을 구분해 보여주게 한다."""
    return COST_BASIS_NOTE if basis == COST_BASIS else COST_BASIS_LEGACY_NOTE


def tier_scenarios(unit: dict, district_id: str | None = None) -> dict:
    """공실 유닛의 3-Tier 비용-효용 시나리오(월 단위, 만원/백만원).

    `district_id` 를 주면 **실측 모델**로 계산한다(2026-08-23):

        rev  = area × foot_k_norm × 거점별 실측 평당매출[tier]
        cost = rent + rev × 비임차 영업비용률[tier]        # KOSIS 서울 2024

    안 주거나 그 거점에 재료가 없으면 낡은 계수 모델로 폴백한다. 어느 쪽이 돌았는지는
    각 시나리오의 `basis` 에 실린다 — **폴백을 조용히 하지 않는 것**이 요점이다.

    표시값(`invest_mn`·`month_cost`·`month_rev`·`roi_months`)은 반올림하되, 추천
    비교에 쓰는 값은 `_raw` 에 원값으로 함께 싣는다 — 반올림이 추천을 뒤집던 것을
    막는다(경위는 `recommend_tier` docstring).
    """
    f_k = _FOOT_K[unit["foot"]]
    base = unit["area"] * f_k
    rent, area, prem = unit["rent"], unit["area"], unit["prem"]
    measured = posting_revenue.available(district_id)

    # (투자계수·투자고정, 비용계수·비용고정, 매출계수·매출고정)
    # ⚠ 매출계수 41/30/18 과 비용계수는 근거 없는 손으로 적은 값이다. 실측 모델이
    #    설 수 없는 거점에서만 쓰인다(services/posting_revenue).
    specs = {
        "premium": (0.55, 4, 1.8, 180, 41, 1150),
        "value": (0.32, 2.2, 1.1, 95, 30, 760),
        "factory": (0.2, 1.1, 0.45, 25, 18, 430),
    }
    out = {}
    for k, (i_a, i_c, c_a, c_f, r_a, r_f) in specs.items():
        inv = prem / 100 + area * i_a + i_c        # 백만원
        if measured:
            rev = posting_revenue.revenue_of(unit, district_id, k)   # 만원/월
            cost = rent + rev * posting_revenue.opex_rate(k)         # 만원/월
            basis = COST_BASIS
        else:
            cost = rent + area * c_a + c_f         # 만원/월
            rev = base * r_a + r_f                 # 만원/월
            basis = COST_BASIS_LEGACY
        net = rev - cost
        # 회수기간(개월). invest 는 백만원, net 은 만원이라 ×100 으로 단위를 맞춘다
        # (2026-08-01 교정 — 이전에는 100배 작게 나와 "0.1개월"로 찍혔다).
        roi = float("inf") if net <= 0 else inv * 100 / net
        out[k] = {
            "tier": k, "name": TIER[k]["nm"], "sub": TIER[k]["sub"],
            "invest_mn": round(inv), "month_cost": round(cost), "month_rev": round(rev),
            "month_net": round(net), "roi_months": 99.0 if net <= 0 else round(roi, 1),
            "viable": net > 0,
            "basis": basis,
            "_raw": {"invest_mn": inv, "cost": cost, "rev": rev, "net": net, "roi": roi},
        }
    # 추천은 **계산한다** — 시드의 `unit["rec"]` 을 읽지 않는다. 그래야 실제 건물에서
    # 뽑은 유닛(gold/{거점}/vacant_units.json)에도 그대로 쓸 수 있다. 그 유닛들에는
    # 서술 필드인 rec 이 아예 없어서, 이 의존이 배선을 막고 있었다.
    best = recommend_tier(out)
    for k, s in out.items():
        s["recommended"] = k == best
        s.pop("_raw")
    return out


def unviable_note(scenarios: dict) -> str | None:
    """세 전략 모두 순익이 0 이하면 그 사실을 문장으로 돌려준다(아니면 None).

    2026-08-22 이전에는 이 경우 `rec_top` 이 빈 문자열이 되어 **카드가 조용히 비었다**.
    "추천이 없다"와 "이 자리는 회수가 안 된다"는 전혀 다른 정보인데 구분되지 않았다.

    문구는 **계산의 한계를 함께 밝히는** 형태다. 2026-08-23 부터 두 모델이 공존하므로
    한계 설명도 실제로 돈 모델의 것을 붙인다 — 폴백으로 계산해 놓고 실측 모델의 한계를
    적으면 그 자체가 거짓 근거가 된다.
    """
    if any(s["viable"] for s in scenarios.values()):
        return None
    basis = next(iter(scenarios.values())).get("basis", COST_BASIS)
    return ("이 자리는 지금 계산으로는 회수 불가 — 세 전략 모두 월 순익이 0 이하다. "
            f"({basis_note(basis)})")


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
    # 추천은 계산한다(recommend_tier). 예전에는 시드에 손으로 적은 `u["rec"]` 를 그대로
    # 세어 카드에 노출했다 — 기준이 정의된 적이 없는 값이었다.
    # `recommended` 플래그를 그대로 읽는다 — 여기서 recommend_tier 를 다시 부르면
    # 반올림된 표시값으로 재판정하게 되어 유닛 상세와 카드가 어긋난다.
    recs = [next((k for k, s in sc.items() if s["recommended"]), None)
            for sc in (tier_scenarios(u, d["id"]) for u in resolved_units(d["id"]) or [])]
    tiers = {k: sum(1 for r in recs if r == k) for k in TIER}
    # rec_top 은 **가장 많이 추천된 전략**이다. 예전에는 `recs[0]` — 즉 첫 유닛의 추천을
    # 그대로 썼는데, 그러면 첫 유닛이 회수불가일 때 다른 넷이 멀쩡해도 카드가 조용히
    # 빈다. 비용 모델을 실측으로 바꾸면서 회수불가가 실제로 생겼고(2026-08-23, 명동·
    # 연남처럼 임대료/매출이 높은 거점) 이 결함이 드러났다. `unviable_note` 가 유닛
    # 상세에서 고쳤던 것과 같은 실패 양식이다 — 카드에서도 같게 고친다.
    # 세 전략 모두 회수불가인 거점에서만 빈 문자열이 된다.
    top = max(TIER, key=lambda k: tiers[k]) if any(tiers.values()) else None
    rec_top = TIER[top]["nm"] if top else ""
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
    return [{**u, "scenarios": tier_scenarios(u, district_id)} for u in units]


def get_marketing(district_id: str) -> dict | None:
    d = DISTRICTS_BY_ID.get(district_id)
    if not d:
        return None
    return {"district_id": district_id, "events": d["events"], "online_contents": d["insta"]}
