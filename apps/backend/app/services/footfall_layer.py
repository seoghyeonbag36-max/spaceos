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


def clear_cache() -> None:
    _load.cache_clear()


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


def footfall_heatmap(district_id: str, hour: int = 12) -> dict | None:
    """시간대별 유동인구를 공실 격자에 얹는다.

    셀 값 = (그 셀 최근접 상권의 유동총량) × (그 상권의 해당 시간대 구성비).
    구성비는 **그 상권 안에서의 비율**이라 시간대를 바꾸면 상권 간 서열도 바뀐다 —
    총량만 쓰면 슬라이더가 밝기만 바꾸는 장식이 된다.
    """
    trdars = trdars_of(district_id)
    cells = _grid(district_id)
    if not trdars or cells is None:
        return None

    band = band_of_hour(hour)
    vals = []
    out = []
    for cell in cells:
        t = _nearest(cell, trdars)
        share = float((t.get("tmzon") or {}).get(band) or 0.0)
        v = round(float(t.get("flpop_tot") or 0.0) * share, 1)
        vals.append(v)
        c = _cell_base(cell, v)
        c["trdar"] = t["nm"]
        out.append(c)

    return {
        "district": district_id,
        "footfall_source": "trdar",
        "resolution": "trdar",
        "trdar_count": len(trdars),
        "hour": hour,
        "band": band,
        "band_label": _TMZON_LABEL[band],
        "unit": "명/일(시간대 배분)",
        "min": min(vals) if vals else 0.0,
        "max": max(vals) if vals else 0.0,
        "note": ("상권 단위 집계를 격자에 얹은 값이다 — 셀마다 최근접 상권의 값을 "
                 "쓴다. 격자 단위 실측이 아니다."),
        "cells": out,
    }


def density_heatmap(district_id: str, metric: str = "flpop") -> dict | None:
    """상권 밀도(유동인구 또는 점포)를 같은 격자에 얹는다.

    `metric="flpop"` 은 유동인구 밀도(명/1,000㎡), `"stor"` 는 점포 밀도다.
    화면 라벨이 '인구밀도'였는데 우리가 가진 것은 **유동인구** 밀도다 — 상주인구가
    아니므로 그렇게 부르지 않는다.
    """
    key = "stor_per_1k_m2" if metric == "stor" else "flpop_per_1k_m2"
    trdars = [t for t in trdars_of(district_id) if t.get(key) is not None]
    cells = _grid(district_id)
    if not trdars or cells is None:
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
