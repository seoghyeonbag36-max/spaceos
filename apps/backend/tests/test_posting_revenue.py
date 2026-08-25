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


def test_margins_stay_in_sane_bounds():
    """마진 중앙이 상식 범위 안에 있다 (붕괴도, 과대도 아니다).

    ⚠ 2026-08-25 **이 테스트의 이름과 전제가 바뀌었다.** 종전 이름은
      `test_margins_sit_below_kosis_band_because_units_are_prime` 였고 *"대역 안에 들면
      오히려 이상하다"* 고 적혀 있었다. 층 분포를 실측(`floor_mix`)으로 갈면서 마진
      중앙이 **5.5 / 4.3 / 7.0%** 로 올라와 KOSIS 대역(3.5~10.5%) 안에 들어왔다.
      전제가 틀렸던 것이 아니라 **입력이 틀려 있었다** — 종전 값(0.4/−1.7/2.1%)은
      전 유닛 1F 가정이 만든 임대료 상한의 결과였다.

      그렇다고 "이제 맞다"는 뜻은 아니다. 프라임 프리미엄이 premium 에서 **0.3%p**
      까지 내려왔는데(종전 3.5%p), 이는 프라임 54거점 인벤토리가 서울 **평균**과
      같은 임대료 부담을 진다는 뜻이라 그것대로 미심쩍다. 두 모델은 참값을 사이에
      두고 있다 — 1F 고정은 **상한**, 층 면적 가중평균은 **하한**에 가깝다.
      → test_weighted_floor_rent_is_a_lower_bound_than_1f 가 그 괄호를 코드로 고정한다.

    ⚠ 2026-08-24 실 인벤토리 배선으로 **value 중앙이 0 을 넘어 내려갔다**(+0.7% →
      **−1.7%**). 종전 하한은 `0 < med[t]` 였다. 그 트립와이어가 울린 이유를 먼저
      확인했고, 모델 고장이 아니었다:

      - 원인은 **층**이다. 시드 270유닛은 23%가 상층(계수 0.30~0.45)이었는데 실
        인벤토리 528유닛은 `build_vacant_units` 가 층을 **전부 1F 로 가정**한다.
        1F 는 계수 1.00 이라 임대료가 계통적으로 가장 비싸게 잡힌다.
      - 위 test_margin_gap_is_exactly_the_prime_rent_premium 이 **그대로 통과한다** —
        즉 마진 = KOSIS 이익률 − 프라임 임대료 프리미엄 이라는 분해가 여전히 2%p
        안에서 닫힌다. 값이 내려간 것이지 설명이 깨진 것이 아니다.

      그래서 하한을 0 에서 **−5%** 로 내리되 폐기하지 않는다. 분해로 설명되는 폭을
      넘어 무너지면(예: −10%) 그때는 정말 모델을 의심해야 한다. 0 을 그대로 두면
      "층 가정 때문에 예측대로 내려간 값"이 매번 모델 고장으로 오독된다.

      실측(528유닛): premium **0.4%** · value **−1.7%** · factory **2.1%**
      (시드 270유닛 기준 종전값은 2.4 / 0.7 / 4.2%)
    """
    med, _ = _margin_and_rent_share()
    for t in P.TIERS:
        assert med[t] < 10.5, f"{t} 마진 중앙 {med[t]:.1f}% — KOSIS 이익률 상한 초과"
        assert med[t] > -5.0, (
            f"{t} 마진 중앙 {med[t]:.1f}% — 분해로 설명되는 폭을 넘어 무너졌다")


def test_weighted_floor_rent_is_a_lower_bound_than_1f():
    """층 가중평균 임대료는 1F 고정보다 **반드시 싸다** — 참값은 둘 사이에 있다.

    2026-08-25 에 `build_vacant_units` 가 층을 층별개요 면적 비중으로 실측하면서
    임대료가 중앙 45% 내려갔고, 그 결과 통과 조건 넷이 전부 ✅ 가 됐다. 숫자가
    원하는 방향으로 움직였을 때가 가장 위험하므로, **어느 쪽이 상한이고 어느 쪽이
    하한인지**를 코드로 못박는다.

    - 1F 고정(종전) = 상한. R-ONE 소규모상가 임대료가 사실상 1층 기준이라 계수 1.00 이
      전 유닛에 걸린다.
    - 층 면적 가중평균(현행) = 하한에 가깝다. 실제 창업 임차인은 저층을 고르는 쪽으로
      쏠리는데, 이 모델은 건물의 모든 상업층을 면적 비중대로 평균낸다.

    참값을 안다고 주장하지 않는다. 괄호가 있다는 사실만 고정한다.
    """
    from app.services.posting_inputs import _floor_factor, _mixed_floor_factor

    one_f = _floor_factor("1F", None)
    checked = 0
    for d in D.DISTRICTS:
        for u in (D.resolved_units(d["id"]) or []):
            mix = u.get("floor_mix")
            if not mix or float(mix.get("1F", 0.0)) >= 0.999:
                continue
            factor, used = _mixed_floor_factor(u, None)
            assert used and factor < one_f, (
                f"{d['id']} {u['id']} 가중계수 {factor:.3f} >= 1F {one_f}")
            # 출처가 어느 모델이 돌았는지 밝히는가 — 안 밝히면 상한과 하한이 같은
            # 이름으로 섞여 나가고, 그건 실측처럼 보이는 추정치가 된다.
            assert u.get("inputs_source", {}).get("floor") == "flr_ouln", (
                f"{d['id']} {u['id']} 층 근거가 응답에 안 드러난다")
            checked += 1
    assert checked > 400, f"층 분포가 붙은 유닛이 {checked}개뿐 — 배선이 풀렸다"


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
