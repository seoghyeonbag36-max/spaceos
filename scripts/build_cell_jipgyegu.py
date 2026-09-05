"""[Page] **100m 공실 격자 셀** → 집계구 PIP 배정표.

## 왜 script 이고 pipeline 이 아닌가

배정 대상 셋 중 이것만 원천이 backend 에 있다:

| 배정표 | 대상 | 원천 | 자리 |
|---|---|---|---|
| `unit_jipgyegu` | 공실 유닛 528호 | `gold/*/vacant_units.json` | data/pipelines |
| `node_jipgyegu` | 점포 노드 40,388 | `gold/platform13/*.parquet` | data/pipelines |
| **`cell_jipgyegu`** | **격자 셀 3,699** | **`app.services.districts.cells_for`** | **여기** |

100m 격자는 거점 `grid`(bbox·dlat·dlng) 정의에서 나오고 그것은 backend 설정이다.
`data/` 는 backend 를 임포트하지 않는다(이 저장소의 층 규칙) — 그래서 두 쪽이 만나도
되는 자리인 `scripts/` 에 둔다. `pppp_status`·`posting_cost_sensitivity` 와 같은 위치다.

## 왜 필요한가

2026-08-26 실측: 격자 셀 **3,699**개(거점당 중앙 68)가 집계구 **1,303**곳에 떨어진다.
유닛+노드 배정표만으로는 셀 기준 커버리지가 **88.4%** 에 그친다 — 셀이 점포도 공실도
없는 집계구(공원·학교·대로)에 떨어지기 때문이다. **326곳**이 더 필요하다.

`living_population_jipgyegu` 는 월별 ZIP 을 스트리밍하며 증분 해제하므로 keep-list 를
넓혀도 **내려받는 양이 그대로**다(~290MB/7일). 늘어나는 저장은 1,501/19,153 = 7.8% 다.

실행: python scripts/build_cell_jipgyegu.py
산출: data/silver/cell_jipgyegu.json
"""
from __future__ import annotations

import collections
import json
import statistics as st
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
for p in (_ROOT, _ROOT / "apps" / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.services import districts                                # noqa: E402
from data.pipelines.build_node_jipgyegu import assign             # noqa: E402

_OUT = _ROOT / "data" / "silver" / "cell_jipgyegu.json"


def run() -> dict:
    lats: list[float] = []
    lngs: list[float] = []
    dids: list[str] = []
    keys: list[str] = []
    per_cells: dict[str, int] = {}
    # ⚠ `DISTRICTS_BY_ID` 가 아니라 `PAGES` 를 돈다. DISTRICTS 는 **시드 54거점**이라
    #   서울 3차 12거점(bulgwang·cheonho·doksan·hwagok·kkachisan·miasageori·mokdong-yc·
    #   oryudong·sangbong·sanggye·suyu·yeonsinnae)이 배정표에 아예 안 들어왔다. 그 결과
    #   `target_codes()` 의 keep-list 가 좁아 생활인구를 안 받았고, 유동·밀도 레이어가
    #   그 12거점에서 조용히 상권(trdar)으로 폴백했다 — 화면은 멀쩡해 보였다.
    #   **같은 버그가 2026-09-04 `pppp_status._precision_hubs` 에서 한 번 잡혔는데
    #   여기가 빠졌다**(2026-09-05 발견). 셀을 도는 곳은 전부 PAGES 여야 한다.
    for _p in getattr(districts, "PAGES", None) or districts.DISTRICTS:
        did = _p["id"]
        hm = districts.get_vacancy_heatmap(did)
        if not hm:
            continue
        cells = hm["cells"]
        per_cells[did] = len(cells)
        for c in cells:
            # 셀 **중심**으로 배정한다. 모서리로 하면 경계에 걸친 셀이 이웃 집계구로
            # 튀고, 어느 모서리를 쓰느냐에 따라 답이 달라진다.
            lats.append(c["c_lat"])
            lngs.append(c["c_lng"])
            dids.append(did)
            # 키는 **격자 좌표**다. 순번으로 잡으면 셀 순회 순서가 바뀌는 날
            # 배정이 통째로 한 칸씩 밀리면서 아무 오류도 안 난다.
            keys.append(f"{did}|{c['i']}|{c['j']}")

    oa = assign(np.array(lats, dtype=float), np.array(lngs, dtype=float))
    hit = np.array([bool(c) for c in oa])

    per: dict[str, set[str]] = collections.defaultdict(set)
    for d, c in zip(np.array(dids)[hit], oa[hit]):
        per[d].add(c)
    sizes = sorted(len(s) for s in per.values())
    codes = sorted({c for c in oa if c})

    out = {
        "source": "SGIS 과거집계구 2016 4Q × app.services.districts.cells_for (100m 격자)",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "boundary_base_year": "2016",
        "note": (
            "Page 유동·밀도 레이어를 상권 단위에서 집계구 단위로 올리기 위한 배정표. "
            "셀은 중심 좌표로 배정한다. living_population_jipgyegu.target_codes() 가 "
            "유닛·노드 표와 함께 합집합으로 쓴다."),
        "stats": {
            "cells": int(len(oa)),
            "assigned": int(hit.sum()),
            "assign_rate": round(float(hit.mean()), 4),
            "oa_codes": len(codes),
            "districts": len(per_cells),
            "cells_per_district_median": int(st.median(per_cells.values())) if per_cells else 0,
            "oa_per_district_median": int(st.median(sizes)) if sizes else 0,
            "oa_per_district_min_max": [sizes[0], sizes[-1]] if sizes else [0, 0],
        },
        "oa_codes": codes,
        # 키 = "{거점}|{i}|{j}" (격자 좌표). 서빙이 셀을 이 키로 조회한다.
        "cells": {k: c for k, c in zip(keys, oa) if c},
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    s = out["stats"]
    print(f"[cell-jipgyegu] 셀 {s['cells']} · 배정 {s['assigned']} "
          f"({s['assign_rate']:.1%}) · 집계구 {s['oa_codes']}곳 · "
          f"거점당 중앙 {s['oa_per_district_median']}곳 → {_OUT.name}")
    return out


if __name__ == "__main__":
    run()
