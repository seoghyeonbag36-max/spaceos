"""Platform·LSTM 서빙 래퍼 — predict_vacancy(district_id).

로드 우선순위:
  1) ml/artifacts/vacancy_lstm.pt + Gold 시계열로 실시간 추론 (torch 필요)
  2) data/gold/platform_vacancy_forecast.json (train_lstm 산출 배치 예측) 폴백
Vercel 서버리스에는 torch 를 싣지 않으므로 2)가 기본 경로다 — 백엔드는
apps/backend/app/services/vacancy_forecast.py 로 같은 json 을 직접 읽는다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
ARTIFACT = _REPO / "ml" / "artifacts" / "vacancy_lstm.pt"
FORECAST_JSON = _REPO / "data" / "gold" / "platform_vacancy_forecast.json"
CALIBRATION_JSON = _REPO / "data" / "gold" / "garosugil" / "calibration.json"

# 지상검증 실측 앵커 보유 거점 (PoC exit 통과분 — 단일 시점 스냅샷)
_ANCHOR_DISTRICTS = {"garosugil"}

_cache: dict[str, Any] = {}


def _anchor(district_id: str) -> dict | None:
    """garosugil 은 building_vacancy PoC 실측(정확도 75%)을 참조 앵커로 부착.

    단일 시점 스냅샷이라 시계열 피처가 아닌 서빙 참조값 — 예측(vac_proxy 스케일)과
    실제 공실률 스케일(%)의 간극을 소비자가 가늠하게 한다.
    """
    if district_id not in _ANCHOR_DISTRICTS or not CALIBRATION_JSON.exists():
        return None
    if "anchor" not in _cache:
        import datetime

        cal = json.loads(CALIBRATION_JSON.read_text(encoding="utf-8"))
        _cache["anchor"] = {
            "estimated_vacancy_pct": cal.get("estimated_vacancy_pct"),
            "anchor_street_pct": cal.get("anchor_street_pct"),
            "buildings_used": cal.get("buildings_used"),
            "as_of": datetime.date.fromtimestamp(CALIBRATION_JSON.stat().st_mtime).isoformat(),
            "source": "building_vacancy PoC 지상검증(정확도 75%) — 단일 시점 스냅샷",
        }
    return _cache["anchor"]


def _load_forecast() -> dict | None:
    """forecast json 로드 — mtime 캐시."""
    if not FORECAST_JSON.exists():
        return None
    mtime = FORECAST_JSON.stat().st_mtime
    if _cache.get("fc_mtime") != mtime:
        _cache["fc"] = json.loads(FORECAST_JSON.read_text(encoding="utf-8"))
        _cache["fc_mtime"] = mtime
    return _cache["fc"]


def _predict_with_model(district_id: str) -> dict | None:
    """체크포인트 + Gold 최신 윈도우로 실시간 추론. torch/Gold 부재 시 None."""
    try:
        import numpy as np
        import torch

        from ml.models.lstm.vacancy_lstm import VacancyLSTM
        from ml.training.datasets import SEQ_FEATURES, TARGET, load_gold

        if not ARTIFACT.exists():
            return None
        if "ckpt" not in _cache:
            _cache["ckpt"] = torch.load(ARTIFACT, map_location="cpu", weights_only=False)
        ckpt = _cache["ckpt"]
        dids = ckpt["district_ids"]
        if district_id not in dids:
            return None
        if "model" not in _cache:
            p = ckpt["params"]
            m = VacancyLSTM(num_features=ckpt["num_features"], hidden=p["hidden"],
                            layers=p["layers"], dropout=0.0)
            m.load_state_dict(ckpt["state_dict"])
            m.eval()
            _cache["model"] = m
        model = _cache["model"]

        df = load_gold()
        g = df[df["district_id"] == district_id]
        lb = ckpt["params"]["look_back"]
        if len(g) < lb:
            return None
        mu, sd = np.asarray(ckpt["mu"]), np.asarray(ckpt["sd"])
        z = (g[list(SEQ_FEATURES)].to_numpy(dtype=float) - mu) / sd
        onehot = np.zeros(len(dids))
        onehot[dids.index(district_id)] = 1.0
        win = np.hstack([z[-lb:], np.tile(onehot, (lb, 1))]).astype(np.float32)
        with torch.no_grad():
            pred = float(model(torch.from_numpy(win[None])).item()) * ckpt["y_sd"] + ckpt["y_mu"]
        last = float(g[TARGET].iloc[-1])
        return {
            "district_id": district_id,
            "forecast_vac_proxy": round(pred, 3),
            "last_vac_proxy": round(last, 3),
            "delta": round(pred - last, 3),
            "direction": "up" if pred > last else "down",
            "last_quarter": str(g["quarter"].iloc[-1]),
            "source": "model",
        }
    except Exception:
        return None


def predict_vacancy(district_id: str) -> dict | None:
    """다음 분기 공실 프록시 예측. 모델 → forecast json 순 폴백. 미지원 거점은 None."""
    out = _predict_with_model(district_id)
    if out is not None:
        fc = _load_forecast() or {}
        out["metrics"] = fc.get("metrics")
        out["model"] = (fc or {}).get("model", "vacancy-lstm-pooled-v2")
        anchor = _anchor(district_id)
        if anchor:
            out["ground_anchor"] = anchor
        return out

    fc = _load_forecast()
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
    anchor = _anchor(district_id)
    if anchor:
        out["ground_anchor"] = anchor
    return out


if __name__ == "__main__":
    import sys

    did = sys.argv[1] if len(sys.argv) > 1 else "garosugil"
    print(json.dumps(predict_vacancy(did), ensure_ascii=False, indent=2))
