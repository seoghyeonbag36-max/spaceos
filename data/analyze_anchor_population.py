"""[Page] 앵커 모집단 불일치 진단 — 우리 공실률을 R-ONE 모집단·단위에 맞춰 재집계.

2026-08-01. 13거점 건물 공실률이 R-ONE 앵커보다 계통적으로 +7~+63%p 높은 원인을
좁히기 위한 진단기다. **산출물을 바꾸지 않는다**(gold 무수정, API 콜 0).

R-ONE 상업용부동산 임대동향조사(공식 정의, reb.or.kr):
  · 공실률 = 표본 공실면적 합 ÷ 표본 총 임대가능면적      ← **면적** 기준
  · 중대형 상가 = 3층 이상 또는 연면적 330㎡ 초과 (일반건축물)
  · 소규모 상가 = 2층 이하이고 연면적 330㎡ 이하 (일반건축물)
  · 집합 상가  = 집합건축물 (**별도 계열** — 중대형 앵커에 안 들어간다)
  · 표본 = 전국 일반 12,111동(중대형 5,761 / 소규모 5,526 / 오피스 824) + 집합 29,500호
우리 지표 = **호실(층)** 기준, 모집단 = 반경 내 상업 호실이 있는 모든 건물(집합 포함).

표 1) 모집단 정렬 변형
  A 현행     primary(expos_units+floor_ouln) 전체
  B 규모정렬 일반건축물 & (3층 이상 or 연면적>330㎡)
  C 용도정렬 B + 표제부 주용도가 상가류(근생·판매·위락·문화)  ← R-ONE 중대형 표본조건
  D 면적가중 C 를 건물 상업면적으로 가중                      ← R-ONE 면적 기준 근사
  E 소규모   일반건축물 & 2층 이하 & ≤330㎡ & 상가류          ← vac_small 대조

표 2) 층 단위 점유 — 상가정보 flrNo 와 층별개요 층번호를 직접 맞춘다.
  현행 지표는 분자(건물 내 점포 수, 층 무관)와 분모(지상 상업층 수)의 단위가 달라
  min() 클램프로 덮고 있다. 층으로 맞추면 상·하한이 나온다(flrNo 공란 ~30%).
    하한 = 층이 확인된 점포만 인정
    상한 = 층 미상 점포를 빈 상업층에 낮은 층부터 배정

건물 속성(층수·연면적·주용도·상업층 번호·점포 층)은 pipelines/build_building_attrs 가
silver/{거점}/building_attrs.json 에 만들어 둔 사이드카를 읽는다.

⚠ 이 진단기의 표 1(A~E)은 **분자를 점포 수로 세던 시절의 정의**다. 2026-08-01 층 단위
매칭 전환 이후 gold 의 capacity 는 넓어졌고 분자는 층으로 바뀌었으므로, 지금 돌리면
분자(점포 수)와 분모(층)가 섞인 값이 나온다. 전환 이후의 정식 지표는
`gold/{거점}/calibration.json` 의 **rone_aligned** 다. 이 파일은 전환 근거를 남긴
기록으로 유지한다.

실행: python -m data.analyze_anchor_population [거점 ...] [--rebuild]
      (--rebuild 는 bronze 에서 사이드카를 다시 만든다. 거점당 수십 초)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

from data.collectors.common import GOLD
from data.config.page_hubs import HUBS
from data.pipelines.build_building_attrs import load as load_attrs
from data.pipelines.build_building_attrs import run as build_attrs
from data.pipelines.calibrate_vacancy import _rone_latest

# 건축물대장 산출물(building_vacancy.json)이 있는 거점만 이 진단의 대상이다.
PRIMARY = {"expos_units", "floor_ouln"}
# 상가 주용도 판정은 사이드카(build_building_attrs.SHOP_PURPS)가 is_shop 으로 넣어 준다.


def ledger_hubs() -> list[str]:
    """HUBS 순서대로 건축물대장 산출물이 있는 거점을 반환."""
    return [slug for slug in HUBS if (GOLD / slug / "building_vacancy.json").exists()]


def load_cache(slug: str, rebuild: bool = False) -> dict:
    """건물 속성 사이드카 — 없거나 --rebuild 면 bronze 에서 다시 만든다."""
    if rebuild or not load_attrs(slug):
        build_attrs(slug)
    return load_attrs(slug)


# ── 건물 단위 집계 ─────────────────────────────────────────────────────

def buildings(slug: str, cache: dict) -> dict[str, dict]:
    """pnu 단위 dedupe — capacity 는 지번당 1회, active 는 같은 지번의 동을 합산.

    ⚠ 지번 dedupe 없이 feature/bdMgtSn 단위로 세면 분모가 과대 계산된다.
    """
    rows = json.loads((GOLD / slug / "building_vacancy.json").read_text(encoding="utf-8"))
    per: dict[str, dict] = {}
    for r in rows:
        if r.get("capacity_method") not in PRIMARY or not r.get("capacity"):
            continue
        at = cache.get(r["lnoCd"], {})
        d = per.setdefault(r["lnoCd"], {
            "cap": r["capacity"], "act": 0, "method": r["capacity_method"],
            "mall": r["capacity_method"] == "expos_units" or bool(at.get("is_mall")),
            "big": at.get("rone_size") == "mid",
            "small": at.get("rone_size") == "small",
            "shop": bool(at.get("is_shop")),
            "known": at.get("rone_size") is not None,
            "area": at.get("com_area_flr") or at.get("com_area") or 0.0,
            "floors": at.get("com_flr_nos") or [],
            "store_floors": set(at.get("store_flr_nos") or []),
            "store_unknown": at.get("store_flr_unknown") or 0,
        })
        d["act"] += r.get("active", 0)
    return per


def _rate(units: list[tuple[int, int]]) -> tuple[float, int]:
    """건물별 min(active, capacity) 클램프 후 합산 공실률(%).

    ⚠ 클램프 없이 sum(active)/sum(capacity) 로 하면 active>capacity 인 건물(거점당
    34~45%)의 초과분이 다른 건물의 공실을 상쇄해 공실률이 0% 로 눌린다.
    """
    act = sum(min(a, c) for a, c in units)
    cap = sum(c for _, c in units)
    return ((1 - act / cap) * 100 if cap else 0.0), len(units)


def _wrate(items: list[tuple[int, int, float]]) -> tuple[float, int]:
    """면적 가중 — Σ(건물 공실률 × 상업면적) ÷ Σ상업면적."""
    num = den = 0.0
    n = 0
    for a, c, ar in items:
        if not ar:
            continue
        num += (1 - min(a, c) / c) * ar
        den += ar
        n += 1
    return ((num / den * 100) if den else 0.0), n


# ── 표 2: 층 단위 점유 ─────────────────────────────────────────────────

def floor_view(per: dict[str, dict]) -> dict:
    """C 모집단의 층 단위 점유 — 하한/상한/층별 점유율/분모 밖 점포."""
    lo = hi = tot = 0
    out_cnt = out_all = 0
    by_lo: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    by_hi: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for d in per.values():
        if d["mall"] or not d["shop"] or not d["big"] or not d["floors"]:
            continue
        have = d["store_floors"]
        floors = d["floors"]
        occ = {f for f in floors if f in have}
        for f in have:                       # 분모 밖 층에 있는 점포(= 상업층 필터 누락 신호)
            out_all += 1
            out_cnt += f not in floors
        spare = d["store_unknown"]
        occ_hi = set(occ)
        for f in sorted(floors):             # 층 미상 점포를 낮은 층부터 빈 층에 배정
            if spare <= 0:
                break
            if f not in occ_hi:
                occ_hi.add(f)
                spare -= 1
        for f in floors:
            k = min(f, 5)
            by_lo[k][1] += 1
            by_hi[k][1] += 1
            by_lo[k][0] += f in occ
            by_hi[k][0] += f in occ_hi
        lo += len(occ)
        hi += len(occ_hi)
        tot += len(floors)
    return {"lo": lo, "hi": hi, "floors": tot, "by_lo": by_lo, "by_hi": by_hi,
            "out_of_denom": out_cnt, "stores_with_floor": out_all}


# ── 출력 ──────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    rebuild = "--rebuild" in args
    slugs = [a for a in args if not a.startswith("-")] or ledger_hubs()
    if not slugs:
        print("[anchor-diag] building_vacancy.json 없음 — data.collectors.building_vacancy 수집 먼저")
        return
    mid_a, small_a = _rone_latest("vac_mid"), _rone_latest("vac_small")

    agg: dict[str, list] = defaultdict(list)
    fl_tot = {"lo": 0, "hi": 0, "floors": 0, "out_of_denom": 0, "stores_with_floor": 0}
    fl_by = {"lo": defaultdict(lambda: [0, 0]), "hi": defaultdict(lambda: [0, 0])}
    rows_out: list[tuple] = []

    for slug in slugs:
        cache = load_cache(slug, rebuild)
        per = buildings(slug, cache)
        A = [(d["act"], d["cap"]) for d in per.values()]
        B = [(d["act"], d["cap"]) for d in per.values() if not d["mall"] and d["big"] and d["known"]]
        C = [(d["act"], d["cap"]) for d in per.values() if not d["mall"] and d["big"] and d["shop"]]
        D = [(d["act"], d["cap"], d["area"]) for d in per.values()
             if not d["mall"] and d["big"] and d["shop"]]
        E = [(d["act"], d["cap"]) for d in per.values() if not d["mall"] and d["small"] and d["shop"]]
        M = [(d["act"], d["cap"]) for d in per.values() if d["mall"]]
        for k, v in (("A", A), ("B", B), ("C", C), ("E", E), ("M", M)):
            agg[k] += v
        agg["D"] += D
        fv = floor_view(per)
        for k in ("lo", "hi", "floors", "out_of_denom", "stores_with_floor"):
            fl_tot[k] += fv[k]
        for side in ("lo", "hi"):
            for k, v in fv[f"by_{side}"].items():
                fl_by[side][k][0] += v[0]
                fl_by[side][k][1] += v[1]
        rows_out.append((slug, mid_a.get(slug) or 0, small_a.get(slug) or 0, A, B, C, D, E, M, fv))

    print("\n[표 1] 모집단 정렬 — 호실(층) 기준 공실률, 괄호는 건물 수")
    print(f"{'거점':16s} {'앵커중':>6s} {'앵커소':>6s} | {'A현행':>13s} {'B규모':>13s} "
          f"{'C용도':>13s} {'D면적가중':>13s} | {'E소규모':>13s} {'집합(참고)':>13s}")
    for slug, am, asm, A, B, C, D, E, M, _fv in rows_out:
        cells = [f"{v:5.1f}%({n:4d})" for v, n in (_rate(A), _rate(B), _rate(C))]
        cells.append("{:5.1f}%({:4d})".format(*_wrate(D)))
        cells += [f"{v:5.1f}%({n:4d})" for v, n in (_rate(E), _rate(M))]
        print(f"{slug:16s} {am:6.1f} {asm:6.1f} | {cells[0]} {cells[1]} {cells[2]} {cells[3]} "
              f"| {cells[4]} {cells[5]}")
    tot_cells = [f"{v:5.1f}%({n:5d})" for v, n in
                 (_rate(agg["A"]), _rate(agg["B"]), _rate(agg["C"]))]
    tot_cells.append("{:5.1f}%({:5d})".format(*_wrate(agg["D"])))
    tot_cells += [f"{v:5.1f}%({n:5d})" for v, n in (_rate(agg["E"]), _rate(agg["M"]))]
    print(f"{'합계':16s} {'':6s} {'':6s} | {tot_cells[0]} {tot_cells[1]} {tot_cells[2]} "
          f"{tot_cells[3]} | {tot_cells[4]} {tot_cells[5]}")

    print("\n[표 2] 층 단위 점유 (C 모집단) — 상가정보 flrNo × 층별개요 층번호")
    print(f"{'거점':16s} {'상업층':>6s} | {'현행':>6s} {'층하한':>6s} {'층상한':>6s} | "
          f"{'1층하한':>7s} {'1층상한':>7s} | {'분모밖점포':>9s}")
    for slug, _am, _asm, _A, _B, C, _D, _E, _M, fv in rows_out:
        cur, _ = _rate(C)
        lo = (1 - fv["lo"] / fv["floors"]) * 100 if fv["floors"] else 0
        hi = (1 - fv["hi"] / fv["floors"]) * 100 if fv["floors"] else 0
        oo = fv["out_of_denom"] / fv["stores_with_floor"] * 100 if fv["stores_with_floor"] else 0
        f1l, f1h = fv["by_lo"][1], fv["by_hi"][1]     # 1층만 — 가두 실태조사 대조용
        v1l = (1 - f1l[0] / f1l[1]) * 100 if f1l[1] else 0
        v1h = (1 - f1h[0] / f1h[1]) * 100 if f1h[1] else 0
        print(f"{slug:16s} {fv['floors']:6d} | {cur:5.1f}% {lo:5.1f}% {hi:5.1f}% | "
              f"{v1l:6.1f}% {v1h:6.1f}% | {oo:8.1f}%")
    f = fl_tot
    print(f"\n합계 층 기준 공실률: 하한 {(1 - f['lo'] / f['floors']) * 100:.1f}% · "
          f"상한 {(1 - f['hi'] / f['floors']) * 100:.1f}%  (상업층 {f['floors']}개)")
    for side, lbl in (("lo", "하한"), ("hi", "상한")):
        d = fl_by[side]
        print(f"층별 점유율 {lbl}: " + " · ".join(
            f"{('5층+' if k == 5 else str(k) + '층')} {d[k][0] / d[k][1] * 100:.1f}%"
            for k in sorted(d)))
    print(f"분모 밖 층에 있는 점포: {f['out_of_denom'] / f['stores_with_floor'] * 100:.1f}% "
          f"({f['out_of_denom']}/{f['stores_with_floor']})")


if __name__ == "__main__":
    main()
