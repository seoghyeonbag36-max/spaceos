"""[Platform] **점포 노드** → 집계구 PIP 배정표 (막힘 5, GNN 쪽 다리).

## 왜 유닛 배정표로는 안 되나

`build_unit_jipgyegu` 는 **공실 유닛 528호**를 집계구에 배정한다. Posting 의 `foot`
서열은 그것으로 족하다 — 값을 붙일 대상이 유닛이기 때문이다.

GNN 은 대상이 다르다. 노드가 **40,388개**이고, 그 노드들이 떨어지는 집계구는
**1,155개**로 유닛 배정표의 293개를 크게 넘는다(거점당 중앙 **19개**, 유닛 기준 6개).
2026-08-26 프로브에서 이 차이가 그대로 드러났다:

| | 값 |
|---|---|
| PIP 성공 | **40,388/40,388 = 100.0%** |
| 생활인구 프로필 보유 | 17,557 = **43.5%** |

즉 못 붙는 노드는 **하나도 없고**, 못 쓰는 노드는 전부 *그 집계구의 생활인구를 아직
안 받아서* 생긴다. 구조 문제가 아니라 **수집 범위 문제**다 — 뭉뚱그려 "귀속률 43.5%"
로 적으면 레버가 없는 것처럼 읽힌다.

## 이 표를 내면 무엇이 달라지나

`living_population_jipgyegu.target_codes()` 가 유닛 배정표 ∪ **이 표**를 대상으로
삼는다. 수집기는 월별 ZIP 을 스트리밍하며 필요한 날짜만 증분 해제하므로,
keep-list 를 넓혀도 **내려받는 양은 그대로**다(~290MB/7일). 늘어나는 것은 저장할
행 수뿐이고 그마저 1,155/19,153 = 6% 라, "전량을 받아 놓고 못 붙인다"는 원래 금지
사유에 걸리지 않는다.

⚠ 경계는 `build_unit_jipgyegu` 와 **같은 2016 4Q** 를 쓴다. 2025 2분기 경계로는
생활인구 코드와 37.5% 밖에 안 맞는다(집계구 재획정 탓이지 포맷 문제가 아니다).

실행: python -m data.pipelines.build_node_jipgyegu
산출: data/silver/node_jipgyegu.json
"""
from __future__ import annotations

import collections
import json
import statistics as st
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import shapefile
from pyproj import Transformer

from data.collectors.common import DATA_ROOT, GOLD
from data.pipelines.build_unit_jipgyegu import _BND, _CODE_FIELD, _inside

_NODES = GOLD / "platform13" / "platform_store_graph_nodes.parquet"
_OUT = DATA_ROOT / "silver" / "node_jipgyegu.json"

# PIP 후보 추림용 격자(EPSG:5179 미터). 유닛 528호는 폴리곤 19,153개를 전수 bbox
# 스캔해도 되지만, 노드 40,388개는 7.7억 번이라 못 쓴다.
# ⚠ 격자는 **후보를 줄일 뿐** 판정은 같은 `_inside` 가 한다 — 결과가 달라지지 않는다.
_GRID_M = 1000.0


def assign(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """WGS84 좌표 배열 → 집계구 코드 배열(못 찾으면 빈 문자열).

    `build_unit_jipgyegu` 와 같은 경계·같은 ray casting 을 쓰되 격자 색인을 얹는다.
    프로브·파이프라인이 이 함수 하나를 공유해야 두 곳의 배정이 안 갈라진다.
    """
    if not _BND.exists():
        raise FileNotFoundError(f"{_BND} 없음 — SGIS 과거집계구(2016 4Q) 를 먼저 받을 것")
    r = shapefile.Reader(str(_BND))
    fields = [f[0] for f in r.fields[1:]]
    ci = fields.index(_CODE_FIELD)
    shapes, recs = r.shapes(), r.records()

    cells: dict[tuple[int, int], list[int]] = collections.defaultdict(list)
    for i, s in enumerate(shapes):
        x0, y0, x1, y1 = s.bbox
        for gx in range(int(x0 // _GRID_M), int(x1 // _GRID_M) + 1):
            for gy in range(int(y0 // _GRID_M), int(y1 // _GRID_M) + 1):
                cells[(gx, gy)].append(i)

    tf = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    ok = np.isfinite(lat) & np.isfinite(lon)
    xs, ys = tf.transform(np.where(ok, lon, 0.0), np.where(ok, lat, 0.0))

    out = np.array([""] * len(lat), dtype=object)
    for n, (x, y, good) in enumerate(zip(xs, ys, ok)):
        if not good:
            continue
        for i in cells.get((int(x // _GRID_M), int(y // _GRID_M)), ()):
            bb = shapes[i].bbox
            if bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3] and _inside(x, y, shapes[i]):
                out[n] = str(recs[i][ci]).strip()
                break
    return out


def run() -> dict:
    nodes = pd.read_parquet(_NODES)
    lat = pd.to_numeric(nodes["lat"], errors="coerce").to_numpy(dtype=float)
    lon = pd.to_numeric(nodes["lon"], errors="coerce").to_numpy(dtype=float)
    did = nodes["district_id"].fillna("").astype(str).to_numpy()
    oa = assign(lat, lon)

    hit = np.array([bool(c) for c in oa])
    per: dict[str, set[str]] = collections.defaultdict(set)
    for d, c in zip(did[hit], oa[hit]):
        per[d].add(c)
    sizes = sorted(len(s) for s in per.values())
    codes = sorted({c for c in oa if c})

    out = {
        "source": f"SGIS 과거집계구 2016 4Q ({_BND.name}) × {_NODES.name}",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "boundary_base_year": "2016",
        "note": (
            "GNN 노드 → 집계구 배정. 유닛 배정표(unit_jipgyegu)와 **대상이 다르다** — "
            "유닛 528호는 집계구 293곳에 떨어지지만 노드 40,388개는 1,155곳에 떨어진다. "
            "living_population_jipgyegu.target_codes() 가 두 표의 합집합을 쓴다."),
        "stats": {
            "nodes": int(len(nodes)),
            "assigned": int(hit.sum()),
            "assign_rate": round(float(hit.mean()), 4),
            "oa_codes": len(codes),
            "oa_per_district_median": int(st.median(sizes)) if sizes else 0,
            "oa_per_district_min_max": [sizes[0], sizes[-1]] if sizes else [0, 0],
            "districts": len(per),
        },
        "oa_codes": codes,
        "nodes": {str(n): c for n, c in zip(nodes["node_id"].astype(str), oa) if c},
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    s = out["stats"]
    print(f"[node-jipgyegu] 노드 {s['nodes']} · 배정 {s['assigned']} "
          f"({s['assign_rate']:.1%}) · 집계구 {s['oa_codes']}곳 · "
          f"거점당 중앙 {s['oa_per_district_median']}곳 → {_OUT.name}")
    return out


def main() -> None:
    run()


if __name__ == "__main__":
    main()
