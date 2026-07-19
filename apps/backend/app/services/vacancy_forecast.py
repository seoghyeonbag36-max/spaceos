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
_GOLD = Path(__file__).resolve().parents[4] / "data" / "gold"
_FORECAST_JSON = _GOLD / "platform_vacancy_forecast.json"
_CALIBRATION_JSON = _GOLD / "garosugil" / "calibration.json"
_TTL_SECONDS = 300.0

# 지상검증 실측 앵커 보유 거점 (garosugil PoC exit 통과분)
_ANCHOR_DISTRICTS = {"garosugil"}

_cache: dict[str, Any] = {}


def _anchor(district_id: str) -> dict | None:
    """building_vacancy PoC 실측 보정값을 참조 앵커로 부착 (단일 시점 스냅샷)."""
    if district_id not in _ANCHOR_DISTRICTS or not _CALIBRATION_JSON.exists():
        return None
    if "anchor" not in _cache:
        import datetime

        cal = json.loads(_CALIBRATION_JSON.read_text(encoding="utf-8"))
        _cache["anchor"] = {
            "estimated_vacancy_pct": cal.get("estimated_vacancy_pct"),
            "anchor_street_pct": cal.get("anchor_street_pct"),
            "buildings_used": cal.get("buildings_used"),
            "as_of": datetime.date.fromtimestamp(
                _CALIBRATION_JSON.stat().st_mtime).isoformat(),
            "source": "building_vacancy PoC 지상검증(정확도 75%) — 단일 시점 스냅샷",
        }
    return _cache["anchor"]


def _load() -> dict | None:
    now = time.monotonic()
    if _cache.get("data") is not None and now - _cache.get("at", 0.0) < _TTL_SECONDS:
        return _cache["data"]
    if not _FORECAST_JSON.exists():
        return None
    _cache["data"] = json.loads(_FORECAST_JSON.read_text(encoding="utf-8"))
    _cache["at"] = now
    return _cache["data"]


def get_forecast(district_id: str, quarters: int = 1) -> dict | None:
    """거점의 다음 분기 공실 프록시 예측. 미지원 거점 또는 파일 부재 시 None.

    quarters(1~4): 재귀 예측 horizon 선택. h2+ 는 외생 피처를 마지막 관측값으로
    고정한 근사라 불확실성이 커진다 (검증 지표는 h1 기준 — 응답 metrics 참조).
    """
    fc = _load()
    if fc is None:
        return None
    item = fc.get("forecasts", {}).get(district_id)
    if item is None:
        return None
    out = {
        "district_id": district_id,
        **item,
        "metrics": fc.get("metrics"),
        "model": fc.get("model", "vacancy-lstm-pooled-v2"),
        "trained_at": fc.get("trained_at"),
        "source": "forecast_json",
    }
    horizons = item.get("horizons") or []
    q = max(1, min(quarters, len(horizons) or 1))
    if horizons and q > 1:
        sel = horizons[q - 1]
        out.update({
            "forecast_vac_proxy": sel["forecast_vac_proxy"],
            "forecast_quarter": sel["quarter"],
            # delta·direction 은 마지막 관측 분기 대비로 재계산
            "delta": round(sel["forecast_vac_proxy"] - item.get("last_vac_proxy", 0.0), 3),
            "direction": "up" if sel["forecast_vac_proxy"] > item.get("last_vac_proxy", 0.0) else "down",
        })
    out["horizon_quarters"] = q
    anchor = _anchor(district_id)
    if anchor:
        out["ground_anchor"] = anchor
    return out


def all_forecasts() -> dict[str, dict]:
    """전 거점 forecast 맵 — heatmap/대시보드 predicted_rate 조인용(D단계)."""
    fc = _load() or {}
    return fc.get("forecasts", {})


def is_available() -> bool:
    return _load() is not None
