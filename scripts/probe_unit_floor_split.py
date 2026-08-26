"""Posting `area` 유닛 서열 — 유닛↔층 1:1 로 풀기 전에 통과조건을 먼저 잰다.

## 무엇을 판정하나

현행 인벤토리는 벌어진 건물 하나당 유닛 **1개**를 내고 그 면적은 `com_area ÷ capacity`
다 — 코드가 스스로 "건물의 **호실당 평균**"이라 적어 두었고, `floor` 도 특정 층이
아니라 범위("1~4F")다. 그래서 게이트가 `area` 를 0.5 가중으로만 세고 있었다.

## 왜 지금 풀 수 있나 (2026-08-26 실측)

| 사실 | 값 |
|---|---|
| `capacity` == 상업층 수 | **495/528 = 93.8%** (나머지 32건도 차이 1) |
| 건물 내 층별 면적비중 max/min | 중앙 **1.40** · p75 2.33 · p90 **4.56** · 최대 22.0 |
| 비중이 1.2배 넘게 갈리는 유닛 | **327 (62%)** |

즉 균등분할은 자료 부재가 아니라 **이미 산출물에 있는 `floor_mix` 를 평균으로 뭉개고
있는 것**이다. `floor_mix` 는 §0-L 이 "새 가정을 들인 것이 아니라 이미 쓰던 면적을
쪼갠 것"이라 검증해 둔 값이다(층 집합 ⊂ `com_flr_nos` 528/528 · 층별 합 ↔
`com_area_flr` 중앙비 1.000).

## 왜 호실 실면적(전유부)이 아닌가 — 그 길은 막혀 있다

`silver/*/expos_units.json` 이 호실별 실면적을 54/54거점 싣고 있다. 그런데 **인벤토리와
교집합이 0** 이다(공실유닛 450 PNU 전수). 우연이 아니라 설계다:
`_COUNTED_METHODS = {"floor_ouln"}` 이라 인벤토리는 **일반건축물만** 싣고, 전유부는
**집합건물**에만 있다. 집합건물을 넣는 것은 다른 문제로 막혀 있다 — 상가정보가 대형
집합상가 **내부** 점포를 그 건물 bdMgtSn 으로 귀속시키지 못해 공실률이 78~86% 로
튀고 거점 대표값이 무너진다(seoulsup 67.0%→19.8% · 앵커 3.4%). 그 해제 조건은
`gold_vacancy` 독스트링이 적어 둔 대로 **층·호 단위 매칭**이고, 상가정보에는 `flrNo` 는
있어도 호가 없다. 그래서 이 프로브는 전유부가 아니라 **층**을 쓴다.

## 판정 규칙 — 돌리기 전에 정해 둔다

§0-M 이 층 축을 한 번 되돌린 자리다(빈 층 배정 → 프라임 프리미엄 부호 역전 →
임계값 안 건드리고 되돌림). 같은 규율을 따른다:

    통과조건 4종(회수불가 · factory 승수 · 평당매출 · 마진 대역) 중 하나라도 나빠지거나
    `premium_pp > 0` 트립와이어가 깨지면 **임계값을 건드리지 않고 되돌린다.**

실행: python scripts/probe_unit_floor_split.py
산출: reports/unit_floor_split_probe_{날짜}.json
"""
from __future__ import annotations

import collections
import json
import statistics as st
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for p in (_ROOT, _ROOT / "apps" / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.services import districts as D                    # noqa: E402
from app.services import posting_inputs as PI              # noqa: E402
from app.services import posting_revenue as PR             # noqa: E402
from app.services import vacant_inventory                  # noqa: E402

_OUT = _ROOT / "reports" / f"unit_floor_split_probe_{date.today().isoformat()}.json"
_M2_PER_PYEONG = 3.3058
# build_vacant_units 와 **같은 범위**여야 한다 — 여기서 넓히면 프로브가 통과시킨 유닛이
# 파이프라인에서 탈락해 두 수가 안 맞는다.
_MIN_PYEONG, _MAX_PYEONG = 3, 300


def _units() -> list[dict]:
    """현행 인벤토리 — 서빙과 같은 경로(resolved_units)."""
    out = []
    for d in D.DISTRICTS:
        for u in (D.resolved_units(d["id"]) or []):
            out.append({**u, "_did": d["id"]})
    return out


def _split_units() -> list[dict]:
    """층 분할 인벤토리 — **원 유닛에서 쪼갠 뒤 같은 resolver 를 다시 태운다.**

    ⚠ 처음에는 `resolved_units()` 결과를 쪼개면서 `area` 만 갈아끼웠는데, 그러면
    `rent` 가 **건물 층 가중평균 계수**(중앙 0.549)로 계산된 값 그대로 남는다. 층을
    나눈 유닛의 임대료는 그 층의 계수여야 하므로 분모만 바뀌고 분자가 안 바뀌어
    rent/rev 가 부풀고, 프라임 프리미엄이 **인위적으로** 음수가 됐다. 배분을 바꿨으면
    두 축을 같이 바꿔야 공정한 비교다.

    그래서 `floor_mix` 를 단일층(`{층: 1.0}`)으로 두고 `resolve_units` 를 다시 부른다 —
    `_mixed_floor_factor` 가 그 층의 계수를 쓰고, `foot` 오프셋도 새 유닛 목록 위에서
    다시 매겨진다.
    """
    out = []
    for d in D.DISTRICTS:
        did = d["id"]
        doc = vacant_inventory.load(did) or {}
        raw = doc.get("units") or []
        if not raw:
            continue
        split = [x for u in raw for x in _split(u)]
        for u in PI.resolve_units(did, split):
            out.append({**u, "_did": did})
    return out


def _split(u: dict) -> list[dict]:
    """유닛 1개(건물 평균) → 상업층마다 1개.

    면적은 `com_area × floor_mix[층]` 이다. 층별 비중의 합이 1.0 이므로 **건물 합계는
    보존된다** — 총량을 늘리는 것이 아니라 배분을 되살리는 것이다.

    `com_area_m2` 가 없으면 현행 유닛을 그대로 돌려준다(면적을 가정하지 않는다).
    """
    mix = u.get("floor_mix") or {}
    com = u.get("com_area_m2")
    if not mix or not com:
        return [u]
    out = []
    for flr, share in sorted(mix.items(), key=lambda kv: int(kv[0][:-1])):
        pyeong = round(com * share / _M2_PER_PYEONG)
        if not (_MIN_PYEONG <= pyeong <= _MAX_PYEONG):
            continue                      # 파이프라인과 같은 범위 필터
        out.append({**u, "id": f"{u['id']}#{flr}", "area": pyeong, "floor": flr,
                    # 층을 하나로 못박는다 — _mixed_floor_factor 가 이 층의 계수를
                    # 쓰게 하려는 것이다. 건물 가중평균을 그대로 두면 면적만 층별이고
                    # 임대료는 건물 평균이라 둘의 짝이 어긋난다.
                    "floor_mix": {flr: 1.0},
                    "_split_from": u["id"]})
    return out or [u]


def _evaluate(units: list[dict]) -> dict:
    """서빙 코드(tier_scenarios)를 실호출한다 — 손으로 재현하면 프로덕션과 어긋난다."""
    win: collections.Counter = collections.Counter()
    margins: dict[str, list[float]] = {t: [] for t in PR.TIERS}
    rent_share: dict[str, list[float]] = {t: [] for t in PR.TIERS}
    rois: list[float] = []
    unviable = 0
    for u in units:
        sc = D.tier_scenarios(u, u["_did"])
        best = None
        for t, v in sc.items():
            if v["month_rev"]:
                margins[t].append(v["month_net"] / v["month_rev"] * 100)
                # 테스트(_margin_and_rent_share)와 **같은 분자**를 쓴다 —
                # 유닛의 rent 이지 시나리오 항목이 아니다.
                rent_share[t].append(u["rent"] / v["month_rev"])
            if v["viable"] and (best is None or v["roi_months"] < best[0]):
                best = (v["roi_months"], t)
        if best:
            win[best[1]] += 1
            rois.append(best[0])
        else:
            unviable += 1
    n = len(units)
    rates = PR._rates()
    return {
        "units": n,
        "unviable": unviable,
        "unviable_pct": round(unviable / n * 100, 2),
        "win": {t: win.get(t, 0) for t in PR.TIERS},
        "margin_median": {t: round(st.median(v), 2) for t, v in margins.items()},
        "roi_median": round(st.median(rois), 1) if rois else None,
        # 트립와이어 — 부호가 뒤집히면 마진 격차의 산술 분해가 깨진다(§0-N·§0-O)
        "premium_pp": {t: round((st.median(rent_share[t]) - rates[t]["rent_rate"]) * 100, 4)
                       for t in PR.TIERS},
        "area_median": round(st.median([u["area"] for u in units]), 1),
        "area_p10_p90": [sorted(u["area"] for u in units)[n // 10],
                         sorted(u["area"] for u in units)[9 * n // 10]],
    }


def run() -> dict:
    base = _units()
    split = _split_units()
    print(f"[probe] 현행 {len(base)}유닛 → 층 분할 {len(split)}유닛 "
          f"(x{len(split) / len(base):.2f})")

    a = _evaluate(base)
    b = _evaluate(split)

    # 통과조건 4종 중 이 프로브가 셀 수 있는 셋 + 트립와이어. 평당매출은 유닛 면적과
    # 무관한 상수(업종×상권)라 분할로 안 변한다 — 그래서 여기서는 안 센다.
    checks = {
        "회수불가 (낮을수록 좋다)": (a["unviable_pct"], b["unviable_pct"],
                              b["unviable_pct"] <= a["unviable_pct"] + 0.5),
        "factory 승수 비율": (round(a["win"]["factory"] / a["units"] * 100, 1),
                          round(b["win"]["factory"] / b["units"] * 100, 1), None),
    }
    trip_ok = all(v > 0 for v in b["premium_pp"].values())
    margin_ok = all(3.5 <= v <= 10.5 for v in b["margin_median"].values())

    print(f"[probe] 회수불가 {a['unviable_pct']}% → {b['unviable_pct']}%")
    print(f"[probe] 마진중앙 "
          + " · ".join(f"{t} {a['margin_median'][t]}→{b['margin_median'][t]}"
                       for t in PR.TIERS)
          + f"  (KOSIS 대역 3.5~10.5: {'✅' if margin_ok else '❌'})")
    print(f"[probe] factory 승 {a['win']['factory']}/{a['units']} → "
          f"{b['win']['factory']}/{b['units']}")
    print(f"[probe] 프라임 프리미엄(pp) "
          + " · ".join(f"{t} {a['premium_pp'][t]:+.3f}→{b['premium_pp'][t]:+.3f}"
                       for t in PR.TIERS)
          + f"  (>0 트립와이어: {'✅' if trip_ok else '❌ 깨짐'})")
    print(f"[probe] 면적 중앙 {a['area_median']}평 → {b['area_median']}평 · "
          f"p10~p90 {a['area_p10_p90']} → {b['area_p10_p90']}")

    verdict = "적용" if (trip_ok and margin_ok
                       and b["unviable_pct"] <= a["unviable_pct"] + 0.5) else "되돌림"
    print(f"[probe] ▶ 판정: **{verdict}**")

    out = {
        "probe": "unit_floor_split",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": ("유닛을 상업층마다 1개로 풀면 통과조건 4종과 프라임 프리미엄 "
                     "트립와이어가 유지되는가 — 파이프라인을 고치기 전에 잰다"),
        "rule_preregistered": ("하나라도 나빠지거나 premium_pp>0 이 깨지면 임계값을 "
                               "건드리지 않고 되돌린다 (§0-M 이 층 축에서 한 번 겪었다)"),
        "why_not_expos": ("전유부 호실 실면적은 집합건물 전용이고 인벤토리는 "
                          "_COUNTED_METHODS={'floor_ouln'} 이라 일반건축물만 — "
                          "공실유닛 450 PNU 와 교집합 0(설계상 배제)"),
        "before": a, "after": b,
        "checks": {k: {"before": v[0], "after": v[1]} for k, v in checks.items()},
        "tripwire_premium_pp_positive": trip_ok,
        "margin_in_kosis_band": margin_ok,
        "verdict": verdict,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[probe] → {_OUT.relative_to(_ROOT)}")
    return out


if __name__ == "__main__":
    run()
