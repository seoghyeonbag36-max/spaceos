"""Posting 매출·비용 실측 모델 — `tier_scenarios` 의 매출/비용을 실데이터로 세운다.

## 무엇을 고치는가 (2026-08-23, docs/feature-posting.md §0-G·§0-H)

예전 모델은 이랬다:

    rev  = area × foot_k × r_a + r_f      # r_a = 41/30/18 — 손으로 적은 값, 근거 없음
    cost = rent + area × c_a + c_f        # 원가·인건비가 통째로 빠져 있다

`r_a`(면적 기울기)에 근거가 없다는 것은 §0-B 가 이미 적어 두었지만, **그것이 지배적
오차**라는 것은 08-23 에 KOSIS 비용률을 넣어 보고서야 드러났다. 비용을 정직하게 넣으면
회수불가가 96%까지 튀었는데, 원인은 비용이 아니라 매출이었다 — **임대료는 면적에
비례해 커지는데 정렬된 매출은 평균 점포 크기에 묶여 있었다.**

## 지금 모델

    평당매출[tier][거점] = 거점별 실측 매출중앙 ÷ A[tier]
    rev  = area × foot_k_norm × 평당매출
    cost = rent + rev × 비임차_영업비용률[tier]        # KOSIS 서울 2024

미지수가 여섯(r_a·r_f 각 3개)에서 **A 하나(tier별 3값)** 로 줄었다. 고정항이 없어졌으므로
매출이 면적에 온전히 비례하고, 임대료와 같은 축을 타게 된다.

## A 를 마진에 맞추지 않은 이유 — 그러면 검증이 순환한다

A 를 "마진 중앙이 KOSIS 영업이익률과 같아지도록" 고르면 A=5.1평이 나오는데, 그건
한식집 평당 월매출 563만원(업계 통상 200~400만원)을 뜻해 실물과 안 맞는다. 게다가
그렇게 맞추면 "KOSIS 마진이 재현된다"가 **정의상 참**이 되어 아무것도 검증하지 못한다.

그래서 A 를 **독립 유도**한다 — KOSIS 점포당 임차료를 거점 평당임대료로 나눈다:

    A[tier] = (KOSIS 임차료 ÷ 사업체수 ÷ 12) ÷ 거점 평당임대료 중앙

마진은 이 A 의 **결과**이지 입력이 아니다. 그래서 결과를 KOSIS 영업이익률과 대조하는
것이 실제 검증이 된다(2/3 tier 가 실측 대역 3.5~10.5% 안에 든다 — §0-H).

⚠ **A 는 하한이다.** 분모로 쓴 평당임대료가 서울 전체가 아니라 우리 54거점(전부 프라임)
값이라, 서울 평균으로 나눴다면 A 가 더 컸을 것이다. A 가 크면 평당매출이 낮아져
마진이 더 나빠진다 — 즉 **지금 값은 낙관 쪽으로 치우쳐 있다.** 공정위 가맹사업
정보공개서의 기준면적을 확보하면(§0-E) 이 상수를 실측으로 갈아끼운다.
"""
from __future__ import annotations

import json
import statistics as st
from functools import lru_cache
from pathlib import Path

_GOLD = Path(__file__).resolve().parents[4] / "data" / "gold"
_REV = _GOLD / "platform_posting_revenue.json"
_RATE = _GOLD / "platform_posting_cost_rates.json"
_INPUTS = _GOLD / "platform_posting_inputs.json"

TIERS = ("premium", "value", "factory")
_FOOT_K = {"저": 0.8, "중": 1.0, "고": 1.25}

# 평당매출의 상식 대역(만원/평·월). 외식업 통상 200~400. 계산된 값이 이 밖으로 나가면
# A 나 매출 실측 중 하나가 틀린 것이므로, 조용히 쓰지 않고 진단에 싣는다.
SANE_PER_PYEONG = (100.0, 600.0)


def _read(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=1)
def _revenue() -> dict:
    return (_read(_REV).get("districts") or {})


@lru_cache(maxsize=1)
def _rates() -> dict:
    return (_read(_RATE).get("tiers") or {})


@lru_cache(maxsize=1)
def _industries() -> dict:
    return (_read(_RATE).get("industries") or {})


@lru_cache(maxsize=1)
def _pyeong_rent() -> float | None:
    """54거점 R-ONE 소규모상가 임대료의 중앙(만원/평·월). A 유도의 분모다."""
    doc = _read(_INPUTS)
    src = doc.get("districts") or doc
    vals = sorted(v["rent_per_m2_krw_thousand"] for v in src.values()
                  if isinstance(v, dict) and "rent_per_m2_krw_thousand" in v)
    if not vals:
        return None
    return vals[len(vals) // 2] * 3.3058 / 10      # 천원/㎡ → 만원/평


@lru_cache(maxsize=1)
def avg_store_pyeong() -> dict[str, float]:
    """tier별 평균 점포 면적 A(평) — **마진이 아니라 임차료에서 유도한다.**

    KOSIS 점포당 월 임차료를 거점 평당임대료로 나눈다. 재료가 없으면 빈 dict 를
    돌려 호출부가 실측 모델을 통째로 끄게 한다 — 조용히 기본값을 쓰면 근거 없는
    상수가 다시 들어앉는다(이 파일이 걷어내려는 바로 그것이다).
    """
    rent_pp = _pyeong_rent()
    ind = _industries()
    if not rent_pp or not ind:
        return {}
    out: dict[str, float] = {}
    for t in TIERS:
        xs = [(v["rent_mn"] / float(v["estab"]) / 12 * 100) / rent_pp
              for v in ind.values()
              if v.get("tier") == t and v.get("estab") and v.get("rent_mn") is not None]
        if xs:
            out[t] = round(sum(xs) / len(xs), 1)
    return out if len(out) == len(TIERS) else {}


def opex_rate(tier: str) -> float | None:
    """비임차 영업비용률 — 임차료는 유닛별 R-ONE 으로 따로 들어가므로 뺀 값이다."""
    r = _rates().get(tier)
    return r.get("opex_rate_ex_rent") if r else None


def per_pyeong(district_id: str | None, tier: str) -> float | None:
    """거점 × tier 평당 월매출(만원). 재료가 하나라도 없으면 None."""
    if not district_id:
        return None
    m = (_revenue().get(district_id) or {}).get(tier)
    a = avg_store_pyeong().get(tier)
    if not m or not a:
        return None
    return m["median"] / a


@lru_cache(maxsize=256)
def _foot_median(district_id: str) -> float:
    """거점 내 foot 계수의 중앙. 이걸로 나눠 **거점 수준을 실측 중앙에 정확히 맞춘다.**

    ⚠ `foot` 의 거점 내 **서열은 아직 시드**다(입력 4종 게이트에 그렇게 적혀 있다).
    정규화하지 않으면 그 시드가 거점의 매출 수준까지 밀어 올린다 — 정규화 후에는
    거점 안에서의 상대 보정으로만 남는다. 서열이 실데이터로 바뀌면 이 함수는 그대로
    두고 값만 좋아진다.
    """
    from app.services import districts as D          # 순환 import 회피
    units = D.resolved_units(district_id) or []
    ks = [_FOOT_K.get(u.get("foot"), 1.0) for u in units]
    return st.median(ks) if ks else 1.0


def revenue_of(unit: dict, district_id: str | None, tier: str) -> float | None:
    """유닛 × tier 월매출(만원). 고정항 없이 **면적에 온전히 비례**한다."""
    pp = per_pyeong(district_id, tier)
    if pp is None or not unit.get("area"):
        return None
    fk = _FOOT_K.get(unit.get("foot"), 1.0) / (_foot_median(district_id) or 1.0)
    return unit["area"] * fk * pp


def available(district_id: str | None) -> bool:
    """이 거점에 실측 모델을 쓸 수 있는가 — 세 tier 전부 재료가 있어야 참."""
    return all(per_pyeong(district_id, t) is not None and opex_rate(t) is not None
               for t in TIERS)


def diagnostics() -> dict:
    """보정 상태 점검용 — 상수와 평당매출이 상식 대역 안인지 함께 돌려준다."""
    a = avg_store_pyeong()
    pp = {t: sorted(v[t]["median"] / a[t] for v in _revenue().values() if t in v)
          for t in TIERS} if a else {}
    return {
        "pyeong_rent": _pyeong_rent(),
        "avg_store_pyeong": a,
        "opex_rate_ex_rent": {t: opex_rate(t) for t in TIERS},
        "per_pyeong_median": {t: round(v[len(v)//2], 1) for t, v in pp.items() if v},
        "out_of_sane_band": {
            t: sum(1 for x in v if not SANE_PER_PYEONG[0] <= x <= SANE_PER_PYEONG[1])
            for t, v in pp.items()},
    }


def clear_cache() -> None:
    for f in (_revenue, _rates, _industries, _pyeong_rent, avg_store_pyeong, _foot_median):
        f.cache_clear()
