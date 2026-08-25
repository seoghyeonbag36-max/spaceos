"""[Posting] 공실 유닛 → **집계구** PIP 배정표 (silver/unit_jipgyegu.json).

## 무엇을 여는가 (막힘 5)

`foot`(유동인구)은 지금 **최근접 상권**에서 온다. 거점당 상권이 1~9곳(중앙 3)뿐이라
한 거점의 유닛 12개가 2~3등급으로만 갈렸다 — 유닛 사이 서열을 만들 수 없었다.

집계구는 서울 19,038개이고, 우리 528유닛이 **326개 (거점,집계구) 쌍**으로 갈린다
(거점당 중앙 **6개** — 상권 중앙 3의 2배). 이 표가 그 배정이다.

## 왜 2016년판 경계인가

집계구 생활인구(OA-14979)의 코드가 **13자리 2016년 기준**이고, 계열의 마지막 달
(2026-07)까지 그대로다. 2025년 2분기 경계(14자리)로는 매칭이 37.5% 에 그쳤다 —
집계구가 재획정됐기 때문이지 코드 포맷 문제가 아니다. 2016년 4분기판으로 받으니
**생활인구 19,038개가 100.00% 붙는다**(경계에만 있는 115개는 생활인구 행이 없는 집계구).

## 좌표계

유닛 좌표는 WGS84(4326), 경계는 UTM-K(5179)다. 변환 없이 대면 수 km 어긋난다.
(이 저장소에 4326·5179·5181 셋이 공존한다 — bronze/national README 참조)

실행: python -m data.pipelines.build_unit_jipgyegu
"""
from __future__ import annotations

import collections
import glob
import json
from datetime import datetime, timezone
from pathlib import Path

import shapefile
from pyproj import Transformer

from data.collectors.common import DATA_ROOT, GOLD

_BND = DATA_ROOT / "bronze" / "seoul" / "2026-08-25" / "jipgyegu_2016" / "bnd_oa_11_2016_4Q.shp"
_OUT = DATA_ROOT / "silver" / "unit_jipgyegu.json"
_CODE_FIELD = "TOT_REG_CD"


def _inside(x: float, y: float, shp) -> bool:
    """ray casting — 멀티파트(구멍 포함) 링을 모두 토글한다."""
    pts, parts = shp.points, list(shp.parts) + [len(shp.points)]
    c = False
    for a, b in zip(parts, parts[1:]):
        ring = pts[a:b]
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-18) + xi):
                c = not c
            j = i
    return c


def run() -> dict:
    if not _BND.exists():
        raise FileNotFoundError(f"{_BND} 없음 — SGIS 과거집계구(2016 4Q) 를 먼저 받을 것")
    r = shapefile.Reader(str(_BND))
    fields = [f[0] for f in r.fields[1:]]
    ci = fields.index(_CODE_FIELD)
    shapes, recs = r.shapes(), r.records()
    bbox = [(s.bbox, i) for i, s in enumerate(shapes)]

    tf = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    units: dict[str, dict] = {}
    missed: list[dict] = []
    for f in sorted(glob.glob(str(GOLD / "*" / "vacant_units.json"))):
        did = Path(f).parent.name
        doc = json.loads(Path(f).read_text(encoding="utf-8"))
        for u in doc.get("units", []):
            if not (u.get("lat") and u.get("lng")):
                continue
            lat, lng = float(u["lat"]), float(u["lng"])
            x, y = tf.transform(lng, lat)
            hit = None
            for bb, i in bbox:
                if bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3] and _inside(x, y, shapes[i]):
                    hit = str(recs[i][ci]).strip()
                    break
            if hit:
                # ⚠ 키는 (거점, 유닛)다. 유닛 id 는 **건물 단위**라 거점 간 유일하지
                # 않다 — 거점 반경이 겹치면 같은 건물이 두 거점에 잡힌다(2026-08-25
                # 실측 47건: apgujeong-rodeo↔dosan · chungmuro↔euljiro 등).
                # id 만으로 키를 잡으면 528쌍이 481개로 조용히 줄어든다.
                units[f"{did}|{u['id']}"] = {"district_id": did, "unit_id": u["id"],
                                             "oa_code": hit, "lat": lat, "lng": lng}
            else:
                missed.append({"id": u["id"], "district_id": did, "lat": lat, "lng": lng})

    per = collections.defaultdict(set)
    for v in units.values():
        per[v["district_id"]].add(v["oa_code"])
    sizes = sorted(len(s) for s in per.values())

    out = {
        "source": f"SGIS 과거집계구 2016 4Q ({_BND.name}) × gold/*/vacant_units.json",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "boundary_base_year": "2016",
        "note": (
            "집계구 코드는 13자리 2016년 기준 — 생활인구(OA-14979)와 100.00% 일치. "
            "2025년 2분기 경계로는 37.5% 였다(집계구 재획정). "
            "⚠ 생활인구 계열은 2026-07-31 로 생산 종료 — 이 배정으로 만드는 foot 은 "
            "2017-01~2026-07 구간의 대표값이다. "
            "⚠ 키는 '거점|유닛id' 다. 유닛 id 는 건물 단위라 거점 간 유일하지 않고, "
            "거점 반경이 겹치는 47건이 두 거점에 함께 잡힌다 — 거점별로 foot 이 "
            "따로 필요하므로 쌍을 유지한다."
        ),
        "stats": {
            "units_assigned": len(units),
            "unit_ids_distinct": len({v["unit_id"] for v in units.values()}),
            "shared_across_districts": len(units) - len({v["unit_id"] for v in units.values()}),
            "units_missed": len(missed),
            "districts": len(per),
            "unique_pairs": len({(v["district_id"], v["oa_code"]) for v in units.values()}),
            "oa_per_district_median": sizes[len(sizes) // 2] if sizes else 0,
            "oa_per_district_min": sizes[0] if sizes else 0,
            "oa_per_district_max": sizes[-1] if sizes else 0,
            "districts_resolvable": sum(1 for s in per.values() if len(s) > 1),
        },
        "missed": missed,
        "units": units,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    o = run()
    s = o["stats"]
    print(f"[unit-jipgyegu] 배정 {s['units_assigned']}쌍 "
          f"(고유 유닛 {s['unit_ids_distinct']} · 두 거점 공유 {s['shared_across_districts']}) "
          f"· 미배정 {s['units_missed']} → {_OUT}")
    print(f"  거점 {s['districts']} · 고유 쌍 {s['unique_pairs']} · "
          f"거점당 집계구 중앙 {s['oa_per_district_median']} "
          f"({s['oa_per_district_min']}~{s['oa_per_district_max']})")
    print(f"  유닛 서열이 갈리는 거점 {s['districts_resolvable']}/{s['districts']}")


if __name__ == "__main__":
    main()
