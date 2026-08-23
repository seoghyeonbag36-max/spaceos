"""[Posting] 3-Tier 비용 모델 보정 — 감도 실험 하네스.

## 왜 스크립트로 남기나

비용 모델을 고치는 일은 "값을 하나 정하는" 일이 아니라 **어떤 항목을 넣으면 추천
순위와 마진이 어떻게 움직이는지**를 보고 고르는 일이다. 손으로 몇 번 돌려 보고
고르면 그 판단의 근거가 남지 않는다 — 이 프로젝트의 주된 실패 양식이 그것이다.
그래서 격자를 전부 돌려 표로 찍는다.

실행: python scripts/posting_cost_sensitivity.py

## 축 셋

- **원가(COGS)**: 매출비례. 지금 모델에 아예 없는 항목이다.
- **인건비**: `월 단가 × 필요인원`. 단가는 2026 최저임금 월 환산 215.7만원
  (시급 10,320원 × 209시간, 고용노동부). 4대보험 사업자부담은 **미포함**이다.
- **매출**: 현행 손으로 적은 계수 vs `gold/platform_posting_revenue.json` 실측 수준.

## 판정 기준 셋

문서(`docs/feature-posting.md` §3-0)의 통과 조건은 둘이었다 — 마진 10~20%,
factory 가 일부 조합에서 1위. 그 둘만으로는 **"절반이 회수불가인데 남은 절반의
마진은 예쁜"** 해가 통과한다. 그래서 회수불가 비율을 세 번째 기준으로 같이 찍는다.
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "apps" / "backend"))

from app.services import districts as D  # noqa: E402

# 현행 계수 (districts.tier_scenarios 와 같아야 한다)
SPEC = {
    "premium": dict(i_a=0.55, i_c=4, c_a=1.8, c_f=180, r_a=41, r_f=1150),
    "value": dict(i_a=0.32, i_c=2.2, c_a=1.1, c_f=95, r_a=30, r_f=760),
    "factory": dict(i_a=0.2, i_c=1.1, c_a=0.45, c_f=25, r_a=18, r_f=430),
}
_FOOT_K = {"저": 0.8, "중": 1.0, "고": 1.25}

# 2026 최저임금 월 환산(만원). 고용노동부 2026 적용 최저임금 시간급 10,320원 × 209시간.
WAGE_MONTH = 215.7

# ── 원가율 축 ──────────────────────────────────────────────────────────
COGS = {
    "C0 없음": {"premium": 0.0, "value": 0.0, "factory": 0.0},
    "C1 균등33%": {"premium": 0.33, "value": 0.33, "factory": 0.33},
    "C2 차등38/33/28": {"premium": 0.38, "value": 0.33, "factory": 0.28},
    "C3 차등32/35/40": {"premium": 0.32, "value": 0.35, "factory": 0.40},
}
# ── 인건비 축: 필요인원(명, 소수 허용) ─────────────────────────────────
HEADS = {
    "L0 없음": None,
    "L1 3.0/2.0/1.0": {"premium": 3.0, "value": 2.0, "factory": 1.0},
    "L2 4.5/2.5/1.2": {"premium": 4.5, "value": 2.5, "factory": 1.2},
    "L3 면적비례": "area",     # 평당 — premium 12평/인, value 18평/인, factory 30평/인
}
_AREA_PER_HEAD = {"premium": 12.0, "value": 18.0, "factory": 30.0}

# ── KOSIS 실측 비용 모델 ────────────────────────────────────────────────
# 위 C·L 축은 원가율·필요인원을 **우리가 골라 넣는** 격자다. 2026-08-23 KOSIS
# 서비스업조사(서울 2024)로 둘 다 실측이 생겨서, 고르는 대신 읽는 축을 하나 더 넣는다.
#
# ⚠ 이 축은 C·L 과 곱해지지 않는다 — **비용 구조 자체가 다르기 때문**이다.
#   legacy: rent + area×c_a + c_f + rev×원가율 + 인건비단가×인원
#   kosis : rent + rev × 비임차영업비용률
# KOSIS 의 영업비용에는 인건비·기타경비(원가 흡수)가 **이미 들어 있다**. 여기에
# area×c_a + c_f 나 L 축을 더하면 같은 항목을 두 번 세는 것이다. 임차료도 마찬가지라
# 파이프라인이 `opex_rate_ex_rent` 로 빼 두었고, 임대료는 유닛별 R-ONE 실측만 쓴다.
#
# 임대료 배율(rent_k)은 §0-D 가 남긴 열린 질문을 재는 축이다: R-ONE 은 **중대형 상가**
# 기준이라 소규모 점포에 과대일 수 있고, 공실 호가는 실계약가보다 높은 경향이 있다.
# 회수불가가 이 배율에 얼마나 민감한지가 (가)사실이다/(나)기준이틀렸다 를 가른다.
RENT_K = {"K1.0 호가그대로": 1.0, "K0.8 −20%": 0.8, "K0.6 −40%": 0.6}


def _cost_rates() -> dict[str, float] | None:
    """gold/platform_posting_cost_rates.json → tier별 비임차 영업비용률.

    없으면 None 을 돌려 KOSIS 축을 통째로 건너뛴다. 조용히 0 으로 떨어뜨리지 않는 것은
    `platform_posting_revenue.json` 이 빠졌을 때 R1 축이 사라지며 표를 뒤집었던 것과
    같은 사고를 막기 위해서다 — 없으면 없다고 찍는다.
    """
    p = _ROOT / "data" / "gold" / "platform_posting_cost_rates.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))["tiers"]
    return {t: d[t]["opex_rate_ex_rent"] for t in SPEC}


def _revenue_factor() -> dict[str, float] | None:
    """실측 tier 수준 ÷ 현행 모델의 실유닛 매출 중앙 → tier별 배율.

    실측(`platform_posting_revenue.json`)이 고정하는 것은 매출의 **수준**이다.
    면적 기울기는 상권분석에 점포 면적이 없어 정할 수 없으므로, 기울기는 그대로 두고
    수준만 배율로 맞춘다. 그래서 이 축은 '실측 반영'이 아니라 '실측 수준 정렬'이다.
    """
    p = _ROOT / "data" / "gold" / "platform_posting_revenue.json"
    if not p.exists():
        return None
    meas = json.loads(p.read_text(encoding="utf-8"))["seoul"]
    units = _units()
    out = {}
    for t, sp in SPEC.items():
        model = st.median([u["area"] * _FOOT_K[u["foot"]] * sp["r_a"] + sp["r_f"]
                           for u in units])
        out[t] = round(meas[t]["median"] / model, 4)
    return out


def _units() -> list[dict]:
    """유닛에 거점 id 를 붙여 돌려준다 — R2(거점별 정렬) 축이 이걸로 매출을 고른다."""
    out = []
    for d in D.DISTRICTS:
        for u in (D.resolved_units(d["id"]) or []):
            out.append({**u, "_did": d["id"]})
    return out


def _revenue_factor_by_district() -> dict[str, dict[str, float]] | None:
    """거점별 실측 중앙 ÷ 거점별 모델 중앙 → {거점: {tier: 배율}}.

    R1 은 서울 전체 중앙 하나로 모든 거점을 맞춘다. 그런데 `rent` 는 거점별
    R-ONE 실측이다 — **비싼 거점의 임대료에 서울 평균 매출을 짝지어 놓고** 손익을
    재고 있었다는 뜻이다. R2 는 양쪽을 같은 거점으로 맞춘다.
    """
    p = _ROOT / "data" / "gold" / "platform_posting_revenue.json"
    if not p.exists():
        return None
    meas = json.loads(p.read_text(encoding="utf-8")).get("districts") or {}
    units = _units()
    out: dict[str, dict[str, float]] = {}
    for did in {u["_did"] for u in units}:
        m = meas.get(did)
        us = [u for u in units if u["_did"] == did]
        if not m or not us:
            continue
        f = {}
        for t, sp in SPEC.items():
            if t not in m:
                continue
            model = st.median([u["area"] * _FOOT_K[u["foot"]] * sp["r_a"] + sp["r_f"]
                               for u in us])
            f[t] = round(m[t]["median"] / model, 4)
        if len(f) == len(SPEC):
            out[did] = f
    return out or None


def evaluate(units: list[dict], cogs: dict, heads, rev_f: dict | None,
             rates: dict | None = None, rent_k: float = 1.0,
             by_district: bool = False) -> dict:
    """rates 가 주어지면 KOSIS 비용 구조(rent + rev×비임차비용률)로 계산한다.

    그 경우 cogs·heads 는 무시된다 — KOSIS 영업비용률이 이미 그 둘을 품고 있다.
    """
    win: Counter = Counter()
    margins: dict[str, list[float]] = {t: [] for t in SPEC}
    rois: list[float] = []
    unviable = 0

    for u in units:
        base = u["area"] * _FOOT_K[u["foot"]]
        best = None
        any_viable = False
        for t, sp in SPEC.items():
            inv = u["prem"] / 100 + u["area"] * sp["i_a"] + sp["i_c"]
            rev = base * sp["r_a"] + sp["r_f"]
            if rev_f:
                # 거점별(R2)이면 한 겹 더 들어간다. 거점 실측이 없으면 배율 1(원값).
                f = rev_f.get(u["_did"], {}) if by_district else rev_f
                rev *= f.get(t, 1.0)
            if heads == "area":
                n_head = u["area"] / _AREA_PER_HEAD[t]
            else:
                n_head = (heads or {}).get(t, 0.0)
            if rates:
                cost = u["rent"] * rent_k + rev * rates[t]
            else:
                cost = (u["rent"] + u["area"] * sp["c_a"] + sp["c_f"]
                        + rev * cogs[t] + WAGE_MONTH * n_head)
            net = rev - cost
            margins[t].append(net / rev * 100)
            if net > 0:
                any_viable = True
                r = inv * 100 / net
                if best is None or (r, -net) < best[0]:
                    best = ((r, -net), t)
        if best:
            win[best[1]] += 1
            rois.append(best[0][0])
        else:
            unviable += 1
    n = len(units)
    return {
        "win": {t: win.get(t, 0) for t in SPEC},
        "unviable": unviable,
        "unviable_pct": round(unviable / n * 100, 1),
        "margin_median": {t: round(st.median(v), 1) for t, v in margins.items()},
        "roi_median": round(st.median(rois), 1) if rois else None,
    }


def _shipped():
    """서빙 코드(districts.tier_scenarios)를 실호출해 같은 지표로 요약한다.

    감도 격자를 손으로 재현하면 반드시 원본과 어긋난다(위 SPEC 상수가 이미 그 위험을
    안고 있다). 배선이 끝난 모델은 재현하지 말고 **부른다** — 그러면 이 표가
    프로덕션과 어긋날 수 없다.
    """
    from app.services import posting_revenue as PR
    if not PR.avg_store_pyeong():
        return None
    win = Counter()
    margins = {t: [] for t in SPEC}
    rois, unviable, legacy = [], 0, 0
    units = _units()
    for u in units:
        sc = D.tier_scenarios(u, u["_did"])
        if any(v["basis"] != D.COST_BASIS for v in sc.values()):
            legacy += 1
        best = None
        for t, v in sc.items():
            if v["month_rev"]:
                margins[t].append(v["month_net"] / v["month_rev"] * 100)
            if v["viable"] and (best is None or v["roi_months"] < best[0]):
                best = (v["roi_months"], t)
        if best:
            win[best[1]] += 1
            rois.append(best[0])
        else:
            unviable += 1
    n = len(units)
    return ({
        "win": {t: win.get(t, 0) for t in SPEC},
        "unviable": unviable, "unviable_pct": round(unviable / n * 100, 1),
        "margin_median": {t: round(st.median(v), 1) for t, v in margins.items()},
        "roi_median": round(st.median(rois), 1) if rois else None,
        "legacy": legacy,
    }, PR.diagnostics())


def main() -> None:
    units = _units()
    rev_f = _revenue_factor()
    print(f"실 유닛 {len(units)}건 · 인건비 단가 월 {WAGE_MONTH}만원(2026 최저임금 환산)")
    print(f"매출 실측 정렬 배율: {rev_f}\n")

    rev_bd = _revenue_factor_by_district()
    rev_axes = [("R0 현행계수", None, False)]
    if rev_f:
        rev_axes.append(("R1 서울수준정렬", rev_f, False))
    if rev_bd:
        rev_axes.append(("R2 거점별정렬", rev_bd, True))
        print(f"거점별 정렬 가능 거점: {len(rev_bd)}/{len(D.DISTRICTS)}")

    hdr = (f"{'매출':14s} {'원가':16s} {'인건비':16s} "
           f"{'P/V/F 1위':>16s} {'회수불가':>9s} {'마진중앙 P/V/F':>22s} {'회수중앙':>8s}")
    print(hdr)
    print("-" * len(hdr))
    rows = []
    for rev_name, rf, bd in rev_axes:
        for c_name, cogs in COGS.items():
            for l_name, heads in HEADS.items():
                r = evaluate(units, cogs, heads, rf, by_district=bd)
                w = r["win"]
                m = r["margin_median"]
                print(f"{rev_name:14s} {c_name:16s} {l_name:16s} "
                      f"{w['premium']:5d}/{w['value']:4d}/{w['factory']:4d} "
                      f"{r['unviable_pct']:8.1f}% "
                      f"{m['premium']:7.1f}/{m['value']:6.1f}/{m['factory']:6.1f} "
                      f"{str(r['roi_median']):>8s}")
                rows.append((rev_name, c_name, l_name, r))

    # ── KOSIS 실측 비용 모델 (2026-08-23) ─────────────────────────────
    # 위 격자는 우리가 값을 고른 것이고, 아래는 실측을 읽은 것이다. 표를 나눠 찍는 것은
    # 둘의 비용 구조가 달라 같은 열로 비교할 수 없기 때문이다(RENT_K 위 주석 참조).
    rates = _cost_rates()
    if rates is None:
        print()
        print("⚠ gold/platform_posting_cost_rates.json 없음 — KOSIS 축을 건너뛴다.")
        print("  python data/pipelines/build_posting_cost_rates.py 로 생성할 것.")
    else:
        print()
        print("=== KOSIS 실측 비용 (서울 2024 · 비임차 영업비용률) ===")
        print("  " + " · ".join(f"{t} {v*100:.1f}%" for t, v in rates.items()))
        k_hdr = (f"{'매출':14s} {'임대료':16s} {'':16s} "
                 f"{'P/V/F 1위':>16s} {'회수불가':>9s} {'마진중앙 P/V/F':>22s} {'회수중앙':>8s}")
        print(k_hdr)
        print("-" * len(k_hdr))
        for rev_name, rf, bd in rev_axes:
            for k_name, k in RENT_K.items():
                r = evaluate(units, COGS["C0 없음"], None, rf, rates=rates,
                             rent_k=k, by_district=bd)
                w, m = r["win"], r["margin_median"]
                print(f"{rev_name:14s} {k_name:16s} {'':16s} "
                      f"{w['premium']:5d}/{w['value']:4d}/{w['factory']:4d} "
                      f"{r['unviable_pct']:8.1f}% "
                      f"{m['premium']:7.1f}/{m['value']:6.1f}/{m['factory']:6.1f} "
                      f"{str(r['roi_median']):>8s}")
                rows.append((rev_name, "KOSIS 실측", k_name, r))

    shipped = _shipped()
    if shipped is None:
        print()
        print("⚠ 실측 모델 재료 없음 — data/pipelines/build_posting_revenue.py 와 "
              "build_posting_cost_rates.py 를 먼저 돌릴 것.")
    else:
        r, diag = shipped
        m, w = r["margin_median"], r["win"]
        print()
        print("=== 배선된 실측 모델 (districts.tier_scenarios 실호출) ===")
        print(f"  평균 점포 면적 A({diag['area_basis']}): {diag['avg_store_pyeong']}"
              f"   ← 역산폴백이면 {diag['avg_store_pyeong_from_rent']}")
        print(f"  매출 절대수준: {diag['revenue_basis']} · KOSIS 점포당 {diag['kosis_store_sales']}")
        print(f"  평당매출 중앙(만원/평·월): {diag['per_pyeong_median']}")
        print("  비임차 영업비용률: " + " · ".join(
            f"{t} {v*100:.1f}%" for t, v in diag["opex_rate_ex_rent"].items()))
        print(f"  마진중앙 P/V/F {m['premium']:.1f}/{m['value']:.1f}/{m['factory']:.1f}"
              f"   회수불가 {r['unviable_pct']}%   회수중앙 {r['roi_median']}개월"
              f"   1위 {w['premium']}/{w['value']}/{w['factory']}")
        print(f"  legacy 폴백으로 계산된 유닛: {r['legacy']}건")
        rows.append(("배선 실측모델", "KOSIS 비용", "실측 평당매출", r))

    # 통과 조건 셋을 동시에 만족하는 조합만 추린다
    # ⚠ 마진 기준을 10~20% → 3.5~10.5% 로 내렸다(2026-08-23). 10~20% 는 KOSIS 를
    # 얻기 전에 감으로 적은 값인데, 서울 2024 실측 영업이익률이 **3.5~10.5%** 로
    # 나왔다. **실측이 기준을 반증했으므로** 기준을 실측 대역에 맞춘다 — 그대로 두면
    # 어떤 조합도 통과할 수 없고, 통과한다면 그건 비용을 덜 센 것이다.
    LO, HI = 3.5, 10.5
    print()
    print(f"=== 통과 조건: 마진(P) {LO}~{HI}%(KOSIS 실측 대역) · factory >=1위 · 회수불가 <=20% ===")
    ok = [(a, b, c, r) for a, b, c, r in rows
          if LO <= r["margin_median"]["premium"] <= HI
          and r["win"]["factory"] > 0 and r["unviable_pct"] <= 20]
    if not ok:
        print("  없음 — 세 조건을 동시에 만족하는 조합이 이 격자에 없다.")
        near = sorted(rows, key=lambda x: (x[3]["unviable_pct"],
                                           abs(x[3]["margin_median"]["premium"] - (LO + HI) / 2)))[:3]
        print("  가장 가까운 셋:")
        for a, b, c, r in near:
            print(f"    {a} · {b} · {c} → 마진 {r['margin_median']['premium']}% · "
                  f"factory {r['win']['factory']}승 · 회수불가 {r['unviable_pct']}%")
    else:
        for a, b, c, r in ok:
            print(f"  {a} · {b} · {c} → 마진 {r['margin_median']['premium']}% · "
                  f"factory {r['win']['factory']}승 · 회수불가 {r['unviable_pct']}%")


if __name__ == "__main__":
    main()
