"""Posting 매출·비용 실측 모델 — `tier_scenarios` 의 매출/비용을 실데이터로 세운다.

## 무엇을 고치는가 (2026-08-23, docs/feature-posting.md §0-G·§0-H)

예전 모델은 이랬다:

    rev  = area × foot_k × r_a + r_f      # r_a = 41/30/18 — 손으로 적은 값, 근거 없음
    cost = rent + area × c_a + c_f        # 원가·인건비가 통째로 빠져 있다

`r_a`(면적 기울기)에 근거가 없다는 것은 §0-B 가 이미 적어 두었지만, **그것이 지배적
오차**라는 것은 08-23 에 KOSIS 비용률을 넣어 보고서야 드러났다. 비용을 정직하게 넣으면
회수불가가 96%까지 튀었는데, 원인은 비용이 아니라 매출이었다 — **임대료는 면적에
비례해 커지는데 정렬된 매출은 평균 점포 크기에 묶여 있었다.**

## 지금 모델 (2026-08-23 개편 — §0-I)

    평당매출[tier][거점] = (상권분석[거점] ÷ 상권분석 서울중앙) × (KOSIS 점포당 ÷ A[tier])
    rev  = area × foot_k_norm × 평당매출
    cost = rent + rev × 비임차_영업비용률[tier]        # KOSIS 서울 2024

**세 실측이 각자 잘하는 축을 하나씩 맡는다:**

| 축 | 소스 | 왜 그것인가 |
|---|---|---|
| 거점 간 격차 | 서울 상권분석 | 거점을 구분하는 유일한 소스 — **비율로만** 쓴다 |
| 매출 절대수준 | KOSIS 서비스업조사 | 사업체 전수에 가깝다 |
| 점포 면적 A | 공정위 정보공개서 | 12만 가맹점 실측 |

## 어떻게 여기까지 왔나 — A 를 갈아끼우자 분자가 드러났다

08-23 오전까지 A 는 **임차료 역산**이었고(KOSIS 점포당 임차료 ÷ 우리 54거점 평당임대료),
그 함수 스스로 자기 값을 하한이라고 적어 두었다. 공정위 실측으로 갈아끼우니 A 가
2~3배 커졌다(premium 12.6→20.8 · value 7.1→18.5 · factory 7.1→17.1). 한식집 7.1평은
실물이 아니었던 것이다.

그런데 A 만 키우자 회수불가가 2.6% → **50%** 로 튀고 평당매출이 85~121만원/평까지
떨어져 상식 대역(100~600) **밖**으로 나갔다. 원인은 A 가 아니라 **분자**였다 —
상권분석 추정매출(카드 기반)이 KOSIS 전수 대비 1.2~2.3배 과소다. A 가 작아서 그
과소추정이 상쇄돼 보이고 있었을 뿐이다.

공정위 면적과 KOSIS 매출은 **서로 독립인 두 실측**인데, 짝지으면 평당매출이
195/143/198만원/평로 업계 통상(150~300)에 정확히 들어온다. 서로를 검증한 셈이고,
그래서 이 조합을 채택했다.

## 마진을 기준에 맞추지 않는다 — 그러면 검증이 순환한다

A 를 "마진 중앙이 KOSIS 영업이익률과 같아지도록" 고르면 A=5.1평이 나오는데, 그렇게
맞추면 "KOSIS 마진이 재현된다"가 **정의상 참**이 되어 아무것도 검증하지 못한다.
지금은 A 도 매출도 마진과 무관하게 외부에서 들어오므로, 결과 마진을 KOSIS
영업이익률과 대조하는 것이 실제 검증이 된다.

⚠ 그 대조에서 마진 중앙은 KOSIS 대역(3.5~10.5%)보다 **낮다**(§0-I). 우리 유닛이 전부
프라임 54거점이라 임대료가 서울 평균보다 높기 때문으로, 버그가 아니라 자리가 비싼
데서 오는 실제 신호다. 대역 안으로 밀어 넣으려고 A 나 매출을 건드리면 위의 순환에
다시 빠진다.
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
_AREA = _GOLD / "platform_posting_store_area.json"

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
def _area_measured() -> dict[str, float]:
    """공정위 가맹사업 정보공개서에서 받은 tier별 A(평) — 실측.

    `data/pipelines/build_posting_store_area.py` 가 떨군 산출물을 읽는다.
    A = 평균매출 ÷ 면적단위평균매출(3.3㎡당)이라 금액 단위가 상쇄된 값이다.
    """
    tiers = (_read(_AREA).get("tiers") or {})
    out = {t: float(v["pyeong"]) for t, v in tiers.items()
           if t in TIERS and v.get("pyeong")}
    return out if len(out) == len(TIERS) else {}


@lru_cache(maxsize=1)
def _area_from_rent() -> dict[str, float]:
    """A 를 임차료에서 역산 — 공정위 실측이 없을 때만 쓰는 **폴백**.

    KOSIS 점포당 월 임차료를 거점 평당임대료로 나눈다. 이 값은 **하한**이다:
    분모가 서울 전체가 아니라 전부 프라임인 54거점 임대료라, 서울 평균으로
    나눴다면 A 가 더 컸다. 실제로 공정위 실측과 대면 2~3배 작았다(08-23).
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


@lru_cache(maxsize=1)
def avg_store_pyeong() -> dict[str, float]:
    """tier별 평균 점포 면적 A(평) — **공정위 실측 우선, 임차료 역산은 폴백.**

    2026-08-23 교체. 예전에는 임차료 역산 하나뿐이었고 그 함수 스스로가 자기 값을
    하한이라고 적어 두었다(§0-E 가 "공정위 기준면적을 확보하면 갈아끼운다"고 예약).
    공정위 정보공개서 12만 가맹점 실측으로 대면 A 는 2~3배 크다:

        premium 12.6 → 20.8 · value 7.1 → 18.5 · factory 7.1 → 17.1

    **A 가 커지면 마진은 나빠진다** — 평당매출(= 매출 ÷ A)이 낮아져 rent/rev 비중이
    커지기 때문이다. 즉 이 교체는 게이트를 통과시키는 방향이 아니라 그 반대이고,
    그래서 낙관 쪽으로 치우쳐 있던 값을 바로잡는 것이 맞다.

    어느 쪽이 쓰였는지는 `area_basis()` 로 드러낸다. 둘 다 없으면 빈 dict 를 돌려
    호출부가 실측 모델을 통째로 끄게 한다 — 조용히 기본값을 쓰면 근거 없는 상수가
    다시 들어앉는다(이 파일이 걷어내려는 바로 그것이다).
    """
    return _area_measured() or _area_from_rent()


def area_basis() -> str:
    """A 의 출처 — "ftc"(공정위 실측) · "rent"(임차료 역산 폴백) · "none"."""
    if _area_measured():
        return "ftc"
    return "rent" if _area_from_rent() else "none"


def opex_rate(tier: str) -> float | None:
    """비임차 영업비용률 — 임차료는 유닛별 R-ONE 으로 따로 들어가므로 뺀 값이다."""
    r = _rates().get(tier)
    return r.get("opex_rate_ex_rent") if r else None


@lru_cache(maxsize=1)
def _kosis_store_sales() -> dict[str, float]:
    """KOSIS 서울 2024 tier별 **점포당 월매출**(만원) — 절대수준 앵커.

    서비스업조사는 사업체 전수에 가깝다. 상권분석 추정매출(카드 기반)보다 1.2~2.3배
    큰데, 그 격차가 이 모델이 오래 안고 있던 과소추정이었다(08-23 발견).
    """
    ind = _industries()
    out: dict[str, float] = {}
    for t in TIERS:
        xs = [v["sales_mn"] / v["estab"] / 12 * 100 for v in ind.values()
              if v.get("tier") == t and v.get("estab") and v.get("sales_mn")]
        if xs:
            out[t] = sum(xs) / len(xs)
    return out if len(out) == len(TIERS) else {}


@lru_cache(maxsize=1)
def _trdar_seoul_median() -> dict[str, float]:
    """상권분석 점포당 월매출의 **서울 중앙**(만원). 거점 상대수준의 기준점이다."""
    rev = _revenue()
    out: dict[str, float] = {}
    for t in TIERS:
        xs = [d[t]["median"] for d in rev.values() if t in d and d[t].get("median")]
        if xs:
            out[t] = st.median(xs)
    return out if len(out) == len(TIERS) else {}


def per_pyeong(district_id: str | None, tier: str) -> float | None:
    """거점 × tier 평당 월매출(만원) — **세 실측이 각자 잘하는 축을 맡는다.**

        평당매출 = (상권분석[거점] ÷ 상권분석 서울중앙) × (KOSIS 점포당 ÷ 공정위 A)
                   └─ 거점 상대수준 ─┘                  └─ 절대수준 앵커 ─┘

    2026-08-23 개편. 예전에는 `상권분석[거점] ÷ A` 하나였는데, 공정위 실측 A 로
    갈아끼우자 평당매출이 85~121만원/평까지 떨어져 상식 대역(100~600) 밖으로
    나갔다. 원인은 A 가 아니라 **분자**였다 — 상권분석 추정매출이 KOSIS 전수 대비
    1.2~2.3배 과소다. 두 실측(공정위 면적 · KOSIS 매출)은 서로 독립인데 짝지으면
    195/143/198만원/평로 업계 통상(150~300)에 정확히 들어온다. 서로를 검증한 셈이다.

    거점 격차는 상권분석이 유일한 소스이므로 **비율로만** 쓴다. 절대 수준을
    KOSIS 로 앵커하면 거점 서열은 보존되면서 수준만 제자리를 찾는다.

    앵커 재료가 없으면 예전 식으로 폴백한다 — 그 경우 `area_basis()` 와 함께
    `diagnostics()["revenue_basis"]` 가 어느 쪽이 돌았는지 밝힌다.
    """
    if not district_id:
        return None
    m = (_revenue().get(district_id) or {}).get(tier)
    a = avg_store_pyeong().get(tier)
    if not m or not a:
        return None
    kosis = _kosis_store_sales().get(tier)
    seoul = _trdar_seoul_median().get(tier)
    if not kosis or not seoul:
        return m["median"] / a                     # 폴백: 상권분석 절대값 그대로
    return (m["median"] / seoul) * (kosis / a)


def revenue_basis() -> str:
    """매출 절대수준의 출처 — "kosis-anchored" · "trdar-raw"."""
    return ("kosis-anchored" if _kosis_store_sales() and _trdar_seoul_median()
            else "trdar-raw")


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
    # per_pyeong() 을 그대로 불러야 진단이 실제 모델과 같은 것을 본다. 예전에는 여기서
    # 식을 다시 적었는데, 그러면 모델이 바뀔 때 진단만 조용히 낡는다.
    pp = {t: sorted(x for x in (per_pyeong(d, t) for d in _revenue()) if x)
          for t in TIERS} if a else {}
    return {
        "pyeong_rent": _pyeong_rent(),
        "avg_store_pyeong": a,
        "area_basis": area_basis(),
        "revenue_basis": revenue_basis(),
        "kosis_store_sales": {t: round(v) for t, v in _kosis_store_sales().items()},
        "avg_store_pyeong_from_rent": _area_from_rent(),
        "opex_rate_ex_rent": {t: opex_rate(t) for t in TIERS},
        "per_pyeong_median": {t: round(v[len(v)//2], 1) for t, v in pp.items() if v},
        "out_of_sane_band": {
            t: sum(1 for x in v if not SANE_PER_PYEONG[0] <= x <= SANE_PER_PYEONG[1])
            for t, v in pp.items()},
    }


def clear_cache() -> None:
    for f in (_revenue, _rates, _industries, _pyeong_rent, avg_store_pyeong,
              _area_measured, _area_from_rent, _kosis_store_sales,
              _trdar_seoul_median, _foot_median):
        f.cache_clear()
