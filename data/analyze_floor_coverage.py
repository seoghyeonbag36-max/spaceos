"""[Page] 층 커버리지 진단 — 건물 규모별로 분자가 어디서 무너지는가.

2026-08-01 층 단위 전환 이후 남은 계통 편향을 좁히는 진단기다(API 콜 0, 산출물 무수정).
소규모(2층↓·330㎡↓) 세그먼트는 R-ONE 앵커와 ±3%p 로 일치하는데 중대형만 +3.5~+23.7%p
벌어진다 — 규모에 비례하는 분자 결손이 남았다는 뜻이다(`docs/prompt-large-building-coverage.md`).

출력
  표 1) 분모 층수 구간(1~2 / 3~5 / 6~10 / 11+)별 공실률·점유율 — 어디서 꺾이는지
  표 2) 층 번호별 점유율(점포·인허가 확인분)을 구간별로 — 상층부가 비는지, 큰 건물이 통째로 비는지
  표 3) 인허가(영업 중) 주소의 층 표기 파싱률 — 상층부를 덮을 독립 소스의 상한

실행: python -m data.analyze_floor_coverage [거점 ...]
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict

from data.collectors.common import BRONZE, GOLD
from data.pipelines.build_building_attrs import lic_floors
from data.pipelines.build_building_attrs import load as load_attrs
from data.pipelines.calibrate_vacancy import _rone_latest

TIER1 = ["garosugil", "apgujeong-rodeo", "hongdae", "yeonnam", "ikseon", "seochon",
         "myeongdong", "euljiro", "seongsu", "seoulsup", "itaewon", "hannam", "songridan"]

# 분모 층수 구간 — R-ONE 중대형 표본은 3층 이상이 기준이라 그 근처를 쪼갠다.
BUCKETS = ((1, 2, "1~2층"), (3, 5, "3~5층"), (6, 10, "6~10층"), (11, 999, "11층+"))


def bucket_of(n: int) -> str:
    for lo, hi, label in BUCKETS:
        if lo <= n <= hi:
            return label
    return "1~2층"


def buildings(slug: str) -> list[dict]:
    """층 근거가 있는 지번 목록 (지번 dedupe — capacity 는 지번당 산출물)."""
    rows = json.loads((GOLD / slug / "building_vacancy.json").read_text(encoding="utf-8"))
    attrs = load_attrs(slug)
    per: dict[str, dict] = {}
    for r in rows:
        if r.get("active_floors_hi") is None or not r.get("capacity"):
            continue
        at = attrs.get(r.get("lnoCd", ""), {})
        if at.get("is_mall") or not at.get("is_shop"):
            continue                      # 집합·비상가는 R-ONE 중대형 대조 대상이 아니다
        per[r["lnoCd"]] = {
            "floors": r.get("capacity_floors") or [],
            "lo": r["active_floors_lo"], "hi": r["active_floors_hi"],
            "cap": r["capacity"], "size": at.get("rone_size"),
            "area": at.get("com_area_flr") or 0.0,
            # 점포(상가정보) ∪ 인허가로 층이 확인된 집합 — 분자의 하한 근거
            "known": set(at.get("store_flr_nos") or []) | set(at.get("lic_flr_nos") or []),
        }
    return list(per.values())


def main() -> None:
    slugs = [a for a in sys.argv[1:] if not a.startswith("-")] or TIER1
    anchors = _rone_latest("vac_mid")

    agg: dict[str, dict] = defaultdict(lambda: {"n": 0, "cap": 0, "lo": 0, "hi": 0,
                                                "area": 0.0, "vac_area": 0.0})
    by_floor: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    per_hub: list[tuple] = []
    for slug in slugs:
        bs = buildings(slug)
        hub = defaultdict(lambda: {"n": 0, "cap": 0, "hi": 0})
        for b in bs:
            k = bucket_of(b["cap"])
            a, h = agg[k], hub[k]
            a["n"] += 1
            a["cap"] += b["cap"]
            a["lo"] += b["lo"]
            a["hi"] += b["hi"]
            if b["area"]:
                a["area"] += b["area"]
                a["vac_area"] += (1 - b["hi"] / b["cap"]) * b["area"]
            h["n"] += 1
            h["cap"] += b["cap"]
            h["hi"] += b["hi"]
            for f in b["floors"]:
                by_floor[k][min(f, 6)][1] += 1
                by_floor[k][min(f, 6)][0] += f in b["known"]
        per_hub.append((slug, anchors.get(slug) or 0, hub))

    print("\n[표 1] 분모 층수 구간별 (13거점 합, 중대형 대조 모집단)")
    print(f"{'구간':8s} {'건물':>6s} {'분모층':>7s} {'공실 상한':>9s} {'공실 하한':>9s} {'면적기준':>9s}")
    for _lo, _hi, k in BUCKETS:
        a = agg[k]
        if not a["cap"]:
            continue
        print(f"{k:8s} {a['n']:6d} {a['cap']:7d} "
              f"{(1 - a['hi'] / a['cap']) * 100:8.1f}% {(1 - a['lo'] / a['cap']) * 100:8.1f}% "
              f"{(a['vac_area'] / a['area'] * 100 if a['area'] else 0):8.1f}%")

    print("\n[표 2] 층 번호별 점유율 하한(점포 flrNo + 인허가 층 확인분) — 구간별")
    print(f"{'구간':8s} " + " ".join(f"{('6층+' if i == 6 else str(i) + '층'):>7s}" for i in range(1, 7)))
    for _lo, _hi, k in BUCKETS:
        if not by_floor[k]:
            continue
        cells = []
        for i in range(1, 7):
            o, n = by_floor[k][i]
            cells.append(f"{(o / n * 100 if n else 0):6.1f}%")
        print(f"{k:8s} " + " ".join(cells))

    print("\n[거점별 구간 공실률(상한)]")
    print(f"{'거점':16s} {'앵커':>5s} " + " ".join(f"{k:>12s}" for _l, _h, k in BUCKETS))
    for slug, anchor, hub in per_hub:
        cells = []
        for _l, _h, k in BUCKETS:
            h = hub[k]
            cells.append(f"{(1 - h['hi'] / h['cap']) * 100:5.1f}%({h['n']:4d})" if h["cap"]
                         else f"{'-':>11s}")
        print(f"{slug:16s} {anchor:5.1f} " + " ".join(cells))

    print("\n[표 3] 인허가(영업/정상) 주소의 층 표기 — 상층부를 덮을 독립 소스")
    tot = hit = 0
    grnd: dict[int, int] = defaultdict(int)
    for slug in slugs:
        ps = sorted((BRONZE / slug).glob("*/licensing_biz.json"))
        if not ps:
            continue
        rows = json.loads(ps[-1].read_text(encoding="utf-8"))
        op = [r for r in rows if r.get("TRDSTATENM") == "영업/정상"]
        n_hit = 0
        for r in op:
            fl, found = lic_floors(f"{r.get('SITEWHLADDR', '')} {r.get('RDNWHLADDR', '')}")
            n_hit += found
            for f in fl:
                grnd[min(f, 6)] += 1
        tot += len(op)
        hit += n_hit
        print(f"{slug:16s} 영업중 {len(op):6d} · 층 표기 {n_hit:6d} ({n_hit / len(op) * 100:5.1f}%)")
    if tot:
        print(f"{'합계':16s} 영업중 {tot:6d} · 층 표기 {hit:6d} ({hit / tot * 100:5.1f}%)")
        s = sum(grnd.values())
        print("  지상 층 분포: " + " · ".join(
            f"{('6층+' if k == 6 else str(k) + '층')} {grnd[k] / s * 100:.1f}%" for k in sorted(grnd)))


if __name__ == "__main__":
    main()
