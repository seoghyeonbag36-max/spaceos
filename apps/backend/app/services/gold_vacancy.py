"""Gold 실데이터 기반 100m 그리드 공실 집계 (Page) — 합성 그리드 대체.

지금까지 거점 공실은 `services/districts.build_cells()` 가 `sin()` 해시로 **합성**한
값이었다. 이 모듈은 같은 계약(cells/sum_stores/sum_vac/avg_vacancy)을 유지한 채 입력을
`data/gold/{slug}/page_building_master.geojson` 실측 건물로 바꾼다.
Gold 가 있는 거점(2026-08-01 기준 13곳)은 실데이터, 나머지는 기존 합성으로 폴백한다.

## 집계 규칙 — 세 가지를 모두 통과한 건물만 센다
1. **분모 근거**(`capacity_method`): `floor_ouln`(층별개요 상업층) 만. `floor_approx` 는
   지상 전체 층수 근사라 주거·사무 층까지 상가로 세어 분모가 부푼다 — 가로수길 기준
   전수 33.1% vs 24.2%.
2. **집합건물 제외**(`capacity_method == "expos_units"`): 분자가 구조적으로 비어 있다.
   상가정보가 대형 집합상가 **내부** 점포를 그 건물의 bdMgtSn 으로 귀속시키지 못해
   공실률이 78~86% 로 나온다(calibration.json 의 "알려진 한계" 항목). 건물 수로는 소수인데
   호실이 많아 **분모의 52~82%** 를 차지하는 거점이 있어, 섞으면 거점 대표값이 통째로
   무너진다 — 2026-08-01 앵커 대조에서 확인:
       seoulsup  혼합 67.0% → 일반만 19.8% (앵커 3.4%, 집합이 분모의 82%)
       ikseon    혼합 57.1% → 일반만 30.1% (앵커 8.5%, 52%)
       myeongdong 혼합 56.3% → 일반만 16.9% (앵커 5.0%, 59%)
   층·호 단위 매칭(flrNo/hoNo)이 붙기 전까지 집합건물은 집계에서 뺀다.
3. **분자 근거**(`source`): `polygon_only` 제외. 점포 매칭이 없어 `active` 가 무조건 0 →
   공실률 100% 로 고정되는 폴리곤이다.

셋 다 calibrate_vacancy.py / calibration.json 의 규칙과 같다. 규칙끼리는 독립이므로
(재빌드가 polygon_only 에 floor_ouln 을 붙일 수 있다) 각각 명시한다.

건물 폴리곤 레이어(`/heatmap/buildings`)는 제외 대상도 그대로 그린다. 거기서는 건물 한
동의 표시값이고, 여기서는 거점을 대표하는 **통계**라 기준을 다르게 둔다.

## 앵커 대조
Gold 에 calibration.json 이 있으면 그 거점의 R-ONE 중대형상가 공실률(`anchor_pct`)과
격차(`anchor_gap_pp`)를 응답에 붙인다. 우리 지표는 호실 기준·전수라 R-ONE(면적 기준·표본)
과 모집단이 달라 격차가 0 이 될 수 없다 — 절대값이 아니라 **거점 간 비교와 추세 감시**에 쓴다.

건물 폴리곤 레이어(`/heatmap/buildings`)는 floor_approx 도 그대로 그린다. 거기서는
건물 한 동의 표시값이고, 여기서는 거점을 대표하는 **통계**라 기준을 다르게 둔다.

## 그리드 격자
셀 크기(dlat/dlng)와 원점(bb 남서 모서리)은 시드 grid 정의를 그대로 쓴다 — 합성
시절과 같은 격자에 정렬돼야 프론트 렌더·비교가 어긋나지 않는다. 다만 셀 인덱스는
bb 밖으로 나가면 음수/초과가 되게 두어, 수집 반경이 시드 bb 를 벗어난 건물도
버리지 않는다(거점별 수집 반경은 data/config/page_hubs.py 에서 따로 정해진다).
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

from app.services.building_vacancy import _resolve, load_master

# 대표 집계에 쓰는 capacity(분모) 근거. expos_units(집합건물)는 분자가 구조적으로
# 비어 있어 뺀다 — 모듈 상단 2번 참조. floor_approx 는 분모가 부푼다 — 1번 참조.
_COUNTED_METHODS = {"floor_ouln"}
# active(분자) 근거가 없는 매칭 — 점포가 붙지 않아 공실률이 100% 로 고정된다
_EXCLUDED_SOURCES = {"polygon_only"}

_GOLD_DIR = Path(__file__).resolve().parents[4] / "data" / "gold"
_TTL_SECONDS = 300.0
_anchor_cache: dict[str, Any] = {}


def _centroid(ring: list[list[float]]) -> tuple[float, float]:
    """폴리곤 외곽 링([lng, lat] 순)의 정점 평균 → (lat, lng).

    건물 footprint 는 수십 m 규모라 100m 셀 배정에는 정점 평균으로 충분하다
    (면적가중 무게중심까지 갈 이유가 없다). 닫힌 링의 마지막 중복 정점은 뺀다.
    """
    pts = ring[:-1] if len(ring) > 2 and ring[0] == ring[-1] else ring
    n = len(pts)
    return sum(p[1] for p in pts) / n, sum(p[0] for p in pts) / n


def is_available(district_id: str) -> bool:
    """이 거점에 Gold 건물 마스터가 있는가."""
    return load_master(district_id) is not None


def anchor_of(district_id: str) -> float | None:
    """거점의 R-ONE 중대형상가 공실률(%). calibration.json 이 없으면 None.

    calibrate_vacancy.py 가 bronze 의 R-ONE 최신 분기에서 뽑아 기록한 값이다.
    파이프라인 재실행이 바로 반영되도록 mtime 이 아니라 TTL 캐시로 둔다(파일이 작다).
    """
    slug = _resolve(district_id)
    now = time.monotonic()
    hit = _anchor_cache.get(slug)
    if hit and now - hit["at"] < _TTL_SECONDS:
        return hit["pct"]
    path = _GOLD_DIR / slug / "calibration.json"
    pct = None
    if path.exists():
        pct = json.loads(path.read_text(encoding="utf-8")).get("anchor_pct")
    _anchor_cache[slug] = {"at": now, "pct": pct}
    return pct


def build_cells(district_id: str, grid: dict) -> dict | None:
    """Gold 건물을 100m 셀로 집계. Gold 미보유·집계 대상 0이면 None(→ 합성 폴백).

    반환은 합성 build_cells 와 동일 계약 + Gold 전용 메타(source/capacity/buildings*/앵커).
    """
    fc = load_master(district_id)
    if fc is None:
        return None

    bb, dlat, dlng = grid["bb"], grid["dlat"], grid["dlng"]
    agg: dict[tuple[int, int], dict] = {}
    buildings_total = len(fc["features"])
    buildings_used = 0
    excluded_mall = 0

    for feat in fc["features"]:
        props = feat["properties"]
        capacity = props.get("capacity") or 0
        if props.get("capacity_method") == "expos_units":
            excluded_mall += 1          # 집합건물 — 분자 미매칭이라 대표 집계에서 뺀다
            continue
        if capacity <= 0 or props.get("capacity_method") not in _COUNTED_METHODS:
            continue
        if props.get("source") in _EXCLUDED_SOURCES:
            continue
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Polygon" or not geom.get("coordinates"):
            continue
        lat, lng = _centroid(geom["coordinates"][0])
        key = (math.floor((lat - bb["s"]) / dlat), math.floor((lng - bb["w"]) / dlng))
        cell = agg.setdefault(key, {"cap": 0, "act": 0, "n": 0})
        cell["cap"] += capacity
        # 파이프라인이 이미 occupancy 를 1.0 으로 클램프하지만(active>capacity 0건),
        # 재빌드 산출물이 규칙을 어겨도 음수 공실이 새지 않게 여기서도 막는다.
        cell["act"] += min(props.get("active") or 0, capacity)
        cell["n"] += 1
        buildings_used += 1

    if not agg:
        return None

    cells: list[dict] = []
    sum_capacity = sum_stores = 0
    for (i, j), c in sorted(agg.items()):
        lat, lng = bb["s"] + i * dlat, bb["w"] + j * dlng
        vac_n = c["cap"] - c["act"]
        cells.append({
            "i": i, "j": j, "lat": round(lat, 6), "lng": round(lng, 6),
            "c_lat": round(lat + dlat / 2, 6), "c_lng": round(lng + dlng / 2, 6),
            "v": round(vac_n / c["cap"] * 100, 2),
            "stores": c["act"], "vac_n": vac_n,
            "dlat": dlat, "dlng": dlng,
            "capacity": c["cap"], "buildings": c["n"],
        })
        sum_capacity += c["cap"]
        sum_stores += c["act"]

    sum_vac = sum_capacity - sum_stores
    avg = round(sum_vac / sum_capacity * 100, 2)
    anchor = anchor_of(district_id)
    return {
        "cells": cells,
        "sum_stores": sum_stores,
        "sum_vac": sum_vac,
        # 분모는 호실 수(capacity)다. 합성 시절 sum_stores 는 '점포 수'였고 분모도
        # 그것이었지만, 실데이터에서는 영업 점포(active) / 총 호실(capacity) 이 맞다.
        "avg_vacancy": avg,
        "capacity": sum_capacity,
        "buildings": buildings_used,
        "buildings_total": buildings_total,
        "precision_pct": round(buildings_used / buildings_total * 100, 1),
        "excluded_mall": excluded_mall,
        "anchor_pct": anchor,
        "anchor_gap_pp": round(avg - anchor, 1) if anchor is not None else None,
        "source": "gold",
    }
