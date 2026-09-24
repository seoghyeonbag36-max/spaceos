#!/usr/bin/env python
"""거점 → 서울 상권분석 상권코드 매핑 **후보**를 낸다 (`DISTRICT_TRDAR` 작성 보조).

## 왜 필요한가

`data/config/platform_districts.DISTRICT_TRDAR` 는 손으로 쓴 설정인데, 보조 도구가
없어서 거점을 늘릴 때 **조용히 빠진다**. 2026-09-24 에 서울 3·4차 15거점이 그랬다:
`DISTRICT_RONE` 은 09-20 에 채웠는데 `DISTRICT_TRDAR` 은 안 채워, 수집기가
"전체 1,648행 중 거점 245행"으로 거르고 `build_trdar_demand` 가 exit=0 인 채
**66거점**을 냈다. 에러가 아니라 그냥 빠진다 → docs/finding-anchor-fallback-2026-09-24.md

## 무엇을 하나

1. `TbgisTrdarRelm`(상권영역 마스터)을 **필터 없이 전량** 받는다(~1,650행).
   수집기는 같은 응답을 받아 `TRDAR_TO_DISTRICT` 로 걸러 버리므로 미매핑 거점은
   후보조차 볼 수 없다 — 그래서 여기서 다시 받는다.
2. 좌표(EPSG:5181 TM)를 WGS84 로 바꿔 거점 중심과의 거리를 잰다.
3. 거점 반경 안에 들어오는 상권을 **거리순**으로 낸다.

**채택은 사람이 한다.** 이 스크립트는 고르지 않는다 — 거리·면적·유형·자치구를
같이 찍어 판단 재료만 준다. 기존 매핑이 거점당 1~6개로 제각각인 것은 상권 경계가
거점 반경과 1:1 이 아니기 때문이고, 그 판단을 자동화하지 않는다.

실행:
  python scripts/propose_trdar_mapping.py <slug ...> [--radius-m 700] [--out <경로>]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.collectors.common import load_env  # noqa: E402
from data.collectors.seoul_trdar import _PAGE, _fetch_page  # noqa: E402
from data.config.page_hubs import get_hub  # noqa: E402
from data.config.platform_districts import DISTRICT_TRDAR, TRDAR_TO_DISTRICT  # noqa: E402

_SERVICE = "TbgisTrdarRelm"
_SE_LABEL = {"A": "골목상권", "D": "발달상권", "R": "전통시장", "U": "관광특구"}


def _fetch_all_relm(key: str) -> list[dict]:
    rows: list[dict] = []
    start = 1
    while True:
        page, total = _fetch_page(key, _SERVICE, start, start + _PAGE - 1)
        rows.extend(page)
        start += _PAGE
        if not page or start > total:
            break
    return rows


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="+", help="후보를 낼 거점 slug")
    ap.add_argument("--radius-m", type=int, default=None,
                    help="반경(기본: 거점의 stores_radius_m)")
    ap.add_argument("--out", default="reports/trdar_mapping_candidates.json")
    args = ap.parse_args()

    load_env()
    key = os.getenv("SEOUL_OPENAPI_KEY")
    if not key:
        print("SEOUL_OPENAPI_KEY 미설정 (data/.env)", file=sys.stderr)
        return 2

    from pyproj import Transformer
    tm = Transformer.from_crs("EPSG:5181", "EPSG:4326", always_xy=True)

    raw = _fetch_all_relm(key)
    print(f"[relm] 전량 {len(raw)}행 · 기존 매핑 {len(TRDAR_TO_DISTRICT)}코드 / {len(DISTRICT_TRDAR)}거점")

    cat = []
    for r in raw:
        try:
            lon, lat = tm.transform(float(r["XCNTS_VALUE"]), float(r["YDNTS_VALUE"]))
        except (KeyError, TypeError, ValueError):
            continue
        code = str(r.get("TRDAR_CD", ""))
        cat.append({
            "code": code, "name": r.get("TRDAR_CD_NM", ""),
            "se": _SE_LABEL.get(str(r.get("TRDAR_SE_CD", "")), r.get("TRDAR_SE_CD_NM", "")),
            "gu": r.get("SIGNGU_CD_NM", ""), "dong": r.get("ADSTRD_CD_NM", ""),
            "area_m2": float(r.get("RELM_AR") or 0),
            "lat": lat, "lon": lon,
            "taken_by": TRDAR_TO_DISTRICT.get(code),   # 이미 다른 거점이 쓰는가
        })
    print(f"[relm] 좌표 변환 {len(cat)}행")

    out: dict[str, list[dict]] = {}
    for slug in args.slugs:
        hub = get_hub(slug)
        if hub is None:
            print(f"  [건너뜀] {slug}: page_hubs 에 없다")
            continue
        rad = args.radius_m or hub.stores_radius_m
        near = []
        for c in cat:
            d = _haversine_m(hub.cy, hub.cx, c["lat"], c["lon"])
            if d <= rad:
                near.append({**c, "dist_m": round(d)})
        near.sort(key=lambda x: x["dist_m"])
        out[slug] = near

        print(f"\n■ {slug} ({hub.name}) r={rad}m — 후보 {len(near)}")
        for c in near:
            mark = f"  ⚠이미 {c['taken_by']}" if c["taken_by"] else ""
            print(f"   {c['dist_m']:>4}m  {c['code']}  {c['name'][:22]:<22} "
                  f"{c['se']:<6} {c['gu']}{mark}")
        if not near:
            print("   (반경 안 상권 없음 — 반경을 넓히거나 인접 거점과의 공유를 검토)")

    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
