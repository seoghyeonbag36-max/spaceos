"""Platform·GNN 업종 추천 서빙 — gold/platform_industry_recommend.json 직접 로드.

ml/training/train_gnn.py 가 학습 후 전 노드의 Top-K 업종 확률을 배치로 떨어뜨린다.
Vercel 서버리스에 torch/torch_geometric 을 싣지 않으므로 vacancy_forecast 와 동일하게
json 정적 서빙이 기본 경로다. 인메모리 TTL 캐시로 파일 재읽기를 줄인다.

조회 키는 좌표다 — 그래프 노드는 '현존 점포 자리'이므로, 빈 자리(공실 유닛)나 건물을
물어보면 같은 거점 안에서 가장 가까운 노드의 추천을 돌려준다. 추천은 그 자리의 입지
(거점 내 위치·건물 규모·주변 밀집도)에서 나온 것이라 인접 자리끼리 공유해도 된다.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

_GOLD = Path(__file__).resolve().parents[4] / "data" / "gold"
_RECOMMEND_JSON = _GOLD / "platform_industry_recommend.json"
_TTL_SECONDS = 300.0

# 이 거리를 넘으면 '가까운 자리'로 보지 않는다(거점 밖 좌표를 물었을 때 방지)
_MAX_MATCH_M = 400.0
_M_PER_DEG_LAT = 111000.0
_M_PER_DEG_LON = 88300.0

_cache: dict[str, Any] = {}


def _load() -> dict | None:
    now = time.monotonic()
    if _cache.get("data") is not None and now - _cache.get("at", 0.0) < _TTL_SECONDS:
        return _cache["data"]
    if not _RECOMMEND_JSON.exists():
        return None
    _cache["data"] = json.loads(_RECOMMEND_JSON.read_text(encoding="utf-8"))
    _cache["at"] = now
    return _cache["data"]


def _dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dy = (lat1 - lat2) * _M_PER_DEG_LAT
    dx = (lon1 - lon2) * _M_PER_DEG_LON
    return math.sqrt(dx * dx + dy * dy)


def recommend(district_id: str, lat: float | None = None,
              lon: float | None = None) -> dict | None:
    """거점(+좌표)의 Top-K 업종 추천. 파일·거점 부재 시 None.

    좌표를 주면 최근접 노드의 추천, 주지 않으면 거점 전체 노드의 확률 평균으로
    거점 단위 추천을 만든다.
    """
    data = _load()
    if data is None:
        return None
    nodes = (data.get("districts") or {}).get(district_id)
    if not nodes:
        return None

    common = {"district_id": district_id, "model": data.get("model", "industry-gnn"),
              "metrics": data.get("metrics"), "source": "recommend_json"}

    if lat is None or lon is None:
        agg: dict[str, float] = {}
        for item in nodes.values():
            for t in item.get("top", []):
                agg[t["industry"]] = agg.get(t["industry"], 0.0) + t["score"]
        n = max(1, len(nodes))
        top = sorted(((k, v / n) for k, v in agg.items()), key=lambda t: -t[1])
        return {**common, "scope": "district",
                "recommendations": [{"industry": k, "score": round(v, 4)}
                                    for k, v in top[:3]]}

    best_id, best_d, best = None, float("inf"), None
    for nid, item in nodes.items():
        d = _dist_m(lat, lon, item.get("lat", 0.0), item.get("lon", 0.0))
        if d < best_d:
            best_id, best_d, best = nid, d, item
    if best is None or best_d > _MAX_MATCH_M:
        return None
    return {**common, "scope": "node", "matched_node_id": best_id,
            "matched_distance_m": round(best_d, 1),
            "recommendations": best.get("top", [])}


def is_available() -> bool:
    return _load() is not None
