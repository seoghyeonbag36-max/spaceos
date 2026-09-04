"""[Page] 행정동 시간대별 생활인구 → **24시간 축** 산출물 (gold/page_footfall_hourly.json).

`build_page_footfall` 의 시간 축을 갈아끼우기 위한 재료다. 그쪽은 상권(TRDAR) 단위라
시간이 **6구간**으로 접혀 있는데(`resolution: "trdar"`), 생활인구는 원본이 **24시간**
이라 접지 않고 그대로 낼 수 있다.

입력: bronze/seoul/{날짜}/living_population_hourly.json (collectors/living_population_hourly)
      + silver/hub_adong.json (pipelines/build_hub_adong)
출력: gold/page_footfall_hourly.json

## 무엇이 실측이고 무엇이 근사인가

- **실측**: 행정동 단위의 시간대별 생활인구(서울시×통신 기지국 전수화). 24시간 그대로.
- **근사**: 거점 **안에서의** 분포. 원천이 행정동 집계라 거점 내부는 모른다. 거점이
  행정동 여러 개에 걸치면 `hub_adong` 의 **상업 연면적 가중**으로 섞는다.
  `resolution: "adong"` 이 이 사실을 밝힌다 — 밝히지 않으면 건물 단위 실측처럼 읽힌다.
  (`build_page_migration` 이 같은 근사를 같은 방식으로 밝힌다.)

## 평일과 주말을 왜 가르나

상권의 성격이 갈리는 축이 바로 그것이다 — 업무지구(을지로·시청)는 평일 주간에 솟고
주말에 비고, 상업지구(가로수길·홍대)는 반대다. 한 벌로 평균하면 **두 성격이 서로를
지운다.** Posting 의 `foot` 서열이 시드에 머물러 있는 것도 이 구분이 없기 때문이다.

토·일을 주말로 본다. 공휴일은 가르지 않는다 — 달력 표를 새로 들이면 그 표가 또 낡고,
28일 표본에서 공휴일 1~2일이 평일 20일 평균을 흔들 정도는 아니다.

## 왜 평균이고 중앙값이 아닌가

생활인구는 이미 기지국 전수를 집계한 값이라 개별 이상치가 없다. 날짜 간 변동(비·행사)은
있지만 20일 평균이면 충분히 눌린다. 중앙값을 쓰면 '비 온 날이 빠진 값'이 되는데, 우리가
알고 싶은 것은 **평상시 기대치**다.

실행: python -m data.pipelines.build_page_footfall_hourly
"""
from __future__ import annotations

import datetime
import json
from collections import defaultdict

from data.collectors.common import BRONZE, GOLD
from data.collectors.living_population_hourly import FILENAME, SLUG, adong8
from data.config.page_hubs import ACTIVE_HUBS
from data.pipelines.build_hub_adong import load as load_hub_adong

_OUT = GOLD / "page_footfall_hourly.json"
HOURS = [f"{h:02d}" for h in range(24)]
_VAL = "TOT_LVPOP_CO"
_HOUR = "TMZON_PD_SE"
_CODE = "ADSTRD_CODE_SE"
_DATE = "STDR_DE_ID"


def _is_weekend(yyyymmdd: str) -> bool:
    d = datetime.date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    return d.weekday() >= 5          # 5=토, 6=일


def _load_bronze() -> tuple[dict[tuple[str, str, bool], list[float]], set[str]]:
    """Bronze 전체를 훑어 (행정동, 시, 주말여부) → 값 목록. 반환: (버킷, 날짜집합)."""
    buckets: dict[tuple[str, str, bool], list[float]] = defaultdict(list)
    dates: set[str] = set()
    root = BRONZE / SLUG
    if not root.exists():
        return buckets, dates
    for day in sorted(p for p in root.iterdir() if p.is_dir()):
        f = day / FILENAME
        if not f.exists():
            continue
        try:
            rows = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            print(f"   [경고] {f.relative_to(BRONZE)} 를 못 읽었다 — 건너뜀")
            continue
        for r in rows:
            ds = str(r.get(_DATE) or "")
            if len(ds) != 8:
                continue
            hh = str(r.get(_HOUR) or "").strip()
            if not hh.isdigit():
                continue
            hh = f"{int(hh):02d}"
            if hh not in HOURS:
                continue
            try:
                v = float(r.get(_VAL))
            except (TypeError, ValueError):
                continue
            dates.add(ds)
            # Bronze 는 서울 원본 그대로라 8자리다. hub_adong 은 카카오 10자리이므로
            # 양쪽 모두 adong8 을 통과시킨다 — 한쪽만 하면 조인이 전부 빈다.
            buckets[(adong8(r.get(_CODE)), hh, _is_weekend(ds))].append(v)
    return buckets, dates


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _share(by_hour: dict[str, float | None]) -> dict[str, float]:
    """시간별 구성비 — 절대 규모가 아니라 **모양**을 비교할 때 쓴다."""
    vals = {h: v for h, v in by_hour.items() if v is not None}
    tot = sum(vals.values())
    return {h: round(v / tot, 6) for h, v in vals.items()} if tot > 0 else {}


def _peak(by_hour: dict[str, float | None]) -> dict | None:
    vals = {h: v for h, v in by_hour.items() if v is not None}
    if not vals:
        return None
    h, v = max(vals.items(), key=lambda kv: kv[1])
    lo_h, lo_v = min(vals.items(), key=lambda kv: kv[1])
    return {"hour": h, "pop": round(v, 1),
            "trough_hour": lo_h, "trough_pop": round(lo_v, 1),
            # 최번시/최한시 배수 — 이 값이 1 에 가까우면 시간 축이 무의미한 거점이다.
            "peak_trough_ratio": round(v / lo_v, 2) if lo_v else None}


def run() -> dict:
    hub_adong = load_hub_adong()
    if not hub_adong:
        raise SystemExit("silver/hub_adong.json 없음 — "
                         "먼저 `python -m data.pipelines.build_hub_adong`")
    buckets, dates = _load_bronze()
    if not buckets:
        raise SystemExit(
            f"bronze/{SLUG}/*/{FILENAME} 없음 — 먼저\n"
            "  python -m data.collectors.living_population_hourly")

    wd_dates = sorted(d for d in dates if not _is_weekend(d))
    we_dates = sorted(d for d in dates if _is_weekend(d))
    districts: dict[str, dict] = {}
    thin: list[str] = []

    for slug in ACTIVE_HUBS:
        adong = hub_adong.get(slug) or {}
        if not adong:
            continue
        out: dict[str, dict] = {}
        for label, weekend in (("weekday", False), ("weekend", True)):
            by_hour: dict[str, float | None] = {}
            for hh in HOURS:
                num, wsum = 0.0, 0.0
                for cd, meta in adong.items():
                    w = float(meta.get("weight") or 0.0)
                    m = _mean(buckets.get((adong8(cd), hh, weekend), []))
                    if m is None or w <= 0:
                        continue
                    num += w * m
                    wsum += w
                # 가중치 합으로 나눈다 — 일부 행정동이 결측이면 남은 것들의
                # 가중평균이 되어야 한다. w 합으로 안 나누면 결측이 '0명'으로 새어든다.
                by_hour[hh] = round(num / wsum, 1) if wsum > 0 else None
            covered = sum(1 for v in by_hour.values() if v is not None)
            out[label] = {"by_hour": by_hour, "hour_share": _share(by_hour),
                          "peak": _peak(by_hour), "hours_covered": covered}
            if covered < len(HOURS):
                thin.append(f"{slug}/{label}({covered}/24)")
        districts[slug] = {
            **out,
            "adong": {cd: {"nm": v.get("adm_nm"), "w": v.get("weight"),
                           "basis": v.get("weight_basis")}
                      for cd, v in adong.items()},
        }

    doc = {
        "source": "서울 생활인구(행정동·시간대) SPOP_LOCAL_RESD_DONG — data.seoul.go.kr",
        "built_from": (f"bronze/{SLUG}/*/{FILENAME} + silver/hub_adong.json"),
        "resolution": "adong",
        "hours": HOURS,
        "sample": {"dates": len(dates),
                   "weekday_dates": len(wd_dates), "weekend_dates": len(we_dates),
                   "range": [min(dates), max(dates)] if dates else None},
        "note": ("시간 축은 **원본 24시간 그대로**다(TRDAR 기반 build_page_footfall 은 "
                 "6구간으로 접힌다). 다만 값은 **행정동 단위 집계**이므로 거점 내부 "
                 "분포는 알 수 없고, 거점이 여러 행정동에 걸치면 상업 연면적 가중으로 "
                 "섞는다 — 건물·격자 단위 실측이 아니다. 토·일만 주말로 보고 공휴일은 "
                 "가르지 않는다."),
        "districts": districts,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"→ {_OUT.name}  ({_OUT.stat().st_size / 1024:.0f}KB)")
    print(f"   거점 {len(districts)}/{len(ACTIVE_HUBS)} · 날짜 {len(dates)}"
          f"(평일 {len(wd_dates)} / 주말 {len(we_dates)})")
    if thin:
        print(f"   [주의] 24시간이 안 채워진 곳 {len(thin)}건: {', '.join(thin[:6])}"
              f"{' …' if len(thin) > 6 else ''}")
    return doc


if __name__ == "__main__":
    run()
