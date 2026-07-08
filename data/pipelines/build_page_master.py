"""Gold 빌더 — page_building_master.geojson (Page 공실 레이어의 단일 소스).

결합: V-World 건물 폴리곤(bronze bldg_polygons.geojson, key=pnu 19자리)
  ⊕ 건물 공실 지표(gold building_vacancy.json, key=lnoCd 19자리 — PNU 동형)

규칙:
  - 폴리곤 pnu == 공실 lnoCd 매칭. 같은 지번 여러 공실행은 active·capacity 합산 후 재분류.
  - 미매칭 폴리곤 중 '상업용도'(용도코드 03/04/05/07/14/15/16)는 활성 점포 0
    → status "empty"(공실 의심). 주거·기타 용도는 지도에서 제외.
  - status 는 프론트(MapShell VacStatus) 규격 4종만 출력: full/partial/high/empty.
    unknown(대장 미확인)·n_a(비상업)는 제외하고 카운트만 보고.

산출: gold/{SLUG}/page_building_master.geojson
  properties: id/name/status/capacity/active/industry/vacancy_rate (+floors/height)
  → apps/backend/app/services/building_vacancy.py 가 이 파일을 서빙.

실행: python -m data.pipelines.build_page_master
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from data.collectors.common import GOLD, load_latest
from data.config.garosugil import SLUG

# 건물통합 용도코드(대분류 5자리) 중 상가 capacity 를 가질 수 있는 상업 계열
_COMMERCIAL_PRPS = ("03", "04", "05", "07", "14", "15", "16")
_STORES_PER_FLOOR = 2      # collectors/building_vacancy.py 와 동일 근사

_DONG = {"10700": "신사동", "10800": "압구정동", "11000": "논현동", "10600": "잠원동"}


def _label(pnu: str, name: str) -> str:
    if name:
        return name
    dong = _DONG.get(pnu[5:10], pnu[5:10])
    return f"{dong} {int(pnu[11:15])}-{int(pnu[15:19])}"


def _classify(occ: float | None) -> str | None:
    if occ is None:
        return None
    if occ >= 0.9:
        return "full"
    if occ >= 0.5:
        return "partial"
    if occ > 0:
        return "high"
    return "empty"


def _aggregate(rows: list[dict]) -> dict:
    """같은 지번(lnoCd)의 공실행 합산 — active 합, capacity 합(미확인 제외)."""
    active = sum(r["active"] for r in rows)
    caps = [r["capacity"] for r in rows if r.get("capacity")]
    # capacity 하한 = active (근사 과소추정 시 음수 공실률 방지 — 프론트 vacRate 클램프 겸용)
    cap = max(sum(caps), active) if caps else None
    occ = min(active / cap, 1.0) if cap else None
    top = max(rows, key=lambda r: r["active"])
    return {
        "name": next((r["name"] for r in rows if r.get("name")), ""),
        "active": active, "capacity": cap,
        "industry": top.get("industry", ""),
        "occupancy": occ,
    }


def run() -> None:
    polys = load_latest(SLUG, "bldg_polygons.geojson")
    vac_path = GOLD / SLUG / "building_vacancy.json"
    if not polys or not vac_path.exists():
        print("[page-master] 입력 없음 — vworld_bldg / building_vacancy 수집 먼저")
        return
    vac = json.loads(vac_path.read_text(encoding="utf-8"))

    by_lno: dict[str, list[dict]] = defaultdict(list)
    for r in vac:
        if r.get("lnoCd"):
            by_lno[r["lnoCd"]].append(r)

    feats: list[dict] = []
    stats: Counter = Counter()
    seen_pnu: Counter = Counter()
    for f in polys["features"]:
        p = f["properties"]
        pnu = p.get("pnu", "")
        if len(pnu) != 19:
            stats["bad_pnu"] += 1
            continue
        floors = int(p.get("ground_floor_co") or 0)

        if pnu in by_lno:
            agg = _aggregate(by_lno[pnu])
            status = _classify(agg["occupancy"])
            if status is None:                    # capacity 미확인 → 지도 제외
                stats["excluded_unknown"] += 1
                continue
            props = {
                "name": _label(pnu, agg["name"]),
                "status": status,
                "capacity": agg["capacity"], "active": agg["active"],
                "industry": agg["industry"],
                "vacancy_rate": round((1 - min(agg["active"] / agg["capacity"], 1.0)) * 100, 1),
                "source": "stores+ledger",
            }
        else:
            # 활성 점포 0 — 상업용도 건물만 '공실 의심'으로 표시
            if not str(p.get("buld_prpos_code", ""))[:2] in _COMMERCIAL_PRPS:
                stats["excluded_non_commercial"] += 1
                continue
            props = {
                "name": _label(pnu, ""),
                "status": "empty",
                "capacity": max(floors * _STORES_PER_FLOOR, 1), "active": 0,
                "industry": "",
                "vacancy_rate": 100.0,
                "source": "polygon_only",         # TODO: 대장 재확인으로 승격
            }

        seen_pnu[pnu] += 1
        props.update({
            "id": f"{pnu}-{seen_pnu[pnu]}",
            "pnu": pnu,
            "floors": floors,
            "height": float(p.get("hg") or 0),
        })
        stats[props["status"]] += 1
        feats.append({"type": "Feature", "geometry": f["geometry"], "properties": props})

    out = {"type": "FeatureCollection", "district": "gangnam-garosugil", "features": feats}
    dst = GOLD / SLUG / "page_building_master.geojson"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    known = [f for f in feats if f["properties"]["source"] == "stores+ledger"]
    act = sum(f["properties"]["active"] for f in known)
    cap = sum(f["properties"]["capacity"] for f in known)
    print(f"[gold] page_building_master.geojson: {len(feats)}동")
    print(f"[page-master] status: " + ", ".join(f"{k}={stats[k]}" for k in ("full", "partial", "high", "empty")))
    print(f"[page-master] 제외: unknown={stats['excluded_unknown']}, 비상업={stats['excluded_non_commercial']}")
    if cap:
        print(f"[page-master] 매칭건물 집계 공실률(참고): {round((1 - act / cap) * 100, 1)}% (부동산원 가두 41.6% 와 비교용)")


if __name__ == "__main__":
    run()
