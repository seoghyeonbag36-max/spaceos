"""[Page→Platform] 행정동 24시간 생활인구 → **노드 피처용** 테이블 (gold/features/adong_hourly.parquet).

`build_page_footfall_hourly` 와 같은 원천을 쓰지만 **소비처가 다르다.**
그쪽은 거점 단위로 접어 Page 히트맵 시간축에 쓰고, 이쪽은 접지 않고 **행정동 단위로
남겨** GNN 노드 피처로 쓴다.

## 왜 거점으로 접으면 안 되나

GNN 피처에는 이미 **거점 원핫**이 들어간다(train_gnn._features). 거점 안에서 상수인
값은 원핫이 완전히 표현하므로 붙여도 정보가 0이다 — `_demand_block` 이 상권 단위를
고른 것과 같은 이유다. `page_footfall_hourly.json` 은 거점 단위(`districts`)라
그대로는 못 쓴다. 이 파이프라인이 그 앞단(행정동)을 산출물로 낸다.

## 실측 — 거점 내부 분산이 실제로 생기는가 (2026-08-24, 붙이기 전에 쟀다)

노드 40,597 중 좌표→행정동 귀속 **38,592(95.1%)** · 거점당 서로 다른 행정동 중앙 3곳
(1곳뿐인 거점 6/54). 15개 후보 피처의 within-district 분산 비율:

    wd_peak_hour      0.439      we_peak_hour      0.389
    wd_share_evening  0.337      we_share_evening  0.305
    wd_log_total      0.228      we_log_total      0.213
    wd_share_night    0.169      we_share_morning  0.218
                                 we_share_night    0.197
                                 we_peakiness      0.169
    ── 이하 거점 원핫에 흡수(<0.15) ──
    wd_peakiness      0.148      we_share_lunch    0.143
    wd_share_lunch    0.127      we_wd_ratio       0.113
    wd_share_morning  0.126
    평균 0.221  (기존 수요블록 실측 0.46 이 비교선)

기존 수요블록(상권 단위)의 절반이지만 0이 아니다. **피크 시각이 가장 크게 갈린다** —
거점 하나가 업무·상업·주거 성격의 행정동에 걸치면 그 차이가 여기서 드러난다.

15개를 **전부** 저장한다. 어느 것을 쓸지는 소비처(train_gnn._ADONG_COLS)가 정하고,
이 표는 그 선택을 나중에 재검증할 수 있게 남기는 것이 역할이다.

## 무엇이 실측이고 무엇이 근사인가

- **실측**: 행정동 단위 시간대별 생활인구(서울시×통신 기지국 전수화). 24시간 원본.
- **근사**: 행정동 **안에서의** 분포. 원천이 행정동 집계라 건물·격자 단위는 모른다.
  노드를 행정동에 귀속시키는 것뿐이므로, 같은 행정동 노드는 전부 같은 값을 받는다.
  거점 내부 변동은 행정동 경계를 넘는 만큼만 생긴다.

입력: bronze/seoul/{날짜}/living_population_hourly.json
출력: gold/features/adong_hourly.parquet  (행정동 8자리 코드 키)

실행: python -m data.pipelines.build_adong_hourly_features
"""
from __future__ import annotations

import collections

import numpy as np
import pandas as pd

from data.collectors.common import GOLD
from data.pipelines.build_page_footfall_hourly import HOURS, _load_bronze

_OUT = GOLD / "features" / "adong_hourly.parquet"

# 시간대 구획 — 6구간으로 접는 것이 아니라, 24시간 프로필의 **모양**을 몇 개 수로
# 요약한다. 24열을 그대로 넣으면 서로 강하게 상관돼 z-score 후에도 중복이 크다.
_MORNING = slice(7, 11)
_LUNCH = slice(11, 14)
_EVENING = slice(17, 21)


def _shape(v: np.ndarray) -> dict[str, float]:
    """24시간 벡터 → 요약 피처. 수준(log_total)과 모양(share·peak)을 나눈다."""
    tot = float(v.sum())
    sh = v / tot if tot > 0 else v
    mean = float(v.mean())
    return {
        "log_total": float(np.log1p(tot)),
        "peak_hour": float(int(np.argmax(v))),
        "share_morning": float(sh[_MORNING].sum()),
        "share_lunch": float(sh[_LUNCH].sum()),
        "share_evening": float(sh[_EVENING].sum()),
        # 심야는 22~23 + 00~04 로 자정을 넘어 이어 붙인다(하루 경계가 생활 경계가 아니다)
        "share_night": float(sh[22:24].sum() + sh[0:5].sum()),
        "peakiness": float(v.max() / mean) if mean > 0 else 0.0,
    }


def run() -> pd.DataFrame:
    buckets, dates = _load_bronze()
    if not buckets:
        print("[adong-hourly] bronze 비어 있음 — "
              "python -m data.collectors.living_population_hourly 먼저")
        return pd.DataFrame()

    # (행정동, 시, 주말) → 날짜 평균. 평균인 이유는 build_page_footfall_hourly 와 같다
    # (생활인구는 이미 전수 집계라 개별 이상치가 없고, 알고 싶은 것은 평상시 기대치다).
    prof: dict[str, dict[tuple[str, bool], float]] = collections.defaultdict(dict)
    for (ad, hr, wknd), vals in buckets.items():
        if vals:
            prof[ad][(hr, wknd)] = float(np.mean(vals))

    rows = []
    for ad in sorted(prof):
        p = prof[ad]
        row: dict[str, object] = {"adm8": ad}
        tot_by_kind = {}
        for wknd, tag in ((False, "wd"), (True, "we")):
            v = np.array([p.get((h, wknd), 0.0) for h in HOURS], dtype=float)
            tot_by_kind[tag] = v.sum()
            for k, val in _shape(v).items():
                row[f"{tag}_{k}"] = val
        # 주말/평일 수준비 — 업무지구와 상업지구를 가르는 축. 다만 실측상 거점 안에서는
        # 거의 안 변한다(within 0.113) — 거점 **간** 성격 지표에 가깝다.
        row["we_wd_ratio"] = (float(tot_by_kind["we"] / tot_by_kind["wd"])
                              if tot_by_kind["wd"] > 0 else 0.0)
        rows.append(row)

    df = pd.DataFrame(rows)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(_OUT, index=False)
    wk = sum(1 for d in dates if _is_weekend_safe(d))
    print(f"[adong-hourly] 행정동 {len(df)}곳 · 피처 {len(df.columns) - 1}열 · "
          f"표본 {len(dates)}일(주말 {wk}) → {_OUT.relative_to(GOLD.parent.parent)}")
    return df


def _is_weekend_safe(yyyymmdd: str) -> bool:
    import datetime
    try:
        d = datetime.date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    except (ValueError, TypeError):
        return False
    return d.weekday() >= 5


if __name__ == "__main__":
    run()
