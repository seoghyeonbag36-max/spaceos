"""서울 25구 거점 선정 점수 산식 — Bronze -> Silver -> Gold.

흐름:
  Bronze: 수집기 4종(SNS/VAC/MAP/FOOT)의 구별 0~100 원시 지표를 적재.
  Silver: 각 지표를 config.SCORE_BANDS로 대상별(b2c/b2b) 1~4점으로 정규화.
  Gold:   대상별 합산 + 전체 합산(최대 32) + tilt 연속점수로 동점 정렬 -> 순위(rank).
          Phase는 점수파생이 아니라 config.PHASE_PLAN(확정 SSOT)에서 부여한다.

산식 원칙(메모리 seoul-25-districts-priority 모델과 동일):
  - 공실(VAC)은 SpaceOS가 푸는 문제라 b2b에선 '많을수록 高점수'.
  - 동점은 TILT 가중 연속점수로 정렬.
  - rank(점수순)와 phase(진입 계획)는 별개 축이다. phase는 PHASE_PLAN만 따른다.

실행:
  python -m data.pipelines.district_score
"""
from __future__ import annotations

import json
import os
from datetime import datetime

from data.config.seoul_districts import (
    CRITERIA, DISTRICTS, SCORE_BANDS, TARGETS, TILT,
    PHASE_PLAN, DISTRICT_PHASE, DISTRICT_PHASE_SEQ, DISTRICT_DEPLOY_ORDER,
)


# ── Bronze ────────────────────────────────────────────────────────────────────
def ingest_bronze() -> dict[str, dict[str, float]]:
    """수집기 4종을 호출해 구별 원시 0~100 지표를 모은다(키 없으면 프록시 폴백)."""
    from data.collectors.living_population import fetch_living_population
    from data.collectors.naver_datalab import fetch_map_interest
    from data.collectors.sns_mentions import fetch_sns_mentions
    from data.collectors.vacancy import fetch_vacancy

    sns = fetch_sns_mentions()
    mp = fetch_map_interest()
    foot = fetch_living_population()
    vac = fetch_vacancy()  # 소상공인 API(density 모드) 또는 공식 공실률 base 앵커

    return {gu: {"SNS": sns[gu], "VAC": vac[gu], "MAP": mp[gu], "FOOT": foot[gu]}
            for gu in DISTRICTS}


# ── Silver ────────────────────────────────────────────────────────────────────
def _score_band(value: float, bands: list[tuple[int, int]]) -> int:
    """0~100 원시값을 (upper, score) 밴드로 1~4점 변환."""
    for upper, score in bands:
        if value <= upper:
            return score
    return bands[-1][1]


def transform_silver(bronze: dict[str, dict[str, float]]) -> dict[str, dict]:
    """원시 지표 -> 대상별·기준별 1~4점."""
    silver: dict[str, dict] = {}
    for gu, raw in bronze.items():
        entry = {"raw": raw, "b2c": {}, "b2b": {}}
        for crit in CRITERIA:
            for tgt in TARGETS:
                entry[tgt][crit] = _score_band(raw[crit], SCORE_BANDS[crit][tgt])
        silver[gu] = entry
    return silver


# ── Gold ──────────────────────────────────────────────────────────────────────
def build_gold(silver: dict[str, dict] | None = None) -> list[dict]:
    """합산·정렬(rank) + PHASE_PLAN 부여 -> Gold 점수표(list, 점수순위 오름차순).

    rank: 점수(total, 동점 시 tilt)로 매기는 분석용 순위.
    phase/phaseSeq/deployOrder: config.PHASE_PLAN(확정 SSOT)에서 부여하는 진입 계획.
    """
    if silver is None:
        silver = transform_silver(ingest_bronze())

    rows = []
    for gu, e in silver.items():
        sum_b2c = sum(e["b2c"].values())
        sum_b2b = sum(e["b2b"].values())
        total = sum_b2c + sum_b2b
        tilt = sum(e["raw"][c] / 25.0 * TILT[t][c] for t in TARGETS for c in CRITERIA)
        rows.append({"name": gu, "code": DISTRICTS[gu]["code"], "raw": e["raw"],
                     "b2c": e["b2c"], "b2b": e["b2b"],
                     "sumB2C": sum_b2c, "sumB2B": sum_b2b, "total": total,
                     "_tilt": round(tilt, 3)})

    rows.sort(key=lambda r: (-r["total"], -r["_tilt"]))
    for i, r in enumerate(rows, 1):
        gu = r["name"]
        r["rank"] = i                                   # 점수순 분석 순위
        r["phase"] = DISTRICT_PHASE[gu]                 # 진입 Phase (PHASE_PLAN SSOT)
        r["phaseSeq"] = DISTRICT_PHASE_SEQ[gu]          # Phase 내 진입 순번
        r["deployOrder"] = DISTRICT_DEPLOY_ORDER[gu]    # 전체 진입 순번(1~25)
    return rows


def save_gold(rows: list[dict], out_dir: str = "data/gold") -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "seoul_district_scores.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now().isoformat(),
                   "model": "seoul-25-districts-priority",
                   "phase_plan": PHASE_PLAN,  # 진입 계획 SSOT 에코(소비자가 그대로 참조)
                   "rows": rows},
                  f, ensure_ascii=False, indent=2)
    return path


def run() -> list[dict]:
    rows = build_gold()
    path = save_gold(rows)
    print(f"[gold] {len(rows)}개 구 점수표 저장 -> {path}")
    # 진입 계획(PHASE_PLAN) 순서로 출력 — Phase 구분선 + 점수순위(rank) 병기.
    by_plan = sorted(rows, key=lambda r: r["deployOrder"])
    print(f"\n{'#':>2} {'구':<6} {'합':>3} {'B2C':>4} {'B2B':>4} {'점수위':>5}")
    cur = 0
    for r in by_plan:
        if r["phase"] != cur:
            cur = r["phase"]
            members = " · ".join(PHASE_PLAN[cur])
            print(f"── Phase {cur} ──  {members}")
        print(f"{r['deployOrder']:>2} {r['name']:<6} {r['total']:>3} "
              f"{r['sumB2C']:>4} {r['sumB2B']:>4} {r['rank']:>5}")
    return rows


if __name__ == "__main__":
    run()
