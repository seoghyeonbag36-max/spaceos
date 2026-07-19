"""Platform·LSTM 공실 예측 서빙 — gold/platform_vacancy_forecast.json 직접 로드.

ml/inference/predictor.py 와 같은 배치 산출물을 읽지만, Vercel 서버리스에는
torch/ml 의존을 싣지 않으므로 백엔드는 json 정적 서빙이 기본 경로다.
Redis 부재 환경(서버리스) 고려 — 인메모리 TTL 캐시로 파일 재읽기를 줄인다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

# repo/data/gold/platform_vacancy_forecast.json (services → app → backend → apps → repo)
_FORECAST_JSON = (Path(__file__).resolve().parents[4]
                  / "data" / "gold" / "platform_vacancy_forecast.json")
_TTL_SECONDS = 300.0

_cache: dict[str, Any] = {}


def _load() -> dict | None:
    now = time.monotonic()
    if _cache.get("data") is not None and now - _cache.get("at", 0.0) < _TTL_SECONDS:
        return _cache["data"]
    if not _FORECAST_JSON.exists():
        return None
    _cache["data"] = json.loads(_FORECAST_JSON.read_text(encoding="utf-8"))
    _cache["at"] = now
    return _cache["data"]


def get_forecast(district_id: str) -> dict | None:
    """거점의 다음 분기 공실 프록시 예측. 미지원 거점 또는 파일 부재 시 None."""
    fc = _load()
    if fc is None:
        return None
    item = fc.get("forecasts", {}).get(district_id)
    if item is None:
        return None
    return {
        "district_id": district_id,
        **item,
        "metrics": fc.get("metrics"),
        "model": fc.get("model", "vacancy-lstm-pooled-v1"),
        "trained_at": fc.get("trained_at"),
        "source": "forecast_json",
    }


def all_forecasts() -> dict[str, dict]:
    """전 거점 forecast 맵 — heatmap/대시보드 predicted_rate 조인용(D단계)."""
    fc = _load() or {}
    return fc.get("forecasts", {})


def is_available() -> bool:
    return _load() is not None
