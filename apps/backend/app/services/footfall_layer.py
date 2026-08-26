"""Page 유동·밀도 레이어 — TRDAR 상권 실측을 공실 격자에 얹는다.

## 무엇을 고치는가

`MapShell` 의 유동인구 히트맵은 `Math.random()` 으로 만든 점 120개였다. 시간
슬라이더를 움직여도 입력을 보지 않으니 아무 의미가 없었다. 밀도 레이어는 엔드포인트
자체가 없어 "데이터 연동 예정" 문구만 떠 있었다. 재료는 이미 저장소 안에 있었다 —
TRDAR 상권 190곳(54거점 전부)의 유동총량·시간대 구성비·점포수·면적.

## 격자에 얹는 방식은 rent_layer 와 같다

셀마다 **최근접 상권**의 값을 얹는다. 공실·임대 레이어와 같은 격자를 쓰므로 네 레이어가
같은 눈금 위에 놓인다.

## ⚠ 무엇이 실측이고 무엇이 근사인지 반드시 함께 내려보낸다

TRDAR 은 **상권 단위 집계**다. 상권 안에서 어디가 더 붐비는지는 원천에 없다. 그래서
격자 값은 "그 셀의 실측"이 아니라 "그 셀이 속한 상권의 값"이다. 응답의
`resolution: "trdar"` · `trdar_count` 와 범례가 이걸 밝힌다 — 밝히지 않으면 격자
단위 실측처럼 읽히고, 그건 우리가 다른 레이어에서 계속 경계해 온 실패 양식이다.

거점당 상권이 1~9곳(중앙 3)이라 **점이 성기다.** 예전 샘플이 만들던 매끈한 히트맵보다
거칠게 보이지만, 매끄러움은 데이터가 아니라 난수가 만들던 것이었다.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from app.services import districts

_GOLD = Path(__file__).resolve().parents[4] / "data" / "gold"
_SRC = _GOLD / "platform_page_footfall.json"
# 생활인구(행정동 × 24시간). 있으면 시간 축을 6구간 → 24시간으로 갈아끼운다.
_HOURLY_SRC = _GOLD / "page_footfall_hourly.json"
# 생활인구(**집계구** × 24시간). 있으면 공간 축까지 상권 → 집계구로 올린다.
_JIPGYEGU_SRC = _GOLD / "page_footfall_jipgyegu.json"

# 시간대 6구간 — TRDAR 원천의 눈금. Program 수요신호(§0-C)와 같은 자를 쓴다.
TMZONS = ["00_06", "06_11", "11_14", "14_17", "17_21", "21_24"]
_TMZON_LABEL = {
    "00_06": "00~06시", "06_11": "06~11시", "11_14": "11~14시",
    "14_17": "14~17시", "17_21": "17~21시", "21_24": "21~24시",
}
# 시각(0~23) → 시간대 구간. 슬라이더가 시(hour) 단위라 구간으로 접는다.
_HOUR_BAND = ([("00_06")] * 6 + ["06_11"] * 5 + ["11_14"] * 3
              + ["14_17"] * 3 + ["17_21"] * 4 + ["21_24"] * 3)


def band_of_hour(hour: int) -> str:
    """0~23 시각을 TRDAR 시간대 구간으로. 범위 밖이면 낮 시간대로 접는다."""
    if not isinstance(hour, int) or not 0 <= hour <= 23:
        return "11_14"
    return _HOUR_BAND[hour]


@lru_cache(maxsize=1)
def _load() -> dict:
    """산출물 로드. 없으면 빈 dict — **0 으로 채우지 않는다.**

    빠진 것을 0 으로 채우면 "사람이 없는 상권"이 되어 거짓이 화면에 나간다.
    없으면 레이어를 통째로 내리는 쪽이 맞다(호출부가 None 을 404 로 바꾼다).
    """
    if not _SRC.exists():
        return {}
    try:
        return json.loads(_SRC.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=1)
def _load_hourly() -> dict:
    """생활인구 24시간 산출물(`page_footfall_hourly.json`). 없으면 빈 dict.

    `_load()` 와 같은 원칙 — 없는 것을 0 으로 채우지 않는다. 여기서 빈 dict 는
    "시간 축을 6구간에서 24시간으로 못 바꾼다" 는 뜻이고, 호출부는 TRDAR 구간으로
    물러난다(레이어를 내리지는 않는다 — 공간 정보는 그대로 유효하다).
    """
    if not _HOURLY_SRC.exists():
        return {}
    try:
        return json.loads(_HOURLY_SRC.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def hourly_share(district_id: str, hour: int,
                 daytype: str = "weekday") -> float | None:
    """그 거점·그 시각의 **일 대비 구성비**(24시간 합 = 1). 없으면 None.

    왜 구성비인가: 셀의 공간 서열은 TRDAR 유동총량이 만들고, 시간 축만 생활인구로
    갈아끼운다. 절대 인원을 그대로 쓰면 행정동 값(수만 명)이 상권 값을 덮어써서
    **거점 안의 공간 차이가 사라진다** — 그건 시간 축을 얻고 공간을 잃는 거래다.

    ⚠ 6구간 구성비(합 1/6구간 ≈ 0.17)와 24시간 구성비(≈ 0.04)는 눈금이 달라 셀
      절대값이 약 4배 작아진다. 프론트가 응답의 min/max 로 재정규화하므로 색상은
      그대로다(MapShell: `(c.v - min) / span`). 응답의 `share_basis` 가 어느 눈금인지
      밝힌다 — 두 눈금의 값을 나란히 비교하면 안 된다.
    """
    if not isinstance(hour, int) or not 0 <= hour <= 23:
        return None
    d = ((_load_hourly().get("districts") or {}).get(district_id) or {})
    prof = d.get("weekend" if daytype == "weekend" else "weekday") or {}
    v = (prof.get("hour_share") or {}).get(f"{hour:02d}")
    return float(v) if v is not None else None


@lru_cache(maxsize=1)
def _load_jipgyegu() -> dict:
    """집계구 24시간 산출물(`page_footfall_jipgyegu.json`). 없으면 빈 dict.

    `_load()` 와 같은 원칙 — 없는 것을 0 으로 채우지 않는다. 여기서 빈 dict 는
    "공간 축을 상권에서 집계구로 못 올린다" 는 뜻이고, 호출부는 종전 상권 경로로
    물러난다(레이어를 내리지는 않는다).
    """
    if not _JIPGYEGU_SRC.exists():
        return {}
    try:
        return json.loads(_JIPGYEGU_SRC.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def jipgyegu_of(district_id: str) -> dict | None:
    """그 거점의 집계구 배정(셀 → 집계구). 산출물이 그 거점을 **전부** 덮을 때만 있다.

    부분 커버는 산출물 단계에서 이미 걸러진다 — 한 화면에서 어떤 셀은 집계구, 어떤
    셀은 상권 값을 쓰면 색은 그럴듯한데 셀 간 비교가 거짓이 된다.
    """
    d = (_load_jipgyegu().get("districts") or {}).get(district_id)
    return d or None


def clear_cache() -> None:
    _load.cache_clear()
    _load_hourly.cache_clear()
    _load_jipgyegu.cache_clear()


def trdars_of(district_id: str) -> list[dict]:
    return list((_load().get("districts") or {}).get(district_id) or [])


def _dist_m(a: float, b: float, c: float, d: float) -> float:
    """rent_layer._dist_m 과 같은 근사(위도 111km/도, 경도 88.3km/도 @ 서울)."""
    dy = (a - c) * 111000
    dx = (b - d) * 88300
    return math.sqrt(dx * dx + dy * dy)


def _nearest(cell: dict, trdars: list[dict]) -> dict:
    return min(trdars, key=lambda t: _dist_m(cell["c_lat"], cell["c_lng"],
                                             t["lat"], t["lng"]))


def _grid(district_id: str) -> list[dict] | None:
    hm = districts.get_vacancy_heatmap(district_id)
    return hm["cells"] if hm else None


def _cell_base(cell: dict, v: float | None) -> dict:
    return {
        "i": cell["i"], "j": cell["j"],
        "lat": cell["lat"], "lng": cell["lng"],
        "c_lat": cell["c_lat"], "c_lng": cell["c_lng"],
        "dlat": cell["dlat"], "dlng": cell["dlng"],
        "v": v,
    }


def _footfall_jipgyegu(district_id: str, jg: dict, cells: list[dict],
                       hour: int, daytype: str) -> dict | None:
    """집계구 경로 — 셀 값 = 그 셀이 속한 **집계구의 그 시각 생활인구**.

    상권 경로와 결정적으로 다른 점은 **곱셈이 없다는 것**이다. 종전에는 공간(상권
    총량)과 시간(행정동 구성비)이 서로 다른 원천이라 둘을 곱해 붙였고, 그래서 거점
    안의 시간 차이를 표현할 수 없었다(행정동이 거점당 1~2개였다). 집계구는 공간과
    시간이 한 표에서 나오므로 거점 내부에서 시각에 따라 서열이 바뀐다.

    ⚠ 값의 눈금이 상권 경로와 다르다 — 상권 경로는 `명/일 × 구성비`, 이쪽은 시각별
    **생활인구 절대값**이다. `share_basis: null` 과 `unit` 이 그걸 밝히고, 프론트는
    응답의 min/max 로 재정규화하므로 색은 정상이다. **두 경로의 v 를 직접 비교하면
    안 된다.**

    산출물이 그 셀을 안 담으면 통째로 None 을 돌려 상권 경로로 물러난다 — 일부만
    집계구로 채우면 같은 화면의 두 셀이 서로 다른 눈금이 된다.
    """
    if not isinstance(hour, int) or not 0 <= hour <= 23:
        hour = 12
    daytype = "weekend" if daytype == "weekend" else "weekday"
    key = "we" if daytype == "weekend" else "wd"
    oa_tbl = _load_jipgyegu().get("oa") or {}
    cmap = jg.get("cells") or {}

    vals, out = [], []
    for cell in cells:
        oa = cmap.get(f"{cell['i']}|{cell['j']}")
        prof = oa_tbl.get(oa) if oa else None
        if not prof:
            return None
        v = round(float((prof.get(key) or [0.0] * 24)[hour]), 1)
        vals.append(v)
        c = _cell_base(cell, v)
        c["oa"] = oa
        out.append(c)

    doc = _load_jipgyegu()
    return {
        "district": district_id,
        "footfall_source": "flpop_jipgyegu",
        "resolution": "jipgyegu",
        "oa_count": jg.get("oa_count") or len(set(cmap.values())),
        # 상권 경로와 필드 모양을 맞춘다 — 프론트가 한 타입으로 받는다. 집계구
        # 경로에서 상권은 안 쓰이므로 0 이다(‘상권이 없다’가 아니라 ‘안 썼다’).
        "trdar_count": 0,
        "hour": hour,
        "band": band_of_hour(hour),
        "band_label": _TMZON_LABEL[band_of_hour(hour)],
        "time_source": "jipgyegu_hourly",
        "daytype": daytype,
        # 구성비를 곱하지 않는다 — 곱할 것이 없다는 뜻으로 null 을 싣는다.
        "share_basis": None,
        "hour_share": None,
        "unit": "명(시각 생활인구)",
        "min": min(vals) if vals else 0.0,
        "max": max(vals) if vals else 0.0,
        "note": ("집계구 단위 생활인구를 격자에 얹은 값이다 — 공간·시간이 같은 "
                 "원천이라 거점 내부의 시간 차이가 표현된다. ⚠ 그래도 격자 실측은 "
                 "아니다: 집계구는 100m 격자보다 크고(면적 중앙 약 22,000㎡), 셀 "
                 "값은 그 셀이 속한 구획의 값이다. 표본은 "
                 f"{doc.get('sample_weekday', 0)}평일·{doc.get('sample_weekend', 0)}주말."),
        "cells": out,
    }


def footfall_heatmap(district_id: str, hour: int = 12,
                     daytype: str = "weekday") -> dict | None:
    """시간대별 유동인구를 공실 격자에 얹는다.

    셀 값 = (그 셀 최근접 상권의 유동총량) × (해당 시각의 구성비).

    구성비의 출처가 둘이다 — **공간은 TRDAR, 시간은 생활인구**로 갈랐다:

      - `adong_hourly`: `gold/page_footfall_hourly.json` 이 이 거점을 담고 있으면
        **행정동 × 24시간** 구성비를 쓴다. 원본 눈금이 시(hour)라 접지 않는다.
      - `trdar_band`: 없으면 TRDAR **6구간**으로 물러난다(종전 동작).

    어느 쪽이 돌았는지는 응답의 `time_source` 가 밝힌다. 두 눈금은 절대값 스케일이
    다르므로(24시간 구성비가 약 4배 작다) `share_basis` 도 함께 싣는다 — 프론트는
    응답의 min/max 로 재정규화하니 색상은 같지만, **두 응답의 v 를 직접 비교하면
    안 된다.**

    시간 축이 왜 중요한가: 구성비는 시각에 따라 상권 간 서열까지 바꾼다. 총량만
    쓰면 슬라이더가 밝기만 바꾸는 장식이 된다(2026-08-23 이전 상태).
    """
    cells = _grid(district_id)
    if cells is None:
        return None

    jg = jipgyegu_of(district_id)
    if jg:
        doc = _footfall_jipgyegu(district_id, jg, cells, hour, daytype)
        if doc is not None:
            return doc

    trdars = trdars_of(district_id)
    if not trdars:
        return None

    band = band_of_hour(hour)
    daytype = "weekend" if daytype == "weekend" else "weekday"
    h_share = hourly_share(district_id, hour, daytype)
    use_hourly = h_share is not None

    vals = []
    out = []
    for cell in cells:
        t = _nearest(cell, trdars)
        # 시간 구성비만 갈아끼운다. 공간(어느 상권이 큰가)은 TRDAR 총량이 그대로 만든다.
        share = h_share if use_hourly else float((t.get("tmzon") or {}).get(band) or 0.0)
        v = round(float(t.get("flpop_tot") or 0.0) * share, 1)
        vals.append(v)
        c = _cell_base(cell, v)
        c["trdar"] = t["nm"]
        out.append(c)

    doc = {
        "district": district_id,
        # ⚠ 이 두 필드는 **공간** 해상도다. 시간 축이 생활인구로 바뀌어도 공간은
        #   여전히 상권 단위이므로 값을 바꾸지 않는다(프론트 TS 가 리터럴로 받는다).
        "footfall_source": "trdar",
        "resolution": "trdar",
        "trdar_count": len(trdars),
        "hour": hour,
        "band": band,
        "band_label": _TMZON_LABEL[band],
        "time_source": "adong_hourly" if use_hourly else "trdar_band",
        "daytype": daytype,
        "share_basis": "hour24" if use_hourly else "band6",
        "hour_share": round(h_share, 6) if use_hourly else None,
        "unit": "명/일(시간 배분)" if use_hourly else "명/일(시간대 배분)",
        "min": min(vals) if vals else 0.0,
        "max": max(vals) if vals else 0.0,
        "note": ("상권 단위 집계를 격자에 얹은 값이다 — 셀마다 최근접 상권의 값을 "
                 "쓴다. 격자 단위 실측이 아니다."
                 + (" 시간 배분은 생활인구(행정동 × 24시간) 실측이고 평일·주말이 "
                    "갈린다 — 시간 축은 접히지 않았지만, 행정동 집계라 거점 내부의 "
                    "시간 차이는 알 수 없다." if use_hourly else
                    " 시간 배분은 TRDAR 6구간이다 — 생활인구 24시간 산출물이 이 "
                    "거점을 담으면 그쪽으로 바뀐다.")),
        "cells": out,
    }
    return doc


def _density_jipgyegu(district_id: str, jg: dict,
                      cells: list[dict]) -> dict | None:
    """유동인구 밀도 — 집계구의 **24시간 평균 생활인구 ÷ 폴리곤 면적**.

    ⚠ 상권 경로와 **분자의 정의가 다르다**: 상권판 `flpop_per_1k_m2` 는 일 총량
    기준이고 이쪽은 24시간 평균(= 어느 시각에 평균 몇 명이 있나)이다. 절대값이
    한 자릿수 이상 차이 나므로 `density_basis` 로 어느 쪽인지 밝힌다 — 두 응답의
    v 를 나란히 놓으면 안 된다.

    평일·주말은 표본 일수로 가중평균한다. 하나만 쓰면 업무지구/상업지구 중 한쪽이
    체계적으로 과대평가된다(`cityhall` 은 주말비가 0.24~0.69 로 갈린다).
    """
    doc = _load_jipgyegu()
    oa_tbl = doc.get("oa") or {}
    cmap = jg.get("cells") or {}
    n_wd = int(doc.get("sample_weekday") or 0)
    n_we = int(doc.get("sample_weekend") or 0)
    if n_wd + n_we <= 0:
        return None

    vals, out = [], []
    for cell in cells:
        oa = cmap.get(f"{cell['i']}|{cell['j']}")
        prof = oa_tbl.get(oa) if oa else None
        area = float((prof or {}).get("area_m2") or 0.0)
        if not prof or area <= 0:
            return None
        wd = sum(prof.get("wd") or []) / 24.0
        we = sum(prof.get("we") or []) / 24.0
        mean_pop = (wd * n_wd + we * n_we) / (n_wd + n_we)
        v = round(mean_pop / area * 1000.0, 2)
        vals.append(v)
        c = _cell_base(cell, v)
        c["oa"] = oa
        out.append(c)

    return {
        "district": district_id,
        "density_source": "flpop_jipgyegu",
        "resolution": "jipgyegu",
        "oa_count": jg.get("oa_count") or len(set(cmap.values())),
        "trdar_count": 0,
        "metric": "flpop",
        "density_basis": "flpop_mean24_per_1k_m2",
        "unit": "명/1,000㎡ (24시간 평균)",
        "label": "유동인구 밀도",
        "min": min(vals) if vals else 0.0,
        "max": max(vals) if vals else 0.0,
        "note": ("집계구 단위다(상주인구가 아니라 **유동인구** 기준). 분자는 24시간 "
                 "평균 생활인구를 평일·주말 표본으로 가중한 값이고, 분모는 집계구 "
                 "폴리곤 면적이다. ⚠ 상권 경로(일 총량 기준)와 눈금이 달라 값을 "
                 "직접 비교할 수 없다 — `density_basis` 를 볼 것."),
        "cells": out,
    }


def density_heatmap(district_id: str, metric: str = "flpop") -> dict | None:
    """상권 밀도(유동인구 또는 점포)를 같은 격자에 얹는다.

    `metric="flpop"` 은 유동인구 밀도(명/1,000㎡), `"stor"` 는 점포 밀도다.
    화면 라벨이 '인구밀도'였는데 우리가 가진 것은 **유동인구** 밀도다 — 상주인구가
    아니므로 그렇게 부르지 않는다.
    """
    key = "stor_per_1k_m2" if metric == "stor" else "flpop_per_1k_m2"
    cells = _grid(district_id)
    if cells is None:
        return None

    # ⚠ 점포 밀도는 올리지 않는다 — 집계구 단위 점포수 원천이 없다. 유동인구 밀도만
    #   집계구로 가고, 그래서 두 metric 의 `resolution` 이 서로 다를 수 있다.
    if metric != "stor":
        jg = jipgyegu_of(district_id)
        if jg:
            doc = _density_jipgyegu(district_id, jg, cells)
            if doc is not None:
                return doc

    trdars = [t for t in trdars_of(district_id) if t.get(key) is not None]
    if not trdars:
        return None

    vals, out = [], []
    for cell in cells:
        t = _nearest(cell, trdars)
        v = float(t[key])
        vals.append(v)
        c = _cell_base(cell, v)
        c["trdar"] = t["nm"]
        out.append(c)

    return {
        "district": district_id,
        "density_source": "trdar",
        "resolution": "trdar",
        "trdar_count": len(trdars),
        "metric": "stor" if metric == "stor" else "flpop",
        "unit": "점포/1,000㎡" if metric == "stor" else "명/1,000㎡",
        "label": "점포 밀도" if metric == "stor" else "유동인구 밀도",
        "min": min(vals) if vals else 0.0,
        "max": max(vals) if vals else 0.0,
        "note": ("상권 단위 집계다(상주인구가 아니라 **유동인구** 기준). 셀마다 "
                 "최근접 상권 값을 쓴다."),
        "cells": out,
    }
