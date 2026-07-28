"""[검증] STORES_PER_FLOOR 실측 — 로드뷰 라벨링 **없이** 분모 상수를 검정한다.

배경(2026-07-28): `STORES_PER_FLOOR` 는 "일반건물의 상업 층 하나에 상가 호가 몇 개인가"
라는 근사이고, 13거점 공실률 수준을 통째로 좌우한다. 원래는 로드뷰 표본에
`units_actual` 을 사람이 채워야 판정할 수 있다고 봤지만(make_capacity_sample),
같은 질문에 답하는 데이터가 이미 수집돼 있다.

세 갈래로 각각 측정한다. 셋 다 독립 데이터원이라 서로를 검증한다:

  A. 상가정보 flrNo  — 영업 중인 점포를 (건물, 지상층)으로 묶어 층당 점포 수를 센다.
     표본이 압도적으로 크고(11거점 1만 건물층+), 사람 손이 안 들어간다.
     한계: 이건 **점유된** 호 수라 capacity 의 하한이다. 다만 공실률이 R-ONE 수준
     (5~17%)이라면 SPF=2 일 때 층당 1.7개가 관측돼야 하는데, 실측은 1.0 이다.
  B. 전유부 실측     — 집합건물의 상업 전유 호 / 그 호들이 걸친 층 수. 실제 호 수라
     하한이 아니지만 모집단이 집합건물이라 대형 상가 쪽으로 치우친다.
     → 소형(전유 호 10 이하)만 보면 SPF 적용 대상과 성격이 가장 가깝다.
  C. 로드뷰 라벨     — score_capacity_method 가 담당(표본 작음, 사람 손 필요).

실행: python -m data.validation.measure_stores_per_floor [slug ...]
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict

from data.collectors.building_vacancy import (
    NON_STOREFRONT_LCLS, STORES_PER_FLOOR, expos_units)
from data.collectors.common import GOLD, load_latest
from data.config.page_hubs import HUBS

# SPF 가 실제로 적용되는 capacity 산출 방식 — 전유부가 없어 층수로 근사하는 건물.
_FLOOR_METHODS = {"floor_ouln", "floor_approx"}


def _ground_floor(v: str) -> bool:
    """지상층인가. 분모(상업 '지상' 층)와 모집단을 맞추기 위해 지하는 뺀다."""
    try:
        return int(float(str(v).strip())) >= 1
    except ValueError:
        return False


def measure_flrno(slugs: list[str]) -> dict[str, Counter]:
    """A. 상가정보 flrNo → {세그먼트: Counter(층당 점포 수)}."""
    seg: dict[str, Counter] = defaultdict(Counter)
    for slug in slugs:
        gold = GOLD / slug / "building_vacancy.json"
        if not gold.exists():
            continue
        method = {r["bdMgtSn"]: r.get("capacity_method")
                  for r in json.loads(gold.read_text(encoding="utf-8"))}
        stores = [s for s in (load_latest(slug, "stores_raw.json") or [])
                  if s.get("indsLclsNm") not in NON_STOREFRONT_LCLS]
        floors: Counter = Counter()
        for s in stores:
            bld = s.get("bldMngNo") or ""
            flr = str(s.get("flrNo") or "").strip()
            if bld and flr and _ground_floor(flr):
                floors[(bld, flr)] += 1
        for (bld, _), n in floors.items():
            key = "일반건물(SPF 적용)" if method.get(bld) in _FLOOR_METHODS else "집합건물·기타"
            seg[key][n] += 1
    return seg


def measure_expos(slugs: list[str]) -> tuple[list[float], list[float]]:
    """B. 전유부 실측 → (전체 호/층 비율, 소형건물만)."""
    allv: list[float] = []
    small: list[float] = []
    for slug in slugs:
        raw = load_latest(slug, "bldg_ledger_raw.json") or {}
        for v in raw.values():
            units = expos_units(v.get("expos") or [])
            if not units:
                continue
            flrs = {t[2] for t in units if t[2]}
            if not flrs:
                continue
            ratio = len(units) / len(flrs)
            allv.append(ratio)
            if len(units) <= 10:      # 소형 = SPF 적용 대상(일반건물)과 성격이 가깝다
                small.append(ratio)
    return allv, small


def _describe(vals: list[float]) -> str:
    q = sorted(vals)
    return (f"n={len(q):,} · 중앙값 {statistics.median(q):.2f} · 평균 "
            f"{statistics.fmean(q):.2f} · p25 {q[len(q)//4]:.2f} · p75 {q[3*len(q)//4]:.2f}")


def main() -> None:
    slugs = [a for a in sys.argv[1:] if not a.startswith("-")] or list(HUBS)
    slugs = [s for s in slugs if (GOLD / s / "building_vacancy.json").exists()]
    print(f"[spf] 대상 {len(slugs)}거점 · 현행 STORES_PER_FLOOR = {STORES_PER_FLOOR}\n")

    print("A. 상가정보 flrNo — 영업 중인 (건물, 지상층)당 점포 수")
    for key, cnt in measure_flrno(slugs).items():
        tot = sum(cnt.values())
        vals = [n for n, c in cnt.items() for _ in range(c)]
        ge3 = sum(c for n, c in cnt.items() if n >= 3)
        print(f"   {key:18s} 건물층 {tot:7,d} · 중앙값 {statistics.median(vals):.2f} "
              f"· 평균 {statistics.fmean(vals):.2f} · 1개뿐 {cnt[1]/tot*100:.1f}% "
              f"· 3개이상 {ge3/tot*100:.1f}%")

    allv, small = measure_expos(slugs)
    print("\nB. 전유부 실측 — 상업 전유 호 / 그 호들이 걸친 층 수")
    if allv:
        print(f"   {'전체':18s} {_describe(allv)}")
    if small:
        print(f"   {'소형(호 10 이하)':18s} {_describe(small)}")

    print("\n판정: A 의 '일반건물' 중앙값과 B 의 '소형' 중앙값이 곧 SPF 의 실측 근거다.\n"
          "      A 는 점유 호 수이므로 하한 — 공실이 있는 만큼 실제 capacity 는 이보다\n"
          "      크다. 다만 R-ONE 수준(공실 5~17%)에서 SPF=2 라면 A 가 1.7 근처여야 한다.")


if __name__ == "__main__":
    main()
