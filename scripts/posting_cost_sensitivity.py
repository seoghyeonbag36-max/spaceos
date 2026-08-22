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
    return [u for d in D.DISTRICTS for u in (D.resolved_units(d["id"]) or [])]


def evaluate(units: list[dict], cogs: dict, heads, rev_f: dict | None) -> dict:
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
                rev *= rev_f[t]
            if heads == "area":
                n_head = u["area"] / _AREA_PER_HEAD[t]
            else:
                n_head = (heads or {}).get(t, 0.0)
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


def main() -> None:
    units = _units()
    rev_f = _revenue_factor()
    print(f"실 유닛 {len(units)}건 · 인건비 단가 월 {WAGE_MONTH}만원(2026 최저임금 환산)")
    print(f"매출 실측 정렬 배율: {rev_f}\n")

    rev_axes = [("R0 현행계수", None)]
    if rev_f:
        rev_axes.append(("R1 실측수준정렬", rev_f))

    hdr = (f"{'매출':14s} {'원가':16s} {'인건비':16s} "
           f"{'P/V/F 1위':>16s} {'회수불가':>9s} {'마진중앙 P/V/F':>22s} {'회수중앙':>8s}")
    print(hdr)
    print("-" * len(hdr))
    rows = []
    for rev_name, rf in rev_axes:
        for c_name, cogs in COGS.items():
            for l_name, heads in HEADS.items():
                r = evaluate(units, cogs, heads, rf)
                w = r["win"]
                m = r["margin_median"]
                print(f"{rev_name:14s} {c_name:16s} {l_name:16s} "
                      f"{w['premium']:5d}/{w['value']:4d}/{w['factory']:4d} "
                      f"{r['unviable_pct']:8.1f}% "
                      f"{m['premium']:7.1f}/{m['value']:6.1f}/{m['factory']:6.1f} "
                      f"{str(r['roi_median']):>8s}")
                rows.append((rev_name, c_name, l_name, r))

    # 통과 조건 셋을 동시에 만족하는 조합만 추린다
    print("\n=== 통과 조건: 마진(P) 10~20% · factory ≥1위 · 회수불가 ≤20% ===")
    ok = [(a, b, c, r) for a, b, c, r in rows
          if 10 <= r["margin_median"]["premium"] <= 20
          and r["win"]["factory"] > 0 and r["unviable_pct"] <= 20]
    if not ok:
        print("  없음 — 세 조건을 동시에 만족하는 조합이 이 격자에 없다.")
        near = sorted(rows, key=lambda x: (x[3]["unviable_pct"],
                                           abs(x[3]["margin_median"]["premium"] - 15)))[:3]
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
