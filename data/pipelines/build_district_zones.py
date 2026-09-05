"""[Platform] 행정동 단위 **실측** 구역 — gold/{slug}/district_zones.json.

## 무엇을 대체하나 (2026-09-05)

`app/data/seoul_pages.py` 의 `zones` 는 **손으로 적은 값**이었다 —
`z("z1", "가로수길 메인로", ..., 76.8, 1.9, 2140, [["플래그십 방문", "+41%", "up"], ...])`.
감성 76.8 · 리뷰 2,140건 · "+41%" 에 근거가 없다. 54거점 × 6구역 = **324개**가 그랬고,
2차 12거점에는 아예 없어 화면이 "이 거점의 감성 구역이 없다"를 냈다.

여기서 그 자리를 **행정동 실측 구역**으로 바꾼다. 66거점이 같은 규칙 위에 선다.

## 감성은 채우지 않는다 — 못 채우는 것이다

`s`(감성) · `d`(증감) · `r`(리뷰수) · `f`(키워드)는 **null 로 나간다.** 빈 것이 정상이고
그 사실이 화면에 실린다(`measured_pages` 머리말과 같은 원칙).

2026-08-25 에 블로그 원문 16,605건을 재고 세 다리가 모두 끊긴 것을 확인했다
(docs/feature-platform.md §0-K):

    ① 구조 — 블로그 레코드의 공간 키는 `_query`(거점명) 하나뿐이다. 좌표·주소가 없어
             **구역 단위로 내려올 수가 없다.**
    ② 귀속 — 점포명 매칭은 노드 3.18% 에만 붙고, 붙는 것은 블로그에 오르는 유명
             점포라 예측 대상인 **공실에는 원리적으로 없다.**
    ③ 신호 — 부정어 0.53% · 점수 +1.0 이 98.3% · 거점간/거점내 분산비 0.101.
             6구역으로 갈라도 전부 같은 점수가 나온다.

⚠ **Gold 활력 지표(`opbiz_rt`·`flpop` 등)를 `s` 에 넣어 감성으로 부르지 말 것.**
AGENTS.md 가 금지한다 — 그건 측정이 아니라 이름 바꾸기다. 감성을 채우려면 좌표를
가진 점포 단위 리뷰가 필요하고, 그 채널은 아직 없다.

## 왜 행정동인가

거점당 **4~7개**가 나와 시드가 쓰던 6구역과 입도가 같은데, 임의 클러스터(k-means)와
달리 **공식 경계**라 이름·경계가 재현 가능하다. 점포(소상공인 상가정보)가
`adongNm`·`ldongNm` 을 들고 있어 별도 수집이 필요 없다.

## 건물을 구역에 붙이는 법 — PNU 조인이 아니라 kNN 이다

건물(`page_building_master`)에는 행정동이 없다. 점포의 `lnoCd`(=건물 `pnu`)로 조인하면
**79.3%** 만 붙는데, **빠지는 21% 는 점포가 없는 건물** — 즉 공실 쪽에 몰린다.
그걸로 구역 공실률을 내면 구조적으로 과소추정된다.

그래서 건물 중심점에서 **가장 가까운 점포 9개의 다수결**로 배정한다(100% 커버).
PNU 조인이 가능한 5,732동에서 두 방법을 대조해 **99.2% 일치**를 확인했다
(2026-09-05, 2차 12거점 기준). 배정 결과에는 그 일치율을 실어 둔다.

## 공실률은 거점 대표값과 **같은 규칙**으로 센다

규칙이 갈라지면 구역 합계와 거점 대표값이 서로 다른 말을 한다. `gold_vacancy.build_cells`
와 같은 넷을 적용한다 — 집합건물(`expos_units`) 제외 · `floor_ouln` 분모만 ·
`polygon_only` 소스 제외 · **지번(pnu) 중복 제거**. `active` 는 `capacity` 로 클램프한다.

`data/tests/test_district_zones.py` 가 구역 합계 == 거점 대표 분모/분자를 고정한다.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "config"))

from page_hubs import ACTIVE_HUBS  # noqa: E402

GOLD = ROOT / "data" / "gold"
BRONZE = ROOT / "data" / "bronze"

# gold_vacancy 와 같은 규칙 — 갈라지면 구역 합계가 거점 대표값과 어긋난다.
_COUNTED_METHODS = {"floor_ouln"}
_EXCLUDED_SOURCES = {"polygon_only"}

# 이웃 표본 수. 9 는 2026-09-05 에 PNU 조인과 99.2% 일치를 확인한 값이다.
KNN_K = 9

# 구역 최소 규모. 이보다 작은 행정동은 **거점 경계에 걸친 스필오버**라 구역으로 세지
# 않는다(예: doksan 의 하안3동 5점포·하안4동 3점포). 버린 것은 산출물 meta 에 남긴다.
MIN_COUNTED_BUILDINGS = 5


def _latest(pattern: str) -> str | None:
    hits = sorted(glob.glob(pattern))
    return hits[-1] if hits else None


def _ring_centroid(ring: list[list[float]]) -> tuple[float, float]:
    """폴리곤 외곽 링([lng, lat])의 정점 평균 → (lat, lng). gold_vacancy._centroid 와 같다."""
    pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    return sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)


def _load_stores(slug: str) -> list[dict]:
    path = _latest(str(BRONZE / slug / "*" / "stores_raw.json"))
    if not path:
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _counted(props: dict) -> bool:
    """대표 집계에 드는 건물인가 — gold_vacancy.build_cells 와 같은 판정."""
    if props.get("capacity_method") == "expos_units":
        return False
    if (props.get("capacity") or 0) <= 0:
        return False
    if props.get("capacity_method") not in _COUNTED_METHODS:
        return False
    if props.get("source") in _EXCLUDED_SOURCES:
        return False
    return True


def build(slug: str) -> dict | None:
    """거점 하나의 행정동 실측 구역. 재료가 없으면 None."""
    master_path = GOLD / slug / "page_building_master.geojson"
    if not master_path.exists():
        return None
    stores = _load_stores(slug)
    if not stores:
        return None

    from scipy.spatial import cKDTree  # 지연 임포트 — 서빙에는 안 실린다

    pts: list[tuple[float, float]] = []
    labels: list[tuple[str, str]] = []      # (행정동, 법정동)
    pnu_dong: dict[str, str] = {}           # 대조용 — kNN 검증에만 쓴다
    for row in stores:
        try:
            lon, lat = float(row["lon"]), float(row["lat"])
        except (KeyError, TypeError, ValueError):
            continue
        adong = (row.get("adongNm") or "").strip()
        if not adong:
            continue
        pts.append((lon, lat))
        labels.append((adong, (row.get("ldongNm") or "").strip()))
        if row.get("lnoCd"):
            pnu_dong.setdefault(row["lnoCd"], adong)
    if not pts:
        return None
    tree = cKDTree(pts)

    with open(master_path, encoding="utf-8") as fh:
        fc = json.load(fh)

    agg: dict[str, dict] = defaultdict(
        lambda: {"cap": 0, "act": 0, "n": 0, "lat": 0.0, "lng": 0.0, "ldong": Counter()}
    )
    seen_lots: set[str] = set()
    agree = compared = 0

    for feat in fc.get("features", []):
        props = feat.get("properties") or {}
        if not _counted(props):
            continue
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Polygon" or not geom.get("coordinates"):
            continue
        # 같은 지번의 두 번째 폴리곤부터는 건너뛴다 — 각 폴리곤이 지번 전체의
        # capacity·active 를 물려받으므로 그대로 더하면 폴리곤 수만큼 가중된다.
        lot = props.get("pnu") or props.get("id")
        if lot in seen_lots:
            continue
        seen_lots.add(lot)

        lat, lng = _ring_centroid(geom["coordinates"][0])
        _, idx = tree.query([lng, lat], k=min(KNN_K, len(pts)))
        neigh = [labels[i] for i in (idx if hasattr(idx, "__iter__") else [idx])]
        adong = Counter(a for a, _ in neigh).most_common(1)[0][0]

        truth = pnu_dong.get(props.get("pnu") or "")
        if truth:
            compared += 1
            agree += truth == adong

        cap = props["capacity"]
        z = agg[adong]
        z["cap"] += cap
        z["act"] += min(props.get("active") or 0, cap)
        z["n"] += 1
        z["lat"] += lat
        z["lng"] += lng
        for a, ld in neigh:
            if a == adong and ld:
                z["ldong"][ld] += 1

    if not agg:
        return None

    store_n = Counter(a for a, _ in labels)
    kept: list[dict] = []
    dropped: list[dict] = []
    for adong, z in sorted(agg.items(), key=lambda kv: -kv[1]["cap"]):
        row = {
            "n": adong,
            "grp": z["ldong"].most_common(1)[0][0] if z["ldong"] else adong,
            "lat": round(z["lat"] / z["n"], 6),
            "lng": round(z["lng"] / z["n"], 6),
            "stores": store_n.get(adong, 0),
            "buildings": z["n"],
            "capacity": z["cap"],
            "active": z["act"],
            "vacancy_rate": round((z["cap"] - z["act"]) / z["cap"] * 100, 2),
            # 감성은 못 잰다 — 모듈 머리말 참조. 0 이 아니라 null 이다.
            "s": None, "d": None, "r": None, "f": [],
        }
        (kept if z["n"] >= MIN_COUNTED_BUILDINGS else dropped).append(row)

    for i, row in enumerate(kept, 1):
        row["id"] = f"z{i}"

    return {
        "slug": slug,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "소상공인 상가정보 행정동(adongNm) × gold/page_building_master",
        "method": f"adong_knn{KNN_K}",
        "note": (
            "건물→행정동 배정은 가장 가까운 점포 9개의 다수결이다. PNU 조인은 79.3% 만 "
            "붙고 빠지는 쪽이 공실에 몰려 과소추정을 낳는다. 공실률은 gold_vacancy 와 "
            "같은 규칙(집합건물 제외·floor_ouln 분모·polygon_only 제외·지번 중복 제거). "
            "감성(s/d/r/f)은 좌표를 가진 점포 리뷰 채널이 없어 null 이다 — feature-platform §0-K."
        ),
        "assign": {
            "counted_buildings": sum(z["n"] for z in agg.values()),
            "knn_vs_pnu_compared": compared,
            "knn_vs_pnu_agree_pct": round(agree / compared * 100, 1) if compared else None,
        },
        # 스필오버로 뺀 행정동. **분모를 그냥 버리면 구역 합계가 거점 대표값과 어긋난다** —
        # 그 차이를 여기 남겨 `sum(zones) + residual == 거점 분모/분자` 가 성립하게 한다.
        # 이 항등식은 data/tests/test_district_zones.py 가 66거점 전부에서 고정한다.
        "dropped_spillover": [
            {"n": r["n"], "buildings": r["buildings"], "stores": r["stores"],
             "capacity": r["capacity"], "active": r["active"]} for r in dropped
        ],
        "residual": {
            "buildings": sum(r["buildings"] for r in dropped),
            "capacity": sum(r["capacity"] for r in dropped),
            "active": sum(r["active"] for r in dropped),
        },
        "zones": kept,
    }


def main(argv: list[str]) -> int:
    slugs = [a for a in argv if not a.startswith("-")] or list(ACTIVE_HUBS)
    dry = "--dry-run" in argv
    total_zones = total_dropped = 0
    ok = 0
    for slug in slugs:
        out = build(slug)
        if out is None:
            print(f"[zones] {slug:16} 재료 없음 — 건너뜀")
            continue
        ok += 1
        total_zones += len(out["zones"])
        total_dropped += len(out["dropped_spillover"])
        agree = out["assign"]["knn_vs_pnu_agree_pct"]
        names = " · ".join(f"{z['n']}({z['buildings']}동 {z['vacancy_rate']}%)" for z in out["zones"])
        print(f"[zones] {slug:16} 구역 {len(out['zones'])} · 배정일치 {agree}% · {names}")
        if out["dropped_spillover"]:
            print(f"         스필오버 제외: "
                  + ", ".join(f"{d['n']}({d['buildings']}동)" for d in out["dropped_spillover"]))
        if not dry:
            path = GOLD / slug / "district_zones.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"\n[zones] 거점 {ok}/{len(slugs)} · 구역 {total_zones}개 "
          f"(거점당 {total_zones / ok:.1f}) · 스필오버 제외 {total_dropped}개"
          + ("  [dry-run — 저장 안 함]" if dry else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
