"""거점(commercial district) 도메인 서비스.

공실 집계의 입력은 **Gold 실데이터 우선**이다 (2026-08-01 배선 교체).
- 실측 거점: 실측 건물을 100m 셀로 집계 (services/gold_vacancy). 응답의 `vacancy_source == "gold"`.
- 그 밖: 기존 `build_cells()` 합성 그리드로 폴백. `vacancy_source == "synthetic"`.
  → 해당 거점의 대장을 받아 파이프라인을 돌리면 자동으로 실데이터로 바뀐다.

**2026-09-05 실측: 서빙 66거점이 전부 `gold` 다**(전 거점 `GET /heatmap/vacancy` 호출로 확인).
즉 `synthetic` 폴백은 코드에 남아 있지만 지금 그 길을 타는 서빙 거점은 없다. 이 문장은
거점이 늘면 낡는다 — **세어서 고칠 것**(개수를 여기 박아 두지 않는 이유이기도 하다).

갈림길은 **파일 존재가 아니다.** `page_building_master.geojson` 은 서빙 거점 전부에 있다
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
from app.data import cities, hub_caveats, measured_pages

from app.services import (district_zones, gold_vacancy, posting_inputs, posting_revenue,
                          vacancy_forecast, vacant_inventory)


def _with_zones(page: dict) -> dict:
    """구역을 **Gold 실측으로 덮은 사본**을 만든다 — 시드에 적힌 값이 아니라(2026-09-05).

    시드 거점(54)과 실측 거점(12)이 여기서 같은 소스를 보게 된다. 그전에는 앞의 54곳만
    손으로 적은 감성 구역을 갖고 뒤의 12곳은 빈 목록이라, 같은 화면이 거점에 따라 다른
    종류의 값을 그렸다.

    ⚠ **원본 dict 를 제자리에서 고치지 않는다.** `DISTRICTS` 는 시드를 세는 곳이
    여럿이라(tests·문서) 그 내용이 흔들리면 안 된다 — 아래 PAGES 주석과 같은 이유다.
    실제로 제자리 변형으로 먼저 짰다가 `test_the_seed_no_longer_carries_hand_written_zones`
    가 잡았다.

    파일이 없는 거점은 빈 목록이 된다 — 파이프라인을 아직 안 돌렸다는 뜻이고, 그 사실이
    화면에 "구역 없음"으로 드러난다. 조용히 시드로 되돌아가지 않는다.
    """
    return {**page, "zones": district_zones.zones(page["id"])}


# 시드(서울 54) + 실측 거점(Gold 만으로 서는 거점, 예: 고양 화정).
# **시드가 이긴다** — measured_pages.build() 가 이미 시드 id 를 제외하고 만든다.
# 이 합본은 API 표면에서만 쓴다. `DISTRICTS`(시드) 자체는 건드리지 않는다 —
# 세는 곳(tests·문서)이 여럿이라 그 수가 흔들리면 안 된다.
PAGES: list[dict] = [_with_zones(p) for p in (*DISTRICTS, *measured_pages.MEASURED)]
PAGES_BY_ID: dict[str, dict] = {p["id"]: p for p in PAGES}


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
    # `prem`(권리금)은 공개 통계가 없어 **입력 계약**으로 받는다(2026-08-24 결정).
    # 안 주면 0 전제로 돈다 — 실측 감도는 추천 5.2% 뒤집힘 · roi 중앙 1.6개월이고
    # 회수가부 판정은 전혀 안 바뀐다(270유닛 전수, docs/feature-posting.md §0-K).
    rent, area, prem = unit["rent"], unit["area"], unit.get("prem") or 0
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


def _predicted_none() -> dict:
    """예측 3필드를 비운다 — 대표 공실률을 내린 거점에서 쓴다.

    `predicted_rate` 는 현재 공실률 + delta 라, 대표값을 내려 놓고 이것만 남기면
    화면이 내린 수를 그대로 되살린다(rate - delta).
    """
    return {"predicted_rate": None, "predicted_delta": None, "predicted_direction": None}


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
    # 실측 거점은 `city` 를 직접 갖는다(gu 가 자치구가 아니라 도시명이라 of_gu 로는 못 찾는다).
    _city = cities.by_id(d["city"]) if d.get("city") else cities.of_gu(d.get("gu"))
    # 감성은 **아무 거점에서도 재지 않았다**(2026-09-05). 종전에는 시드에 손으로 적은
    # `z["s"]`·`z["r"]` 을 가중평균해 "거점 감성"으로 내려보냈는데, 그 입력에 근거가
    # 없었다(54거점 × 6구역 = 324개 전부 사람이 쓴 값). 구역을 행정동 실측으로 갈면서
    # 그 입력이 사라졌고, 따라서 파생값도 함께 내린다.
    #
    # 0 으로 내려보내면 "쟀더니 0" 으로 읽히므로 None 을 주고 화면이 "실측 없음"으로
    # 그린다(measured_pages 머리말과 같은 원칙). 좌표를 가진 점포 리뷰 채널이 생기면
    # 그때 되살아난다 — docs/feature-platform.md §0-K.
    zs = d["zones"]
    sum_r = sum(z["r"] for z in zs if z.get("r") is not None)
    scored = [z for z in zs if z.get("s") is not None and z.get("r")]
    sent = (sum(z["s"] * z["r"] for z in scored) / sum_r) if scored and sum_r else None
    risk = sum(1 for z in scored if z["s"] < 40) if scored else None
    ci = cells_for(d)
    withheld = hub_caveats.is_withheld(d["id"])
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
        "id": d["id"], "name": d["name"], "gu": d["gu"],
        # 도시는 시드에 적지 않고 `gu` 로 판정한다 — 54개 항목을 건드리지 않고
        # 도시 축을 넣기 위해서다(app/data/cities.of_gu).
        "city": _city.id, "city_name": _city.short,
        "type": d["type"],
        "center": d["center"], "note": d["sub"], "rec_top": rec_top,
        "sentiment": round(sent, 1) if sent is not None else None,
        "reviews": sum_r if scored else None, "risk_zones": risk,
        # 시드 없이 Gold 만으로 서는 거점인가 — 화면이 빈 축을 "실측 없음"으로 그리는 근거.
        "measured_only": bool(d.get("measured_only")),
        # 예외 문구는 시드에 적힌 것(경기 실측 거점)이 있으면 그것을, 없으면 계획상가
        # 판단(hub_caveats)에서 만든다. 후자는 비율을 **이 집계에서** 뽑으므로 재수집으로
        # 값이 움직이면 문구도 같이 움직인다 — 손으로 적은 수가 낡는 것을 막는다.
        "caveat": d.get("caveat") or hub_caveats.caveat_of(d["id"], ci),
        # 대표값을 내린 거점은 vacancy_rate·anchor_gap_pp·predicted_* 를 함께 내린다.
        # 셋 다 대표값에서 유도되는 값이라, 하나만 남기면 내린 수를 되계산할 수 있다.
        "vacancy_rate": None if withheld else ci["avg_vacancy"],
        "vacancy_withheld": withheld,
        "inventory_coverage_pct": ci.get("inventory_coverage_pct"),
        "vacant_units": ci["sum_vac"],
        "cell_count": len(ci["cells"]), "store_count": ci["sum_stores"],
        "tier_mix": tiers,
        "vacancy_source": ci["vacancy_source"],
        "building_count": ci.get("buildings"),
        "precision_pct": ci.get("precision_pct"),
        # 앵커(R-ONE) 자체는 남긴다 — 우리 대표값과 무관한 외부 관측이다.
        # 격차는 대표값과의 차이라 대표값이 없으면 성립하지 않는다.
        "anchor_pct": ci.get("anchor_pct"),
        "anchor_gap_pp": None if withheld else ci.get("anchor_gap_pp"),
        **(_predicted_none() if withheld else _predicted(d["id"], ci["avg_vacancy"])),
    }


def list_summaries() -> list[dict]:
    """거점 요약(감성·공실·리뷰·Tier) 목록 — City Dashboard 용."""
    return [_summary(d) for d in PAGES]


def get_summary(district_id: str) -> dict | None:
    d = PAGES_BY_ID.get(district_id)
    return _summary(d) if d else None


def get_district(district_id: str) -> dict | None:
    """거점 전체 원천 데이터(zones/units/events/poi/grid)."""
    return PAGES_BY_ID.get(district_id)


def get_sentiment(district_id: str) -> list[dict] | None:
    """거점의 구역 목록. 거점이 없으면 None, 구역이 없으면 빈 리스트.

    ⚠ 엔드포인트 이름은 `/sentiment` 인데 **감성은 실려 있지 않다.** 2026-09-05 에
    손으로 적은 감성 구역을 행정동 실측 구역으로 갈았고, `s`/`d`/`r` 은 null 이다.
    이름을 바꾸지 않은 것은 공개 API 표면이기 때문이다 — 필드가 그 사실을 밝힌다.
    """
    d = PAGES_BY_ID.get(district_id)
    return d["zones"] if d else None


def get_vacancy_heatmap(district_id: str) -> dict | None:
    d = PAGES_BY_ID.get(district_id)
    if not d:
        return None
    ci = cells_for(d)
    withheld = hub_caveats.is_withheld(district_id)
    return {"district_id": district_id, "resolution_m": 100, **ci,
            # 셀은 그대로 둔다 — 내린 것은 셀이 아니라 거점 하나로 뭉친 대표값이다.
            "avg_vacancy": None if withheld else ci["avg_vacancy"],
            # 격차도 같이 내린다. 여기를 빼먹으면 화면이 `앵커 + 격차` 로 내린 수를
            # 그대로 되살린다 — 요약 응답만 막고 히트맵을 안 막은 채로 한 번 새어
            # 나갔다(2026-09-02, test_gold_anchor_comparison_attached 가 잡았다).
            "anchor_gap_pp": None if withheld else ci.get("anchor_gap_pp"),
            "vacancy_withheld": withheld,
            **(_predicted_none() if withheld
               else _predicted(district_id, ci["avg_vacancy"]))}


def resolved_units(district_id: str) -> list[dict] | None:
    """거점의 공실 유닛 — **실 인벤토리 우선**, 없으면 시드. rent·foot 은 실데이터로 덮는다.

    2026-08-24 배선. 그전까지 이 함수는 시드(`seoul_pages.DISTRICTS`, 270유닛)만
    읽었다. 실제 공실 인벤토리는 08-22 에 54/54거점 528유닛으로 완주해 있었는데
    **아무도 읽지 않아서**, Posting 화면이 계속 손으로 적은 예시 위에서 돌았다
    (Program ①층이 08-23 에 겪은 것과 똑같은 실패 양식 — 수집이 아니라 배선이었다).

    실 인벤토리는 건축물대장 실측이라 시드에 있던 서술 필드(`rec`·`persona`·`note`)가
    없다. 지어내지 않고 **비운 채로** 내보낸다 — `rec` 은 이미 계산으로 대체됐고
    (`recommend_tier`), 나머지 둘은 근거 없이 적은 문구다. 스키마에서 선택 필드다.

    시드 원본은 건드리지 않는다(프로세스 전역 공유 dict 다).
    각 유닛의 `inputs_source` 가 필드별 출처(seed/rone/flpop/gold-ledger/absent)를 밝힌다.
    """
    # 실 인벤토리 유닛에는 `rent` 가 **없다** — R-ONE 으로 계산해서 넣는 값이다.
    # 그래서 R-ONE 입력(gold/platform_posting_inputs.json)이 미적재면 임대료가 빈
    # 유닛이 나가고 `tier_scenarios` 가 KeyError 로 죽는다. 신규 클론에서 실제로
    # 그렇게 된다 → 둘이 **함께** 있을 때만 실 인벤토리를 쓰고, 아니면 시드로 물러난다.
    real = (vacant_inventory.units(district_id)
            if posting_inputs.for_district(district_id) else [])
    if district_id not in DISTRICTS_BY_ID:
        # 시드 밖 거점(서울 2차 12거점 · 2026-09-04). 여기서 무조건 None 을 내던 탓에
        # **지도에는 뜨는데 Posting 은 통째로 비는** 거점이 있었다: 12거점 전부
        # 인벤토리 136유닛 + R-ONE 입력을 갖추고도 `get_postings` 가 None 이었다.
        # 시드가 문지기였던 것이지 재료가 없던 것이 아니다 — 이 저장소가 반복해서
        # 겪은 '수집이 아니라 배선' 양식이다(feature-posting.md §0-J 와 같은 자리).
        # 시드가 없으므로 **폴백도 없다**: 실 인벤토리가 없으면 그대로 None 이다.
        # 지어낸 유닛으로 화면을 채우지 않는다.
        return posting_inputs.resolve_units(district_id, real) if real else None
    if real:
        return posting_inputs.resolve_units(district_id, real)
    return posting_inputs.resolve_units(district_id, DISTRICTS_BY_ID[district_id]["units"])


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
