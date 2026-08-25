"""[Posting] 유닛 단위 `foot` — 집계구 생활인구로 승격 (막힘 5 해소).

## 무엇이 달라지나

종전 `foot` 서열의 원천은 **최근접 상권 유동총량**이었다(`posting_inputs._unit_trdar_flpop`).
거점당 상권이 1~9곳(중앙 3)뿐이라 경계가 굵고, 상권이 1곳인 거점은 아예 못 갈랐다.

집계구는 거점당 중앙 **6개**(1~11)라 입도가 2배다. 종전에 "원리적으로 못 가른다"던
`nokdu`(상권 1곳 → 집계구 6개) · `euljiro`(유닛이 300m 안 → 집계구 7개)가 갈린다.

## 표본을 왜 1주로 잡았나 — 재고 골랐다 (2026-08-25)

| 축 | 실측 | 판정 |
|---|---|---|
| 계절 | 2025-10-24(금) · 2026-04-28(화) · 2026-07-01(수) 거점 내 서열 ρ중앙 **0.976~1.000** · ρ<0.5 인 거점 **0** | 계절 보정 **불필요** |
| 일간 | 같은 주 21쌍 ρ중앙의 중앙 **1.0000** · 최소 **0.9594** | 표본 크기 **무관** |
| 수렴 | 앞 1일 vs 7일 ρ중앙 **1.0000** · 5일이면 평균 **0.9977** | 1개월은 **낭비** |
| **평일/주말** | ρ중앙 0.964 지만 **2거점이 ρ<0.5** — `cityhall` 은 **−1.00 (완전 역전)** | **주말이 표본에 있어야 한다** |

즉 1주가 필요한 이유는 표본 크기가 아니라 **평일/주말 구조 차이 하나**다. 그래서
7일(평일 5 · 주말 2)을 받는다. 토 vs 일은 ρ중앙 1.0000 이라 주말 2일로 족하다.

`cityhall` 은 잡음이 아니다 — 집계구 3개의 주말비가 0.37 / 0.58 / 0.69 로 단조라
서열이 정확히 뒤집힌다(도심 업무지구가 주말에 비는 정도가 자리마다 다르다).

## 무엇을 싣나

`foot_value` 는 **7일 가중평균**(평일 5 + 주말 2)이다. 지금 `foot` 스키마가 등급 하나라
그렇게 한다. 다만 `weekday` · `weekend` 를 **함께 싣는다** — 위 역전이 산출물에서
보이지 않으면 다음 사람이 못 찾는다.

⚠ 생활인구 계열은 **2026-07-31 로 생산 종료**(국가표준격자 250m 전환). 후속은 자치구
단위라 더 거칠다. 이 값은 그 시점까지의 **대표값**이며 갱신되지 않는다.

실행: python -m data.pipelines.build_unit_foot
"""
from __future__ import annotations

import collections
import datetime
import json
import statistics as st
from pathlib import Path

from data.collectors.common import DATA_ROOT, GOLD

_ASSIGN = DATA_ROOT / "silver" / "unit_jipgyegu.json"
_BRONZE = DATA_ROOT / "bronze" / "seoul"
_OUT = GOLD / "platform_unit_foot.json"

# 주간대(10~20시) 평균을 쓴다. 야간을 섞으면 거주인구가 유동 서열을 덮는다.
_DAY_HOURS = range(10, 21)
_SAMPLE = [f"2026-07-0{i}" for i in range(1, 8)]      # 수목금토일월화 — 완전한 한 주


def _is_weekend(day: str) -> bool:
    return datetime.date.fromisoformat(day).weekday() >= 5


def _oa_profile(days: list[str]) -> dict[str, dict]:
    """집계구 → {weekday, weekend, hours} (주간대 평균 · 24시간 프로파일)."""
    wd: dict[str, list[float]] = collections.defaultdict(list)
    we: dict[str, list[float]] = collections.defaultdict(list)
    hr: dict[str, dict[int, list[float]]] = collections.defaultdict(
        lambda: collections.defaultdict(list))
    seen = []
    for day in days:
        p = _BRONZE / day / "living_population_jipgyegu.json"
        if not p.exists():
            continue
        seen.append(day)
        wknd = _is_weekend(day)
        for r in json.loads(p.read_text(encoding="utf-8")):
            if r["pop"] is None:
                continue
            hr[r["oa"]][r["hour"]].append(r["pop"])
            if r["hour"] in _DAY_HOURS:
                (we if wknd else wd)[r["oa"]].append(r["pop"])
    if not seen:
        raise FileNotFoundError(
            f"{_BRONZE} 에 표본이 없다 — "
            f"`python -m data.collectors.living_population_jipgyegu --month 202607 --days 7`")
    out = {}
    for oa in set(wd) | set(we):
        a, b = wd.get(oa), we.get(oa)
        out[oa] = {
            "weekday": round(st.mean(a), 1) if a else None,
            "weekend": round(st.mean(b), 1) if b else None,
            "hours": {str(h): round(st.mean(v), 1) for h, v in sorted(hr[oa].items())},
        }
    return out, seen


def run() -> dict:
    assign = json.loads(_ASSIGN.read_text(encoding="utf-8"))
    prof, days = _oa_profile(_SAMPLE)
    n_wd = sum(1 for d in days if not _is_weekend(d))
    n_we = len(days) - n_wd

    units: dict[str, dict] = {}
    for key, v in assign["units"].items():
        p = prof.get(v["oa_code"])
        if not p or p["weekday"] is None:
            continue
        # 7일 가중평균 — 평일 n_wd · 주말 n_we
        we = p["weekend"] if p["weekend"] is not None else p["weekday"]
        blended = (p["weekday"] * n_wd + we * n_we) / (n_wd + n_we)
        units[key] = {
            "district_id": v["district_id"], "unit_id": v["unit_id"],
            "oa_code": v["oa_code"],
            "foot_value": round(blended, 1),
            "weekday": p["weekday"], "weekend": p["weekend"],
            "weekend_ratio": round(we / p["weekday"], 3) if p["weekday"] else None,
        }

    per = collections.defaultdict(set)
    for u in units.values():
        per[u["district_id"]].add(u["oa_code"])
    resolvable = sum(1 for s in per.values() if len(s) > 1)

    out = {
        "source": ("서울 열린데이터광장 OA-14979 집계구 단위 생활인구(내국인) × "
                   "SGIS 과거집계구 2016 4Q 경계 PIP 배정"),
        "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "sample_days": days,
        "sample_weekday": n_wd, "sample_weekend": n_we,
        "day_hours": [min(_DAY_HOURS), max(_DAY_HOURS)],
        "note": (
            "foot_value 는 주간대(10~20시) 생활인구의 7일 가중평균이다. "
            "표본을 1주로 잡은 이유는 크기가 아니라 **평일/주말 구조 차이**다 — 계절 ρ 0.976~1.000, "
            "일간 ρ 최소 0.959 로 둘 다 서열을 안 바꾸지만, cityhall 은 평일↔주말 서열이 "
            "완전히 뒤집힌다(ρ=−1.00, 주말비 0.37/0.58/0.69). 그래서 weekday·weekend 를 "
            "함께 싣는다. "
            "⚠ 이 계열은 2026-07-31 로 생산 종료(국가표준격자 250m 전환) — 갱신되지 않는 대표값이다."
        ),
        "stats": {
            "units": len(units),
            "districts": len(per),
            "districts_resolvable": resolvable,
            "oa_per_district_median": sorted(len(s) for s in per.values())[len(per) // 2],
        },
        "units": units,
    }
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    o = run()
    s = o["stats"]
    print(f"[unit-foot] 유닛 {s['units']} · 거점 {s['districts']} → {_OUT.name}")
    print(f"  표본 {len(o['sample_days'])}일 (평일 {o['sample_weekday']} · 주말 {o['sample_weekend']})")
    print(f"  거점당 집계구 중앙 {s['oa_per_district_median']} · 서열이 갈리는 거점 "
          f"{s['districts_resolvable']}/{s['districts']}")
    wr = [u["weekend_ratio"] for u in o["units"].values() if u["weekend_ratio"]]
    print(f"  주말비 중앙 {st.median(wr):.2f} (최소 {min(wr):.2f} · 최대 {max(wr):.2f})")


if __name__ == "__main__":
    main()
