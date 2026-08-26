"""[Platform] **집계구** 24시간 생활인구 → GNN 피처 표.

## 무엇이 다른가 — `build_adong_hourly_features` 와 입도만 다르다

`_shape()` 를 **임포트해서** 쓴다. 피처 정의가 갈라지면 두 축의 비교가 무의미해지고,
이 표의 존재 이유가 바로 그 비교다(행정동 → 집계구, 입도만 바꾼 A/B).

| | 행정동 | 집계구 |
|---|---|---|
| 거점당 구획 수 | 1~2 | 노드 기준 중앙 **19** |
| within-district 분산비(동일 10열) | **0.266** | **0.458** (1.72배) |
| 노드 귀속 | 95.1% | **100.0%**(PIP, `silver/node_jipgyegu.json`) |

분산비 0.458 은 이미 잘 도는 수요블록(0.46)과 같은 수준이다. 2026-08-26 3다리 프로브
(`scripts/probe_jipgyegu_foot.py` · reports/jipgyegu_foot_probe_2026-08-26.json)가
사전등록 기각 조건에 안 걸린다고 판정했고, 이 표가 그 판정을 학습으로 옮기는 재료다.

⚠ **프로브 통과가 곧 게이트 상승은 아니다.** 프로브는 변동의 **양**만 재고, §0-J 의
진단은 **종류**를 지목했다("시간·유동 계열로는 약국을 병원 옆에서 가릴 수 없다").
집계구 foot 은 같은 유동 계열의 더 고운 판본이므로, 이 표를 쓰는 학습은 그 진단에
대한 **반증 시도**이지 확정된 개선이 아니다.

## 표본

`build_unit_foot` · `build_page_footfall_jipgyegu` 와 **같은 주**(2026-07-01~07,
평일 5 · 주말 2)를 쓴다. 다른 주를 쓰면 Posting `foot` 서열 · Page 히트맵 · GNN 피처가
같은 자리를 두고 서로 다른 말을 한다.

⚠ 계열은 **2026-07-31 로 생산 종료**다(국가표준격자 250m 전환, 후속은 자치구 단위라
더 거칠다). 이 값은 그 시점까지의 대표값이며 갱신되지 않는다.

실행: python -m data.pipelines.build_jipgyegu_hourly_features
산출: data/gold/features/jipgyegu_hourly.parquet
"""
from __future__ import annotations

import collections
import datetime
import json

import numpy as np
import pandas as pd

from data.collectors.common import DATA_ROOT, GOLD
from data.pipelines.build_adong_hourly_features import _shape

_BRONZE = DATA_ROOT / "bronze" / "seoul"
_OUT = GOLD / "features" / "jipgyegu_hourly.parquet"
_SAMPLE = [f"2026-07-0{i}" for i in range(1, 8)]


def _is_weekend(day: str) -> bool:
    return datetime.date.fromisoformat(day).weekday() >= 5


def run() -> pd.DataFrame:
    # (집계구, 시, 주말) → 날짜 평균. 평균인 이유는 build_adong_hourly_features 와 같다
    # (생활인구는 이미 전수 집계라 개별 이상치가 없고, 알고 싶은 것은 평상시 기대치다).
    buckets: dict[tuple[str, int, bool], list[float]] = collections.defaultdict(list)
    seen: list[str] = []
    for day in _SAMPLE:
        p = _BRONZE / day / "living_population_jipgyegu.json"
        if not p.exists():
            continue
        seen.append(day)
        wknd = _is_weekend(day)
        for r in json.loads(p.read_text(encoding="utf-8")):
            if r.get("pop") is None:
                continue
            buckets[(r["oa"], int(r["hour"]), wknd)].append(float(r["pop"]))
    if not seen:
        print("[jipgyegu-hourly] bronze 비어 있음 — "
              "python -m data.collectors.living_population_jipgyegu --month 202607 --days 7 먼저")
        return pd.DataFrame()

    prof: dict[str, dict[tuple[int, bool], float]] = collections.defaultdict(dict)
    for (oa, hr, wknd), vals in buckets.items():
        prof[oa][(hr, wknd)] = float(np.mean(vals))

    rows = []
    for oa in sorted(prof):
        p = prof[oa]
        row: dict[str, object] = {"oa": oa}
        tot_by_kind = {}
        for wknd, tag in ((False, "wd"), (True, "we")):
            v = np.array([p.get((h, wknd), 0.0) for h in range(24)], dtype=float)
            tot_by_kind[tag] = v.sum()
            for k, val in _shape(v).items():
                row[f"{tag}_{k}"] = val
        row["we_wd_ratio"] = (float(tot_by_kind["we"] / tot_by_kind["wd"])
                              if tot_by_kind["wd"] > 0 else 0.0)
        rows.append(row)

    df = pd.DataFrame(rows)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(_OUT, index=False)
    wk = sum(1 for d in seen if _is_weekend(d))
    print(f"[jipgyegu-hourly] 집계구 {len(df)}곳 · 피처 {len(df.columns) - 1}열 · "
          f"표본 {len(seen)}일(주말 {wk}) → {_OUT.relative_to(GOLD.parent.parent)}")
    return df


def main() -> None:
    run()


if __name__ == "__main__":
    main()
