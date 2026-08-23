"""Posting 실측 매출·비용 모델 (services/posting_revenue + districts.tier_scenarios).

## 무엇을 바꾼 것인가 (2026-08-23, docs/feature-posting.md §0-H)

    이전:  rev = area × foot_k × r_a + r_f      # r_a = 41/30/18, 손으로 적은 값
           cost = rent + area × c_a + c_f       # 원가·인건비 없음
    지금:  rev = area × foot_k_norm × 거점별 실측 평당매출[tier]
           cost = rent + rev × 비임차 영업비용률[tier]      # KOSIS 서울 2024

핵심은 **고정항이 없어진 것**이다. 임대료는 면적에 비례하는데 매출은 안 그래서
임대료/매출이 6배 부풀어 있었고(§0-G), 그게 회수불가 96%의 원인이었다.

## 이 스위트가 붙드는 것

1. **A 는 마진이 아니라 임차료에서 유도된다.** 마진에 맞춰 뽑으면 "KOSIS 마진이
   재현된다"가 정의상 참이 되어 검증이 순환한다. 그래서 유도식을 테스트가 고정한다.
2. **매출이 면적에 온전히 비례한다** — 고정항이 되살아나면 실패한다.
3. **폴백을 조용히 하지 않는다** — 재료가 없으면 `basis` 가 다른 값이어야 한다.
4. **결과가 KOSIS 실측 대역 안에 든다** — 이게 순환하지 않는 진짜 대조다.
"""
from __future__ import annotations

import statistics as st

import pytest

from app.services import districts as D
from app.services import posting_revenue as P

_D = "garosugil"


def _units(did=_D):
    return D.resolved_units(did) or []


# ── A 는 임차료에서 유도된다 (마진에 맞춘 것이 아니다) ───────────────────────

def test_avg_store_pyeong_is_derived_from_rent_not_margin():
    """A[tier] = (KOSIS 점포당 월임차료) ÷ (거점 평당임대료 중앙). 식 그대로 재현된다."""
    a = P.avg_store_pyeong()
    rent_pp = P._pyeong_rent()
    assert a and rent_pp
    ind = P._industries()
    for t in P.TIERS:
        xs = [(v["rent_mn"] / float(v["estab"]) / 12 * 100) / rent_pp
              for v in ind.values() if v["tier"] == t]
        assert a[t] == pytest.approx(sum(xs) / len(xs), abs=0.05), t


def test_avg_store_pyeong_is_plausible():
    """A 가 실물과 어긋나면(예: 5평) 평당매출이 업계 대역 밖으로 튄다."""
    a = P.avg_store_pyeong()
    for t, v in a.items():
        assert 5 <= v <= 30, f"{t} A={v}평 — 점포 면적으로 납득할 범위 밖"


def test_per_pyeong_is_in_industry_band_for_most_districts():
    """평당 월매출은 외식업 통상 200~400만원 대역이다. 대부분이 상식 대역 안이어야 한다."""
    d = P.diagnostics()
    total = len(P._revenue()) * len(P.TIERS)
    out = sum(d["out_of_sane_band"].values())
    assert out / total < 0.25, f"상식 대역 밖 {out}/{total} — A 나 매출 실측을 의심할 것"


# ── 매출이 면적에 온전히 비례한다 (고정항 없음) ─────────────────────────────

def test_revenue_is_proportional_to_area():
    """면적을 2배로 하면 매출도 정확히 2배 — 고정항이 되살아나면 깨진다.

    고정항이 있으면 큰 유닛일수록 매출이 과소평가되고, 임대료는 면적에 비례하므로
    임대료/매출이 부푼다. 그것이 §0-G 에서 회수불가 96%를 만든 구조다.
    """
    u = dict(_units()[0])
    r1 = P.revenue_of(u, _D, "value")
    r2 = P.revenue_of({**u, "area": u["area"] * 2}, _D, "value")
    assert r2 == pytest.approx(r1 * 2, rel=1e-9)


def test_foot_normalisation_pins_district_level_to_measurement():
    """foot 중앙인 유닛은 정확히 `면적/A × 거점 실측 중앙` 을 받는다.

    `foot` 의 거점 내 서열은 아직 시드라, 정규화하지 않으면 그 시드가 거점의 매출
    수준까지 밀어 올린다.
    """
    med = P._foot_median(_D)
    u = next((u for u in _units() if P._FOOT_K[u["foot"]] == med), None)
    assert u is not None
    expect = u["area"] * (P._revenue()[_D]["value"]["median"] / P.avg_store_pyeong()["value"])
    assert P.revenue_of(u, _D, "value") == pytest.approx(expect, rel=1e-9)


# ── 비용 = 임대료 + 매출 × 비임차 비용률 ────────────────────────────────────

def test_cost_is_rent_plus_revenue_share():
    u = _units()[0]
    sc = D.tier_scenarios(u, _D)["value"]
    rev = P.revenue_of(u, _D, "value")
    assert sc["month_cost"] == pytest.approx(
        round(u["rent"] + rev * P.opex_rate("value")), abs=1)


def test_rent_is_not_double_counted():
    """KOSIS 영업비용률에서 임차료를 뺀 값을 쓴다 — 안 그러면 임대료를 두 번 센다."""
    for t in P.TIERS:
        assert P.opex_rate(t) < P._rates()[t]["opex_rate"]


# ── 폴백을 조용히 하지 않는다 ───────────────────────────────────────────────

def test_basis_distinguishes_the_two_models():
    u = _units()[0]
    assert all(v["basis"] == D.COST_BASIS for v in D.tier_scenarios(u, _D).values())
    assert all(v["basis"] == D.COST_BASIS_LEGACY for v in D.tier_scenarios(u).values())


def test_unviable_note_quotes_the_model_that_actually_ran():
    """폴백으로 계산해 놓고 실측 모델의 한계를 적으면 그 자체가 거짓 근거다."""
    legacy = {t: {"viable": False, "basis": D.COST_BASIS_LEGACY} for t in P.TIERS}
    assert D.COST_BASIS_LEGACY_NOTE in D.unviable_note(legacy)
    meas = {t: {"viable": False, "basis": D.COST_BASIS} for t in P.TIERS}
    assert D.COST_BASIS_NOTE in D.unviable_note(meas)


def test_missing_artifact_falls_back_and_says_so(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "_RATE", tmp_path / "absent.json")
    P.clear_cache()
    try:
        assert P.avg_store_pyeong() == {}
        assert not P.available(_D)
        sc = D.tier_scenarios(_units()[0], _D)
        assert all(v["basis"] == D.COST_BASIS_LEGACY for v in sc.values())
    finally:
        P.clear_cache()


# ── 순환하지 않는 대조: 결과가 KOSIS 실측 대역 안인가 ───────────────────────

def test_margins_land_in_kosis_band_for_value_and_factory():
    """A 를 마진에 맞추지 않았으므로 이 대조는 순환하지 않는다.

    premium 은 대역 밖(중앙 −1.2%)이다. 이건 버그가 아니라 §0-B 실측과 같은 방향이다 —
    서울에서 '고급화 = 고매출'이 성립하지 않아 tier 서열이 value > premium 이다.
    A[premium] 이 **하한**이라 실제 A 는 더 크고, 그러면 마진은 더 낮아진다.
    """
    mg = {t: [] for t in P.TIERS}
    for d in D.DISTRICTS:
        for u in (D.resolved_units(d["id"]) or []):
            for t, v in D.tier_scenarios(u, d["id"]).items():
                if v["month_rev"]:
                    mg[t].append(v["month_net"] / v["month_rev"] * 100)
    med = {t: st.median(v) for t, v in mg.items()}
    lo, hi = 3.5, 10.5                    # KOSIS 서울 2024 영업이익률 실측 대역
    assert lo <= med["value"] <= hi, med
    assert lo <= med["factory"] <= hi, med
    assert med["premium"] < lo, f"premium 이 대역 안이면 §0-B 실측과 어긋난다: {med}"


def test_unviable_share_is_small_and_factory_can_win():
    """통과 조건 셋 중 둘 — 회수불가 ≤20%, factory ≥1위."""
    wins, unviable, n = {t: 0 for t in P.TIERS}, 0, 0
    for d in D.DISTRICTS:
        for u in (D.resolved_units(d["id"]) or []):
            n += 1
            sc = D.tier_scenarios(u, d["id"])
            best = min((v for v in sc.values() if v["viable"]),
                       key=lambda v: v["roi_months"], default=None)
            if best is None:
                unviable += 1
            else:
                wins[best["tier"]] += 1
    assert unviable / n * 100 <= 20
    assert wins["factory"] > 0, "factory 0승은 死문항 — 추천이 둘로만 갈린다"
