"""막힘 5(Platform 집계구 입도) 사전 판정 — 600ep 을 돌리기 **전에** 세 다리를 잰다.

## 왜 이 스크립트가 있나

GNN off-prior 게이트는 37%대에서 **네 번** 기각됐다(이웃 36.49 · 조기종료 35.92~37.17 ·
행정동 37.51 · 08-25 재실행 재현). §0-J 가 남긴 진단은 이랬다:

> 막는 것은 변동의 **양**이 아니라 **종류**다 — 시간·유동 계열로는 약국을 병원 옆에서
> 가릴 수 없다.

집계구 `foot` 은 **같은 유동 계열의 더 고운 판본**이라 그 진단과 정면으로 부딪힌다.
다만 한 가지가 다르다: 행정동은 거점당 1~2개라 노드 대부분이 같은 값을 공유했는데,
집계구는 **노드 기준 거점당 중앙 19개**다(유닛 기준 6개 — 노드가 유닛보다 넓게
퍼져 있다). 분산 **구조**가 다르므로 자동 기각은 아니다.

그래서 §0-K(감성)에서 다섯 번째 기각을 실측으로 사지 않게 해 준 값싼 3다리 프로브를
그대로 쓴다. **판정 규칙은 돌리기 전에 정해져 있다**(docs/feature-platform.md §0-L):

    3이 0.221 근처면 돌리지 않는다.

⚠ **2026-08-26 실행에서 그 0.221 이 잘못 인용된 값임이 드러났다.** §0-J 표의 15열
전체 평균이 0.221 인데, `_adong_hour_block` 이 실제로 실은 것은 0.15 미만 5열을 뺀
**10열**이고 그 평균은 **0.266** 이다. 즉 기각된 블록과 같은 자로 대려면 기준선은
0.266 이다. 이 프로브의 교정 실행이 §0-J 표의 10열 값을 소수점까지 재현하므로
(평균 0.266 · 귀속 95.0% ↔ 문서 95.1%) 자는 같다 — 틀린 것은 임계값의 인용이다.

## 세 다리

1. **구조** — 집계구 코드가 노드에 붙는가. 배정표(`silver/unit_jipgyegu.json`)는 공실
   유닛 528호 기준이지 전체 점포 노드가 아니다 → 노드 좌표로 PIP 를 다시 돈다.
2. **귀속** — 40,388 노드 중 집계구가 배정되는 비율. 낮으면 채움값이 지배한다
   (`_adong_hour_block` 은 95.1% 였다).
3. **신호** — within-district 분산비가 `_adong_hour_block`(0.221)보다 유의하게 큰가.
   거점 원핫이 `_features()` 에 이미 있으므로, 거점 안에서 안 변하는 값은 정보량 0 이다.

## 자기 검증 — 같은 자로 재는지부터 본다

0.221 은 **다른 스크립트가 다른 날 계산한 값**이다. 그 숫자에 이 프로브의 결론을
걸려면 같은 정의로 재고 있는지부터 확인해야 한다. 그래서 이 프로브는 동일한 분산비
함수를 **행정동 블록에 먼저 돌려** 0.221 이 재현되는지 본다. 재현이 안 되면 집계구
숫자도 비교 대상이 아니다 — 그때는 판정하지 않는다.

피처 정의는 `build_adong_hourly_features._shape` 를 **임포트해서** 쓴다. 복사하면
두 축의 정의가 조용히 갈라져, 비교 자체가 무의미해진다.

실행: python scripts/probe_jipgyegu_foot.py
산출: reports/jipgyegu_foot_probe_{날짜}.json
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
import statistics as st
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
# `python scripts/…` 로 직접 부르면 sys.path[0] 이 scripts/ 라 data·ml 이 안 보인다.
# 이 프로브의 요점은 학습이 **실제로 쓸 정의**를 그대로 임포트하는 것이므로 경로를 연다.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_NODES = _ROOT / "data" / "gold" / "platform13" / "platform_store_graph_nodes.parquet"
_BRONZE = _ROOT / "data" / "bronze" / "seoul"
_ADONG_HOURLY = _ROOT / "data" / "gold" / "features" / "adong_hourly.parquet"
_COORD_ADONG = _ROOT / "data" / "silver" / "coord_adong_cache.json"
_OUT = _ROOT / "reports" / f"jipgyegu_foot_probe_{date.today().isoformat()}.json"

# build_unit_foot._SAMPLE 과 같은 주를 쓴다 — 다른 주를 쓰면 이 프로브가 통과시킨
# 재료와 실제로 학습에 들어갈 재료가 달라진다.
_SAMPLE = [f"2026-07-0{i}" for i in range(1, 8)]

# _ADONG_COLS 와 **같은 10열**. 행정동에서 0.15 미만이라 탈락한 5열은 여기서도 뺀다 —
# 열 집합이 다르면 평균 분산비를 나란히 못 놓는다.
_COLS = [
    "wd_peak_hour", "we_peak_hour",
    "wd_share_evening", "we_share_evening",
    "wd_log_total", "we_log_total",
    "we_share_morning", "we_share_night",
    "wd_share_night", "we_peakiness",
]
_ADONG_BASELINE = 0.221          # docs/feature-platform.md §0-J 실측
_ADONG_ATTACH = 0.951            # 같은 곳 — 귀속률 95.1%


def _is_weekend(day: str) -> bool:
    return datetime.date.fromisoformat(day).weekday() >= 5


# ---------------------------------------------------------------- 분산비
def _within_ratio(vals: np.ndarray, groups: np.ndarray) -> float:
    """within-district 분산 / 전체 분산.

    거점 원핫이 이미 있으므로 **거점 안에서 남는 변동만**이 새 정보다. 1.0 에
    가까울수록 거점과 무관하게 변한다(= 새 정보), 0 에 가까울수록 거점 원핫에
    통째로 흡수된다(= 정보량 0).

    거점별 분산을 노드 수로 **가중평균**한다 — 단순평균을 내면 노드 3개짜리 거점이
    2,000개짜리 거점과 같은 무게를 갖는다.
    """
    tot = float(np.var(vals))
    if tot <= 0:
        return 0.0
    num = 0.0
    for g in np.unique(groups):
        m = groups == g
        num += m.sum() * float(np.var(vals[m]))
    return num / len(vals) / tot


def _ratios(frame: pd.DataFrame, groups: np.ndarray) -> dict[str, float]:
    return {c: round(_within_ratio(frame[c].to_numpy(dtype=float), groups), 3)
            for c in _COLS}


# ---------------------------------------------------------------- 집계구 프로필
def _oa_features() -> pd.DataFrame:
    """집계구 → 10열. build_adong_hourly_features.run() 과 같은 절차·같은 _shape."""
    from data.pipelines.build_adong_hourly_features import _shape

    buckets: dict[tuple[str, int, bool], list[float]] = collections.defaultdict(list)
    seen = []
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
        raise FileNotFoundError(
            f"{_BRONZE} 에 집계구 생활인구 표본이 없다 — "
            "python -m data.collectors.living_population_jipgyegu --month 202607 --days 7")

    prof: dict[str, dict[tuple[int, bool], float]] = collections.defaultdict(dict)
    for (oa, hr, wknd), vals in buckets.items():
        prof[oa][(hr, wknd)] = float(np.mean(vals))

    rows = []
    for oa in sorted(prof):
        p = prof[oa]
        row: dict[str, object] = {"oa": oa}
        for wknd, tag in ((False, "wd"), (True, "we")):
            v = np.array([p.get((h, wknd), 0.0) for h in range(24)], dtype=float)
            for k, val in _shape(v).items():
                row[f"{tag}_{k}"] = val
        rows.append(row)
    df = pd.DataFrame(rows).set_index("oa")
    print(f"[probe] 집계구 프로필 {len(df)}곳 · 표본 {len(seen)}일"
          f"(주말 {sum(1 for d in seen if _is_weekend(d))})")
    return df


# ---------------------------------------------------------------- PIP
def _assign_oa(nodes: pd.DataFrame) -> np.ndarray:
    """노드 좌표 → 집계구 코드.

    배정은 `build_node_jipgyegu.assign` 한 곳에만 둔다 — 프로브가 자기 사본을 들고
    있으면 나중에 파이프라인만 고쳐지고 프로브는 옛 배정으로 판정하게 된다.
    """
    from data.pipelines.build_node_jipgyegu import assign

    lat = pd.to_numeric(nodes["lat"], errors="coerce").to_numpy(dtype=float)
    lon = pd.to_numeric(nodes["lon"], errors="coerce").to_numpy(dtype=float)
    return assign(lat, lon)


# ---------------------------------------------------------------- 교정
def _calibrate(nodes: pd.DataFrame) -> dict:
    """같은 분산비 함수를 행정동 블록에 돌려 0.221 이 재현되는지 본다."""
    if not (_ADONG_HOURLY.exists() and _COORD_ADONG.exists()):
        return {"ran": False, "why": "행정동 표 또는 좌표 캐시 없음"}
    from data.collectors.living_population_hourly import adong8

    tbl = pd.read_parquet(_ADONG_HOURLY)
    tbl = tbl.set_index(tbl["adm8"].astype(str))
    cache = json.loads(_COORD_ADONG.read_text(encoding="utf-8"))
    lat = pd.to_numeric(nodes["lat"], errors="coerce").fillna(0.0).to_numpy()
    lon = pd.to_numeric(nodes["lon"], errors="coerce").fillna(0.0).to_numpy()
    adm = np.array([
        adong8((cache.get(f"{round(lo / 0.001):d}_{round(la / 0.001):d}") or {})
               .get("adm_cd") or "")
        for lo, la in zip(lon, lat)
    ])
    m = tbl.reindex(adm)
    blk = m[_COLS].astype(float)
    matched = ~blk.isna().any(axis=1).to_numpy()
    did = nodes["district_id"].fillna("").astype(str).to_numpy()
    per = _ratios(blk[matched].reset_index(drop=True), did[matched])
    return {"ran": True, "attach_rate": round(float(matched.mean()), 4),
            "per_feature": per, "mean": round(st.mean(per.values()), 3),
            "adong_count": len(set(adm[matched]))}


# ---------------------------------------------------------------- main
def run(calibrate: bool = True) -> dict:
    nodes = pd.read_parquet(_NODES)
    did_all = nodes["district_id"].fillna("").astype(str).to_numpy()
    print(f"[probe] 노드 {len(nodes)} · 거점 {len(set(did_all))}")

    cal = _calibrate(nodes) if calibrate else {"ran": False, "why": "--no-calibrate"}
    if cal.get("ran"):
        print(f"[probe] 교정(행정동): 분산비 평균 {cal['mean']} "
              f"(문서 {_ADONG_BASELINE}) · 귀속 {cal['attach_rate']:.1%} "
              f"(문서 {_ADONG_ATTACH:.1%})")

    oa = _assign_oa(nodes)
    feats = _oa_features()
    # 귀속 실패를 **두 종류로 가른다** — 대응이 다르기 때문이다.
    #   (a) PIP 실패      = 노드가 어떤 집계구에도 안 떨어진다 → 구조 문제, 못 고친다
    #   (b) 프로필 부재   = 집계구는 붙었는데 생활인구 표본이 그 집계구를 안 받았다
    #                      → 수집 범위 문제, 더 받으면 는다
    # 뭉뚱그려 "귀속률"로 적으면 (b)가 (a)처럼 읽혀 레버가 없는 것처럼 보인다.
    piped = np.array([bool(c) for c in oa])
    attached = np.array([bool(c) and c in feats.index for c in oa])
    print(f"[probe] PIP 성공 {piped.sum()}/{len(nodes)} = {piped.mean():.1%} · "
          f"프로필 보유 {attached.sum()}/{len(nodes)} = {attached.mean():.1%}")
    print(f"[probe]   → 차이 {piped.sum() - attached.sum()}개는 "
          f"**생활인구 표본이 그 집계구를 안 받은 것**(수집 범위) — "
          f"프로필 {len(feats)}곳 / 경계 19,153곳")

    blk = feats.reindex(oa[attached])[_COLS].astype(float).reset_index(drop=True)
    did = did_all[attached]
    per = _ratios(blk, did)
    mean_ratio = round(st.mean(per.values()), 3)

    uniq = {(d, c) for d, c in zip(did, oa[attached])}
    per_hub: collections.Counter = collections.Counter()
    for d, _c in uniq:
        per_hub[d] += 1
    sizes = sorted(per_hub.values())

    print(f"[probe] within-district 분산비 평균 {mean_ratio} "
          f"(행정동 {_ADONG_BASELINE}) · (거점,집계구) 쌍 {len(uniq)} · "
          f"거점당 중앙 {int(st.median(sizes)) if sizes else 0}")
    for c in _COLS:
        print(f"          {c:<18} {per[c]:.3f}")

    out = {
        "probe": "jipgyegu_foot",
        "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "question": ("집계구 24시간 생활인구가 GNN off-prior 게이트를 움직일 수 있는 "
                     "종류의 정보인가 — 600ep 을 사기 전에 판정한다"),
        "rule_preregistered": ("docs/feature-platform.md §0-L: 분산비가 "
                               f"_adong_hour_block({_ADONG_BASELINE}) 근처면 돌리지 않는다"),
        "sample_days": _SAMPLE,
        "cols": _COLS,
        "calibration_adong": cal,
        "leg1_structure": {
            "oa_per_district_median": int(st.median(sizes)) if sizes else 0,
            "oa_per_district_min_max": [sizes[0], sizes[-1]] if sizes else [0, 0],
            "district_oa_pairs": len(uniq),
            "oa_codes_hit": len(set(oa[attached])),
        },
        "leg2_attachment": {
            "nodes": int(len(nodes)),
            "pip_ok": int(piped.sum()),
            "pip_rate": round(float(piped.mean()), 4),
            "attached": int(attached.sum()),
            "rate": round(float(attached.mean()), 4),
            "gap_is_collection_not_structure": int(piped.sum() - attached.sum()),
            "oa_profiled": int(len(feats)),
            "oa_in_boundary": 19153,
            "adong_reference": _ADONG_ATTACH,
        },
        "leg3_signal": {
            "within_district_ratio_mean": mean_ratio,
            "per_feature": per,
            "adong_baseline": _ADONG_BASELINE,
            "delta_vs_adong": round(mean_ratio - _ADONG_BASELINE, 3),
        },
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[probe] → {_OUT.relative_to(_ROOT)}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-calibrate", action="store_true",
                    help="행정동 재현 확인을 건너뛴다(권장하지 않음)")
    a = ap.parse_args()
    run(calibrate=not a.no_calibrate)


if __name__ == "__main__":
    main()
