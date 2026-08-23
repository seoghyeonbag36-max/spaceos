"""Posting 실측 매출·비용 모델 (services/posting_revenue + districts.tier_scenarios).

## 무엇을 바꾼 것인가 (2026-08-23, docs/feature-posting.md §0-H·§0-I)

    rev  = area × foot_k_norm × 평당매출[tier][거점]
    cost = rent + rev × 비임차 영업비용률[tier]              # KOSIS 서울 2024
    평당매출 = (상권분석[거점] ÷ 서울중앙) × (KOSIS 점포당 ÷ A[tier])

고정항이 없어진 것이 §0-H, **A 와 매출 절대수준이 외부 실측으로 바뀐 것**이 §0-I 다.
A 는 공정위 정보공개서 12만 가맹점(예전엔 임차료 역산 — 스스로 하한이라 적어 둔 값),
매출 절대수준은 KOSIS 전수(예전엔 상권분석 카드추정 — KOSIS 대비 1.2~2.3배 과소).

## 이 스위트가 붙드는 것

1. **A 도 매출도 마진과 무관한 외부 실측이다.** 마진에 맞춰 뽑으면 "KOSIS 마진이
   재현된다"가 정의상 참이 되어 검증이 순환한다.
2. **절대수준을 앵커해도 거점 서열은 상권분석 그대로다** — 거점을 구분하는 유일한 소스다.
3. **매출이 면적에 온전히 비례한다** — 고정항이 되살아나면 실패한다.
4. **폴백을 조용히 하지 않는다** — 재료가 없으면 `basis` 가 다른 값이어야 한다.
5. **마진과 KOSIS 이익률의 격차가 프라임 임대료로 산술 분해된다** — 순환하지 않는 대조.
"""
from __future__ import annotations

import statistics as st

import pytest

from app.services import districts as D
from app.services import posting_revenue as P

_D = "garosugil"


def _units(did=_D):
    return D.resolved_units(did) or []


# ── A 와 매출은 마진과 무관한 외부 실측이다 ─────────────────────────────────

def test_avg_store_pyeong_comes_from_ftc_measurement():
    """A 는 공정위 정보공개서 실측이다 — 마진과 무관한 외부 값이어야 순환하지 않는다."""
    assert P.area_basis() == "ftc"
    a = P.avg_store_pyeong()
    assert a == P._area_measured()
    tiers = P._read(P._AREA)["tiers"]
    for t in P.TIERS:
        assert a[t] == pytest.approx(tiers[t]["pyeong"], abs=0.01), t
        # 가맹점수 가중 중앙값이라 표본이 실제로 쌓여 있어야 한다.
        assert tiers[t]["stores"] > 1000, t


def test_rent_derived_area_is_kept_only_as_fallback():
    """임차료 역산은 폴백으로만 남는다. 그 값이 **하한**이라는 것이 교체의 이유였다."""
    fallback = P._area_from_rent()
    measured = P._area_measured()
    assert fallback and measured
    for t in P.TIERS:
        assert fallback[t] < measured[t], (
            f"{t}: 역산 {fallback[t]} ≥ 실측 {measured[t]} — 하한이라는 전제가 깨졌다")


def test_per_pyeong_is_anchored_to_kosis_and_keeps_district_ranking():
    """평당매출 = (거점÷서울중앙) × (KOSIS 점포당 ÷ A). 앵커와 서열을 함께 고정한다."""
    assert P.revenue_basis() == "kosis-anchored"
    a, kosis = P.avg_store_pyeong(), P._kosis_store_sales()
    seoul = P._trdar_seoul_median()
    for t in P.TIERS:
        got = P.per_pyeong(_D, t)
        want = (P._revenue()[_D][t]["median"] / seoul[t]) * (kosis[t] / a[t])
        assert got == pytest.approx(want, rel=1e-9), t

    # 절대수준을 앵커해도 **거점 서열은 상권분석 그대로** 보존돼야 한다.
    trdar = sorted(P._revenue(), key=lambda d: P._revenue()[d]["value"]["median"])
    model = sorted((d for d in P._revenue() if P.per_pyeong(d, "value")),
                   key=lambda d: P.per_pyeong(d, "value"))
    assert [d for d in trdar if d in model] == model


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
    """foot 중앙인 유닛은 정확히 `면적 × 거점 평당매출` 을 받는다(계수 1.0).

    `foot` 의 거점 내 서열은 아직 시드라, 정규화하지 않으면 그 시드가 거점의 매출
    수준까지 밀어 올린다.
    """
    med = P._foot_median(_D)
    u = next((u for u in _units() if P._FOOT_K[u["foot"]] == med), None)
    assert u is not None
    expect = u["area"] * P.per_pyeong(_D, "value")
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
    # A 는 공정위 실측(_AREA) → 임차료 역산(_RATE) 순으로 찾는다. 폴백까지 확인하려면
    # 둘 다 지워야 한다 — 하나만 지우면 다른 하나가 조용히 메운다.
    monkeypatch.setattr(P, "_RATE", tmp_path / "absent.json")
    monkeypatch.setattr(P, "_AREA", tmp_path / "absent-area.json")
    P.clear_cache()
    try:
        assert P.avg_store_pyeong() == {}
        assert P.area_basis() == "none"
        assert not P.available(_D)
        sc = D.tier_scenarios(_units()[0], _D)
        assert all(v["basis"] == D.COST_BASIS_LEGACY for v in sc.values())
    finally:
        P.clear_cache()


# ── 순환하지 않는 대조: KOSIS 와의 격차가 산술로 닫히는가 ───────────────────

def _margin_and_rent_share():
    """tier별 (마진 중앙 %, rent/rev 중앙) — 전 거점 전 유닛."""
    mg = {t: [] for t in P.TIERS}
    rr = {t: [] for t in P.TIERS}
    for d in D.DISTRICTS:
        for u in (D.resolved_units(d["id"]) or []):
            for t, v in D.tier_scenarios(u, d["id"]).items():
                if v["month_rev"]:
                    mg[t].append(v["month_net"] / v["month_rev"] * 100)
                    rr[t].append(u["rent"] / v["month_rev"])
    return ({t: st.median(v) for t, v in mg.items()},
            {t: st.median(v) for t, v in rr.items()})


def test_margin_gap_is_exactly_the_prime_rent_premium():
    """마진이 KOSIS 이익률보다 낮은 **이유가 산술로 닫힌다** — 해석이 아니다.

        마진 = (1 − 비임차비용률) − rent/rev
             = (KOSIS 이익률 + KOSIS 임차료율) − rent/rev
             = KOSIS 이익률 − (rent/rev − KOSIS 임차료율)
                              └────── 프라임 프리미엄 ──────┘

    우리 유닛은 전부 프라임 54거점이라 매출 대비 임대료가 서울 평균보다 3.5~6.6%p
    높다. 그만큼 마진이 깎이는 것이고, 이건 버그가 아니라 자리가 비싼 데서 오는
    실제 신호다. 대역 안으로 밀어 넣으려고 A 나 매출을 건드리면 검증이 순환한다.
    """
    rates = P._rates()
    for t in P.TIERS:
        r = rates[t]
        # KOSIS 항등식: 비임차비용률을 뺀 나머지가 이익률 + 임차료율이다.
        assert 1 - r["opex_rate_ex_rent"] == pytest.approx(
            r["profit_rate"] + r["rent_rate"], abs=0.001), t

    med, rent_share = _margin_and_rent_share()
    for t in P.TIERS:
        premium_pp = (rent_share[t] - rates[t]["rent_rate"]) * 100
        assert premium_pp > 0, f"{t}: 프라임인데 임대료 비중이 서울 평균 이하 — 의심"
        # 마진 중앙이 "KOSIS 이익률 − 프라임 프리미엄" 근처에 선다(중앙값이라 정확히는
        # 안 맞지만, 두 %p 넘게 벌어지면 위 분해로 설명되지 않는 무언가가 있는 것이다).
        expect = rates[t]["profit_rate"] * 100 - premium_pp
        assert abs(med[t] - expect) < 2.0, f"{t}: 마진 {med[t]:.1f} vs 분해 {expect:.1f}"


def test_margins_sit_below_kosis_band_because_units_are_prime():
    """마진은 KOSIS 대역(3.5~10.5%) **아래**지만 붕괴하지는 않는다.

    대역 안에 들면 오히려 이상하다 — 프라임 자리의 임대료를 서울 평균 이익률과
    같은 자리에 놓는 셈이기 때문이다. 음수로 무너지면 그때는 모델을 의심한다.
    """
    med, _ = _margin_and_rent_share()
    for t in P.TIERS:
        assert 0 < med[t] < 10.5, f"{t} 마진 중앙 {med[t]:.1f}% — 0 이하면 모델을 의심할 것"


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
