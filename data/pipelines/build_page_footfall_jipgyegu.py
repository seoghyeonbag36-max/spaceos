"""[Page] 유동·밀도 레이어를 **집계구**로 올리는 gold 산출물.

## 무엇이 달라지나

종전 Page 유동 레이어는 셀마다 **최근접 상권**의 총량에 시간 구성비를 곱했다:

    셀 값 = (최근접 TRDAR 상권 유동총량) × (그 시각 구성비)

공간은 상권(거점당 1~9곳·중앙 3), 시간은 행정동(거점당 1~2곳)이었다. 그래서 게이트
문구가 이렇게 물러서 있었다 — *"행정동 집계라 **거점 내부의 시간 차이는 알 수 없다**"*.

집계구는 **공간과 시간을 같은 눈금에서 동시에** 준다. 거점당 중앙 **26곳**(4~66)이고
값 자체가 시각별 생활인구다:

    셀 값 = (그 셀이 속한 집계구의 그 시각 생활인구)

곱셈이 사라지는 것이 요점이다. 종전에는 공간 축과 시간 축이 서로 다른 원천이라
둘을 곱해 붙였는데, 이제 한 표에서 나온다 — **거점 내부의 시간 차이가 표현된다.**

## ⚠ 그래도 격자 실측은 아니다

집계구는 100m 격자보다 크다(서울 평균 인구 약 500명 단위). 셀 값은 여전히 "그 셀이
속한 **구획**의 값"이지 그 셀의 실측이 아니다. 상권 → 집계구는 입도가 올라간 것이지
종류가 바뀐 것이 아니므로, 응답의 `resolution: "jipgyegu"` 와 범례가 계속 밝힌다.

## 커버리지는 거점 단위로 전부-아니면-전무다

한 거점 안에서 어떤 셀은 집계구, 어떤 셀은 상권으로 값을 매기면 **같은 화면의 두 셀이
서로 다른 눈금**이 된다. 색은 min/max 재정규화로 그럴듯하게 나오지만 비교가 거짓이
된다. 그래서 거점의 셀이 **전부** 덮일 때만 그 거점을 싣는다.

## 밀도

집계구 폴리곤 면적(EPSG:5179 shoelace)으로 나눈다 — `명/1,000㎡`. 점포 밀도(`stor`)는
집계구에 대응하는 원천이 없으므로 **올리지 않고 상권에 남긴다**(§ 서빙 폴백).

⚠ 생활인구 계열은 **2026-07-31 로 생산 종료**다. 이 값은 그 시점까지의 대표값이며
갱신되지 않는다 — `build_unit_foot` 과 같은 전제다.

실행: python -m data.pipelines.build_page_footfall_jipgyegu
산출: data/gold/page_footfall_jipgyegu.json
"""
from __future__ import annotations

import collections
import datetime
import json
import statistics as st
from pathlib import Path

import numpy as np

from data.collectors.common import DATA_ROOT, GOLD

_CELLS = DATA_ROOT / "silver" / "cell_jipgyegu.json"
_BRONZE = DATA_ROOT / "bronze" / "seoul"
_OUT = GOLD / "page_footfall_jipgyegu.json"

# build_unit_foot._SAMPLE 과 같은 주. 두 산출물이 다른 주를 쓰면 Posting 의 `foot`
# 서열과 Page 히트맵이 같은 자리를 두고 다른 말을 한다.
_SAMPLE = [f"2026-07-0{i}" for i in range(1, 8)]


def _is_weekend(day: str) -> bool:
    return datetime.date.fromisoformat(day).weekday() >= 5


def _ring_area(ring: list[tuple[float, float]]) -> float:
    """shoelace — 부호가 있는 면적(㎡). ESRI 규약상 외곽링과 구멍의 부호가 반대다."""
    a = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a / 2.0


def _oa_areas(codes: set[str]) -> dict[str, float]:
    """집계구 코드 → 폴리곤 면적(㎡). 멀티파트·구멍을 부호 합으로 처리한다."""
    import shapefile
    from data.pipelines.build_unit_jipgyegu import _BND, _CODE_FIELD

    r = shapefile.Reader(str(_BND))
    fields = [f[0] for f in r.fields[1:]]
    ci = fields.index(_CODE_FIELD)
    out: dict[str, float] = {}
    for shp, rec in zip(r.shapes(), r.records()):
        code = str(rec[ci]).strip()
        if code not in codes:
            continue
        pts, parts = shp.points, list(shp.parts) + [len(shp.points)]
        area = sum(_ring_area(pts[a:b]) for a, b in zip(parts, parts[1:]))
        out[code] = abs(area)
    return out


def _profiles(codes: set[str]) -> tuple[dict[str, dict], list[str]]:
    """집계구 → {wd: [24], we: [24]} (날짜 평균). build_adong_hourly_features 와 같은 방식."""
    buckets: dict[tuple[str, int, bool], list[float]] = collections.defaultdict(list)
    seen: list[str] = []
    for day in _SAMPLE:
        p = _BRONZE / day / "living_population_jipgyegu.json"
        if not p.exists():
            continue
        seen.append(day)
        wknd = _is_weekend(day)
        for r in json.loads(p.read_text(encoding="utf-8")):
            if r.get("pop") is None or r["oa"] not in codes:
                continue
            buckets[(r["oa"], int(r["hour"]), wknd)].append(float(r["pop"]))
    if not seen:
        raise FileNotFoundError(
            f"{_BRONZE} 에 집계구 생활인구 표본이 없다 — "
            "python -m data.collectors.living_population_jipgyegu --month 202607 --days 7")

    prof: dict[str, dict[tuple[int, bool], float]] = collections.defaultdict(dict)
    for (oa, hr, wknd), vals in buckets.items():
        prof[oa][(hr, wknd)] = float(np.mean(vals))

    out: dict[str, dict] = {}
    for oa, p in prof.items():
        wd = [round(p.get((h, False), 0.0), 1) for h in range(24)]
        we = [round(p.get((h, True), 0.0), 1) for h in range(24)]
        # 24시간이 통째로 0 이면 표본에 그 집계구가 안 들어온 것이다 — 0 을 실으면
        # "사람이 없는 곳"으로 읽히므로 아예 싣지 않는다.
        if max(wd) <= 0 and max(we) <= 0:
            continue
        out[oa] = {"wd": wd, "we": we}
    return out, seen


def run() -> dict:
    if not _CELLS.exists():
        raise FileNotFoundError(
            f"{_CELLS} 없음 — `python scripts/build_cell_jipgyegu.py` 를 먼저 실행할 것")
    doc = json.loads(_CELLS.read_text(encoding="utf-8"))
    cell_oa: dict[str, str] = doc["cells"]

    codes = set(doc["oa_codes"])
    prof, days = _profiles(codes)
    areas = _oa_areas(codes)
    n_wd = sum(1 for d in days if not _is_weekend(d))

    # 거점별로 모은다. 커버리지는 **전부-아니면-전무** — 부분이면 그 거점은 안 싣는다.
    per: dict[str, dict[str, str]] = collections.defaultdict(dict)
    total: collections.Counter = collections.Counter()
    for key, oa in cell_oa.items():
        did, i, j = key.split("|")
        total[did] += 1
        if oa in prof:
            per[did][f"{i}|{j}"] = oa

    districts: dict[str, dict] = {}
    partial: dict[str, list[int]] = {}
    for did, cells in per.items():
        if len(cells) < total[did]:
            partial[did] = [len(cells), total[did]]
            continue
        districts[did] = {
            "cells": cells,
            "oa_count": len(set(cells.values())),
            "cell_count": len(cells),
        }

    used = sorted({oa for d in districts.values() for oa in d["cells"].values()})
    sizes = sorted(d["oa_count"] for d in districts.values())
    out = {
        "source": ("서울 열린데이터광장 OA-14979 집계구 단위 생활인구(내국인) × "
                   "SGIS 과거집계구 2016 4Q 경계 PIP 배정 (100m 격자 셀 중심)"),
        "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "sample_days": days,
        "sample_weekday": n_wd,
        "sample_weekend": len(days) - n_wd,
        "note": (
            "셀 값은 그 셀이 속한 **집계구**의 시각별 생활인구다. 공간과 시간이 같은 "
            "원천에서 나오므로 거점 내부의 시간 차이가 표현된다 — 종전 상권×행정동 "
            "곱셈에서는 알 수 없던 것이다. ⚠ 그래도 격자 실측은 아니다: 집계구는 "
            "100m 격자보다 크고, 셀 값은 그 셀이 속한 구획의 값이다. "
            "⚠ 커버리지는 거점 단위로 전부-아니면-전무다 — 한 화면에서 두 눈금이 "
            "섞이면 색은 그럴듯한데 비교가 거짓이 된다. "
            "⚠ 생활인구 계열은 2026-07-31 로 생산 종료이며 이 값은 대표값이다."),
        "stats": {
            "districts": len(districts),
            "districts_partial": partial,
            "oa_used": len(used),
            "cells": sum(d["cell_count"] for d in districts.values()),
            "oa_per_district_median": int(st.median(sizes)) if sizes else 0,
            "oa_per_district_min_max": [sizes[0], sizes[-1]] if sizes else [0, 0],
            "oa_area_m2_median": round(st.median(areas.values()), 1) if areas else 0.0,
        },
        "oa": {c: {**prof[c], "area_m2": round(areas.get(c, 0.0), 1)} for c in used},
        "districts": districts,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    s = out["stats"]
    print(f"[page-foot-jipgyegu] 거점 {s['districts']}/54 · 셀 {s['cells']} · "
          f"집계구 {s['oa_used']}곳 · 거점당 중앙 {s['oa_per_district_median']}곳 · "
          f"집계구 면적 중앙 {s['oa_area_m2_median']:,.0f}㎡ → {_OUT.name}")
    if partial:
        print(f"  ⚠ 부분 커버라 제외한 거점 {len(partial)}곳: "
              + " ".join(f"{k}({v[0]}/{v[1]})" for k, v in sorted(partial.items())))
    return out


def main() -> None:
    run()


if __name__ == "__main__":
    main()
