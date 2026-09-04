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
    """정규화가 거점 매출 수준을 실측에 고정한다 — foot 서열이 수준을 밀지 못한다.

    ⚠ 2026-08-25 단언을 다시 적었다. 종전에는 *"계수가 정확히 1.0 인 유닛이 있다"* 로
      확인했는데, 그건 **유닛 수가 홀수일 때만** 참이다. `_foot_median` 은
      `st.median` 이라 짝수면 두 중간값의 평균(예 0.9)을 돌려주고, 그 값은
      `_FOOT_K` 격자(0.8·1.0·1.25)에 없다. 집계구 승격으로 등급 분포가 바뀌자
      garosugil 이 6/3/3 이 되어 중앙이 0.9 가 됐고, 종전 단언이 유닛을 못 찾아
      깨졌다 — **모델이 아니라 단언이 격자를 전제하고 있었다.**

      지금은 불변식 자체를 확인한다: 각 유닛의 매출은 `면적 × 평당매출 × (계수/중앙)`
      이고, **계수의 중앙이 1.0 으로 정규화**되므로 거점 수준이 서열에 안 밀린다.
    """
    med = P._foot_median(_D)
    assert med > 0
    for u in _units():
        k = P._FOOT_K[u["foot"]]
        expect = u["area"] * P.per_pyeong(_D, "value") * (k / med)
        assert P.revenue_of(u, _D, "value") == pytest.approx(expect, rel=1e-9), u["id"]
    # 정규화된 계수의 중앙은 정확히 1.0 이다 — 이것이 "수준을 안 민다"의 정의다
    ks = sorted(P._FOOT_K[u["foot"]] / med for u in _units())
    assert st.median(ks) == pytest.approx(1.0, rel=1e-9)


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
        # ⚠ 2026-08-25 이 단언의 **근거가 바뀌었다**(§0-O). 종전 실패 문구는 "프라임인데
        #   임대료 비중이 서울 평균 이하 — 의심" 이었는데, 그 '의심'이 기대던 *"우리
        #   유닛은 전부 프라임"* 전제가 측정으로 반증됐다 — 54거점 중 22곳(유닛
        #   182/528)이 R-ONE 서울 표본상권 집계보다 싸다. 즉 premium 이 0 근처인 것은
        #   이상현상이 아니라 인벤토리가 41백분위에 걸쳐 있다는 사실의 결과다.
        #   임계값은 **내리지 않았다** — 부호가 뒤집히면 여전히 무언가 잘못된 것이다.
        #   → test_prime_inventory_premise_is_measurably_false 가 그 분포를 고정한다.
        assert premium_pp > 0, (
            f"{t}: 임대료 비중이 서울 기준 이하 — 분해가 성립하지 않는다 "
            f"(프리미엄 {premium_pp:+.3f}%p)")
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
            assert u.get("inputs_source", {}).get("floor") in (
                "flr_ouln", "flr_ouln+vac"), (
                f"{d['id']} {u['id']} 층 근거가 응답에 안 드러난다")
            checked += 1
    assert checked > 400, f"층 분포가 붙은 유닛이 {checked}개뿐 — 배선이 풀렸다"


def test_vacant_floor_band_is_ordered():
    """공실 유닛의 층 괄호가 **뒤집히지 않는다** — 1F 고정 ≥ 전체 층 ≥ 빈 층 ≥ 빈 층 하단.

    2026-08-25 오후(§0-M). 위 테스트가 고정한 괄호는 두 끝(1F 고정 · 건물 전체 층
    가중평균)뿐이었다. 그런데 **공실 유닛은 점포가 있는 층에 있을 수 없다** — 건물
    상업층 **전체**를 평균에 넣은 값은 이미 찬 층까지 세는 것이라 공실 자리의
    임대료로는 여전히 상한이었다.

    좁힐 근거는 새로 받을 것이 없었다. Page 마스터가 `occ_floors`(상가정보 flrNo·
    인허가로 확인된 점유 층)와 `unknown_n` 을 이미 싣고 있었다 — 수집이 아니라
    **배선** 문제였다(이 저장소가 반복해 잡아 온 양식이다).

    괄호가 남는 원인은 상가정보 flrNo 공란(약 30%)이다:
      · `vac_floor_mix`    점유 하한(확인된 층만 찼다) → 빈 층 최다 → 임대료 **상단**
      · `vac_floor_mix_lo` 점유 상한(층 미상까지 낮은 층부터 찼다) → 임대료 **하단**

    지상 상업층 계수는 층이 올라갈수록 단조 감소하므로(1F 1.00 · 2F 0.45 · 3F 0.40 ·
    4F+ 0.30) 낮은 층을 덜어낸 쪽이 항상 싸다. 그 단조성이 깨지면 괄호의 두 끝이
    이름과 반대가 되므로 여기서 막는다.

    실측(528유닛 · 계수 중앙): 1F 1.000 → 전체 층 0.549 → 빈 층 0.487 → 하단 0.401.
    ⚠ **싣는 값은 여전히 `floor_mix`(전체 층)다.** 빈 층을 실어 보니 premium 티어의
    프라임 프리미엄이 +0.3%p → **−0.23%p** 로 부호를 넘어 위
    `test_margin_gap_is_exactly_the_prime_rent_premium` 가 걸렸다 — 프라임 인벤토리가
    서울 평균보다 임대료 부담이 낮다는 뜻이라 성립하지 않는다. 임계값을 내려
    통과시키지 않고 **싣는 값을 되돌렸고**, 이 테스트는 그 선택까지 함께 고정한다.
    """
    from app.services.posting_inputs import (
        _floor_factor, _mixed_floor_factor, _weighted)

    one_f = _floor_factor("1F", None)
    checked = narrowed = 0
    for d in D.DISTRICTS:
        for u in (D.resolved_units(d["id"]) or []):
            mix, vac = u.get("floor_mix"), u.get("vac_floor_mix")
            if not mix or not vac:
                continue
            f_all = _weighted(mix, None)
            f_vac = _weighted(vac, None)
            f_lo = _weighted(u.get("vac_floor_mix_lo"), None)
            assert f_all is not None and f_vac is not None
            assert set(vac) <= set(mix), (
                f"{d['id']} {u['id']} 빈 층이 건물 상업층 밖이다 — 분모와 갈라졌다")
            assert abs(sum(vac.values()) - 1.0) < 0.01, (
                f"{d['id']} {u['id']} 빈 층 비중 합 {sum(vac.values()):.3f} != 1")
            assert f_vac <= one_f + 1e-9, (
                f"{d['id']} {u['id']} 빈 층 계수 {f_vac:.3f} > 1F {one_f}")
            if f_lo is not None:
                assert f_lo <= f_vac + 1e-9, (
                    f"{d['id']} {u['id']} 하단 {f_lo:.3f} > 상단 {f_vac:.3f} — 괄호가 뒤집혔다")
            # 싣는 값은 **건물 전체 층**이다 — 빈 층을 실어 보니 프라임 프리미엄이
            # 부호를 넘어 위 트립와이어가 걸렸다. 근거 라벨이 측정치 쪽으로 올라가
            # 있으면 응답이 "빈 층으로 계산했다"고 거짓말을 하게 된다.
            shipped, _ = _mixed_floor_factor(u, None)
            assert shipped == pytest.approx(f_all, abs=1e-9), (
                f"{d['id']} {u['id']} 싣는 계수가 floor_mix 가 아니다 — "
                f"괄호의 아래 끝이 조용히 실렸다")
            assert u.get("inputs_source", {}).get("floor") == "flr_ouln", (
                f"{d['id']} {u['id']} 층 근거가 싣는 모델과 어긋난다")
            if u.get("occ_floors"):
                narrowed += 1
            checked += 1
    assert checked > 400, f"빈 층 분포가 붙은 유닛이 {checked}개뿐 — 배선이 풀렸다"
    assert narrowed > 200, (
        f"점유 층으로 좁혀진 유닛이 {narrowed}개뿐 — occ_floors 배선이 풀렸다")


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


# ── §0-O: R-ONE 서울 기준점 — 층 축은 맞았고, 모집단 축이 어긋났다 ─────────────

def test_seoul_benchmark_sits_on_the_same_rone_axis_as_our_districts():
    """서울 기준점이 우리 거점과 **같은 표본·같은 층 관례**여야 한다.

    §0-N 이 요구한 수집의 산출물이다. 우리 거점 임대료와 서울 기준점이 둘 다 R-ONE
    소규모상가(사실상 1층 기준)이므로, 둘을 나누면 **층 계수가 약분된다** — 그래서
    `location_premium()` 은 층 관례와 무관한 순수 입지 격차다.

    실측 2026-08-25 (분기 20261): 서울 17.37 만원/평 · 우리 중앙 19.26 → **1.109**.
    """
    seoul = P._seoul_pyeong_rent()
    assert seoul, "R-ONE 서울 기준점 없음 — `python -m data.collectors.rone_rent` 후 build_posting_inputs"
    ours = P._pyeong_rent()
    assert ours and seoul < ours, "우리 거점 중앙이 서울 표본상권 집계보다 낮다 — 매핑 의심"

    lp = P.location_premium()
    # 대역을 넓게 잡는다. 이 값은 "프라임이라 얼마나 비싼가" 가 아니라 "우리가 고른
    # 42개 상권이 서울 표본 59곳 안에서 어디쯤인가" 이므로 1 근처인 것이 정상이다.
    assert 1.0 < lp < 1.4, f"입지 배율 {lp:.3f} — 대역 밖이면 기준 분기가 어긋났는지 볼 것"

    # 분기가 강제로 일치해야 한다 — 벤치마크만 앞서 가면 배율이 조용히 틀어진다.
    doc = P._read(P._INPUTS)
    assert "seoul" in doc and doc.get("quarter"), "seoul 키가 분기와 함께 실려야 한다"


def test_prime_inventory_premise_is_measurably_false():
    """*"우리 유닛은 전부 프라임"* 은 틀렸다 — 41%가 서울 상권 기준선 아래다.

    이 전제는 §0-I 이후 마진·프리미엄 논의를 계속 떠받쳐 왔고,
    `test_margin_gap_is_exactly_the_prime_rent_premium` 의 실패 문구에도 들어 있었다.
    R-ONE 서울 기준점이 생기면서 **처음으로 직접 잴 수 있게 됐다.**

    실측 2026-08-25: 거점 **22/54** · 유닛 **182/528** 이 기준선 미만.
    (noryangjin 30.3 · garak 31.6 … myeongdong 147.6 — 인벤토리는 프라임 집합이
    아니라 서울 상권 분포 전반에 걸쳐 있다.)

    그래서 프리미엄이 0 근처인 것은 모델 고장의 신호가 아니다. 이걸 고정해 두지
    않으면 다음 사람이 또 "프라임인데 왜 0 이냐"에서 출발한다 — §0-L·§0-M·§0-N 이
    세 번 그렇게 출발했다.
    """
    seoul_pm2 = (P._read(P._INPUTS).get("seoul") or {}).get("rent_per_m2_krw_thousand")
    assert seoul_pm2
    dist = P._read(P._INPUTS)["districts"]

    below = [k for k, v in dist.items() if v["rent_per_m2_krw_thousand"] < seoul_pm2]
    # ⚠ **비율로 잰다.** 종전에는 `15 <= len(below) <= 30` 이라고 절대 개수로 적었는데,
    #   그 대역은 54거점에서만 뜻이 있었다 — 2026-09-04 서울 2차 12거점이 붙자 32/66
    #   (48.5%, 대역 안)인데도 `32 <= 30` 으로 깨졌다. 이 테스트가 고정하려는 것은
    #   "인벤토리가 프라임 집합이 아니다"라는 **분포의 성질**이지 거점 수가 아니다.
    #   아래 유닛 단언이 이미 비율(0.20~0.50)로 되어 있어 거기에 맞춘다.
    share = len(below) / len(dist)
    assert dist and 0.20 < share < 0.60, (
        f"기준선 미만 거점 {len(below)}/{len(dist)} = {share:.1%} — 분포가 크게 바뀌었다")

    n_below = n_all = 0
    # 시드 54가 아니라 **서빙 목록(PAGES)** 을 돈다 — 2026-09-04 부터 시드 밖 거점도
    # 실 인벤토리로 유닛을 내므로, DISTRICTS 로 세면 제품과 다른 모집단을 재게 된다.
    for d in getattr(D, "PAGES", None) or D.DISTRICTS:
        n = len(D.resolved_units(d["id"]) or [])
        n_all += n
        if dist.get(d["id"], {}).get("rent_per_m2_krw_thousand", 0) < seoul_pm2:
            n_below += n
    assert n_all and 0.20 < n_below / n_all < 0.50, (
        f"기준선 미만 유닛 {n_below}/{n_all} — '전부 프라임' 전제가 참이 되려면 0 이어야 한다")


def test_kosis_rent_rate_cannot_be_rebased_by_a_single_floor_coefficient():
    """§0-N 의 가설을 **기각**한다 — KOSIS↔R-ONE 격차는 층 하나로 환산되지 않는다.

    §0-N 은 *"우리는 R-ONE(1층 기준)에 층 면적계수를 곱하는데 KOSIS 임차료는 점포가
    실제 있는 층의 실지불액이니, R-ONE 서울 평균을 받으면 두 기준을 같은 축에 놓을
    수 있다"* 고 적었다. 받아서 재 보니 **층 축은 맞출 수 있지만 모집단 축이 어긋난다.**

    KOSIS 평당임차료 ÷ R-ONE 서울(1층 기준) 을 '서울 평균 점포의 함의 층계수'로 읽으면
    tier 마다 값이 갈린다 (2026-08-25 실측):

        premium 0.672 · value 0.425 · factory 0.460      ↔ 우리 유닛 실효계수 0.549

    층이라면 tier 별로 이렇게 갈릴 이유가 없다. 이 비율은 층 × **모집단**이기 때문이다 —
    R-ONE `서울` 은 **표본 상권 59곳의 집계**이고(단순평균 55.21 · 중앙 51.41 사이에
    52.54), KOSIS 는 서울 전역 사업체 전수다. tier 마다 점포가 상권에 몰린 정도가
    다르니 비율도 다르게 나온다.

    즉 이 비율을 층 계수로 되돌려 KOSIS 임차료율을 보정하면 **모집단 차이를 층으로
    오기입**하게 된다. 그래서 하지 않았다. 이 테스트는 그 유혹을 막는 자리다.
    """
    seoul_pp = P._seoul_pyeong_rent()
    A = P.avg_store_pyeong()
    ind = P._industries()
    implied = {}
    for t in P.TIERS:
        xs = [v["rent_mn"] / float(v["estab"]) / 12 * 100 for v in ind.values()
              if v.get("tier") == t and v.get("estab") and v.get("rent_mn") is not None]
        implied[t] = (sum(xs) / len(xs)) / A[t] / seoul_pp

    spread = max(implied.values()) - min(implied.values())
    assert spread > 0.15, (
        f"함의계수가 tier 간에 {spread:.3f} 밖에 안 갈린다 — 단일 층계수로 읽힐 여지가 "
        f"생겼다는 뜻이므로, 그때는 §0-N 의 가설을 다시 볼 것: {implied}")
