"""[검증] capacity 산식 판정 채점 — floor_approx vs floor_ouln 중 무엇이 사실인가.

make_capacity_sample 로 만든 표본에 로드뷰 관찰값이 채워지면 실행한다.

세 가지를 따로 답한다.
  1) 층수 산식   — 대장 지상층수(implied_floors) 가 실제 상업 층수보다 몇 배 많은가.
                   floor_approx 가 분모를 부풀린다는 가설의 직접 검정.
  2) 층당 호수   — units_actual 이 있으면 STORES_PER_FLOOR=2 근사가 맞는지.
  3) 최종 판정   — 각 산식으로 capacity 를 다시 깔았을 때 status 정확도와
                   집계 공실률이 로드뷰 라벨/부동산원 앵커에 얼마나 맞는가.

정확도 판정 규칙은 score_labels 와 동일하다(라벨 → 허용 예측 status).

실행: python -m data.validation.score_capacity_method ikseon [slug ...]
"""
from __future__ import annotations

import csv
import statistics
import sys
from collections import Counter
from pathlib import Path

from data.collectors.building_vacancy import STORES_PER_FLOOR, classify
from data.pipelines.calibrate_vacancy import anchor_of

if hasattr(sys.stdout, "reconfigure"):     # Windows 콘솔 cp949 크래시 방지
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_OUT = Path(__file__).resolve().parent
_ALLOWED = {
    "공실": {"empty", "high"},
    "부분공실": {"partial", "high"},
    "영업": {"full", "partial"},
}


def _num(v: str) -> float | None:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _vacancy(active: float, cap: float | None) -> tuple[float | None, str]:
    """(공실률%, status) — 하한 capacity=active 규칙은 파이프라인과 동일."""
    if not cap:
        return None, "unknown"
    occ = min(active / max(cap, active), 1.0)
    return round((1 - occ) * 100, 1), classify(occ, "floor_ouln")


def score(slug: str) -> None:
    path = _OUT / f"roadview_capacity_{slug}.csv"
    if not path.exists():
        print(f"[score:{slug}] {path.name} 없음 — make_capacity_sample 을 먼저 실행하세요")
        return
    anchor = anchor_of(slug)               # 거점별 R-ONE 앵커 (2026-07-28 이전 단일 41.6% 대체)
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    labeled = [r for r in rows if (r.get("label_actual") or "").strip() in _ALLOWED]
    if not labeled:
        print(f"[score:{slug}] label_actual 이 비어 있음 — {path.name} 을 먼저 채우세요 "
              f"(총 {len(rows)}동 대기)")
        return

    print(f"\n{'='*66}\n[score:{slug}] 채점 {len(labeled)}동 (불명/미기입 제외 {len(rows)-len(labeled)})")

    # ── 1) 층수 산식 ────────────────────────────────────────────────
    ratios, floor_gap = [], []
    for r in labeled:
        imp, act = _num(r.get("implied_floors")), _num(r.get("commercial_floors_actual"))
        if imp and act:
            ratios.append(imp / act)
            floor_gap.append(imp - act)
    if ratios:
        med = statistics.median(ratios)
        print(f"\n1) 층수 — 대장 지상층수 / 실제 상업층수 (n={len(ratios)})")
        print(f"   중앙값 {med:.2f}배 · 평균 {statistics.fmean(ratios):.2f}배 "
              f"· 층 차이 중앙값 {statistics.median(floor_gap):+.1f}층")
        if med > 1.15:
            print(f"   → floor_approx 가 분모를 약 {med:.2f}배 부풀린다. floor_ouln 방향이 옳다.")
        elif med < 0.87:
            print(f"   → 대장 층수가 오히려 적다. 지하·복층 상가 누락을 의심할 것.")
        else:
            print("   → 두 산식의 층수 차이가 유의하지 않다. 분모 문제는 층수가 아닌 곳에 있다.")
    else:
        print("\n1) 층수 — commercial_floors_actual 이 비어 있어 판정 불가")

    # ── 2) 층당 호수 ────────────────────────────────────────────────
    per_floor = [u / f for r in labeled
                 if (u := _num(r.get("units_actual"))) and (f := _num(r.get("commercial_floors_actual")))]
    print(f"\n2) 층당 호수 — 현재 근사 STORES_PER_FLOOR={STORES_PER_FLOOR}")
    if per_floor:
        med = statistics.median(per_floor)
        print(f"   실측 중앙값 {med:.2f}호/층 (n={len(per_floor)}) "
              f"→ {'근사 타당' if abs(med - STORES_PER_FLOOR) < 0.5 else f'{med:.1f} 로 조정 검토'}")
    else:
        print("   units_actual 미기입 — 판정 보류(선택 항목)")

    # ── 3) 산식별 재계산 ────────────────────────────────────────────
    rules = {
        "floor_approx(현행)": lambda r: _num(r.get("capacity")),
        "floor_ouln(상업층×2)": lambda r: (f * STORES_PER_FLOOR
                                         if (f := _num(r.get("commercial_floors_actual"))) else None),
        "units_actual(실측호수)": lambda r: _num(r.get("units_actual")),
    }
    print("\n3) 산식별 재계산")
    print(f"   {'산식':24s} {'판정가능':>6s} {'정확도':>8s} {'집계공실':>9s} {'앵커격차':>9s}")
    verdict: dict[str, float] = {}
    for name, cap_of in rules.items():
        ok = n = 0
        act_sum = cap_sum = 0.0
        for r in labeled:
            cap, active = cap_of(r), _num(r.get("active")) or 0
            if not cap:
                continue
            n += 1
            act_sum += active
            cap_sum += max(cap, active)
            _, st = _vacancy(active, cap)
            if st in _ALLOWED[r["label_actual"].strip()]:
                ok += 1
        if not n:
            print(f"   {name:24s} {'—':>6s} {'(데이터 없음)':>18s}")
            continue
        acc = ok / n * 100
        est = (1 - act_sum / cap_sum) * 100 if cap_sum else float("nan")
        verdict[name] = acc
        print(f"   {name:24s} {n:>6d} {acc:>7.1f}% {est:>8.1f}% {est - anchor:>+8.1f}%p")

    if verdict:
        best = max(verdict, key=verdict.get)
        print(f"\n   판정: {best} 이 status 정확도 {verdict[best]:.1f}% 로 가장 높다.")
        if len(verdict) > 1:
            second = sorted(verdict.values(), reverse=True)[1]
            if verdict[best] - second < 5:
                print("   ⚠ 2위와 5%p 이내 — 표본을 늘리기 전엔 결론을 확정하지 말 것.")
        print(f"   (참고: {slug} R-ONE 앵커 {anchor:.1f}%. 앵커격차가 큰 산식이라도 "
              "로드뷰 정확도가 높다면 앵커 쪽을 의심해야 한다.)")

    conf = Counter((r["label_actual"].strip(), r["status_predicted"]) for r in labeled)
    print("\n   현행 예측 혼동(실제라벨 → 예측):")
    for (a, p), c in sorted(conf.items()):
        print(f"     {a} → {p}: {c}")


def main() -> None:
    slugs = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not slugs:
        print("사용법: python -m data.validation.score_capacity_method <slug> [slug ...]")
        return
    for s in slugs:
        score(s)


if __name__ == "__main__":
    main()
