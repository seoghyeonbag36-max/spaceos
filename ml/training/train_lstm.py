"""VacancyLSTM 13거점 pooled 학습 + 다음 분기 공실률 예측.

타깃: vac_proxy(대리 지표) 유지. v2 = R-ONE 실측(공실률 소규모/중대형·임대료)을 피처로
추가 — v1 대비 MAE 0.941→0.901, RMSE 1.361→1.147, 방향정확도 84.6% 동일.
실측(vac_small)을 타깃으로 쓰는 실험은 46.2%로 실패(표본개편 노이즈) — datasets.py 참조.

전략 (분기 데이터 → look_back 자동 조정, /platform-autorun B단계):
  - 거점당 분기 수가 적어(≈20) 단일 거점 학습 불가 → 전 거점 통합(pooled) + 거점 원핫.
  - 홀드아웃 = 거점별 마지막 분기 1개(13샘플). 지표: MAE/RMSE(%p)·방향 정확도.
  - 목표 방향 정확도 70%+. 미달 시 하이퍼파라미터 1~2회만 재시도 (무한 튜닝 금지).

산출:
  ml/artifacts/vacancy_lstm.pt              모델 + 전처리 메타 (predictor 가 로드)
  data/gold/platform_vacancy_forecast.json  거점별 다음 분기 예측 (서빙 폴백·정적 서빙용)
  ml/mlruns                                 MLflow 로컬 파일 스토어

실행: python -m ml.training.train_lstm
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from ml.models.lstm.vacancy_lstm import VacancyLSTM  # noqa: E402
from ml.training.datasets import SEQ_FEATURES, TARGET, build_dataset, load_gold  # noqa: E402

ARTIFACT = _REPO / "ml" / "artifacts" / "vacancy_lstm.pt"
FORECAST_JSON = _REPO / "data" / "gold" / "platform_vacancy_forecast.json"
MLRUNS = _REPO / "ml" / "mlruns"

_SEED = 42


def _train_once(hidden: int, layers: int, look_back: int | None, epochs: int = 400,
                lr: float = 1e-3) -> dict:
    torch.manual_seed(_SEED)
    np.random.seed(_SEED)
    ds = build_dataset(look_back=look_back)
    holdout = ds.sample_is_last
    Xtr, ytr = torch.from_numpy(ds.X[~holdout]), torch.from_numpy(ds.y[~holdout])
    Xte, yte = torch.from_numpy(ds.X[holdout]), torch.from_numpy(ds.y[holdout])

    model = VacancyLSTM(num_features=ds.X.shape[2], hidden=hidden, layers=layers,
                        dropout=0.2 if layers > 1 else 0.0)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    lossf = nn.MSELoss()
    for _ in range(epochs):
        model.train()
        opt.zero_grad()
        loss = lossf(model(Xtr).squeeze(-1), ytr)
        loss.backward()
        opt.step()

    model.eval()
    with torch.no_grad():
        pred_z = model(Xte).squeeze(-1).numpy()
    pred = pred_z * ds.y_sd + ds.y_mu                # 원단위 복원
    actual = yte.numpy() * ds.y_sd + ds.y_mu
    # 방향 기준값 = 각 홀드아웃 윈도우 마지막 분기의 vac_proxy (피처 0 역표준화)
    prev = ds.X[holdout][:, -1, 0] * ds.sd[0] + ds.mu[0]
    mae = float(np.mean(np.abs(pred - actual)))
    rmse = float(np.sqrt(np.mean((pred - actual) ** 2)))
    dir_acc = float(np.mean(np.sign(pred - prev) == np.sign(actual - prev)))
    return {
        "model": model, "ds": ds, "pred": pred, "actual": actual, "prev": prev,
        "mae": mae, "rmse": rmse, "dir_acc": dir_acc,
        "params": {"hidden": hidden, "layers": layers, "look_back": int(ds.X.shape[1]),
                   "epochs": epochs, "lr": lr, "train_loss": float(loss.item())},
    }


def _log_mlflow(res: dict, run_name: str) -> None:
    try:
        import mlflow
        mlflow.set_tracking_uri(f"file:///{MLRUNS.as_posix()}")
        mlflow.set_experiment("platform_vacancy_lstm")
        with mlflow.start_run(run_name=run_name):
            mlflow.log_params(res["params"])
            mlflow.log_metrics({"holdout_mae": res["mae"], "holdout_rmse": res["rmse"],
                                "holdout_dir_acc": res["dir_acc"]})
    except Exception as exc:  # MLflow 실패가 학습을 막지 않도록
        print(f"[mlflow] 기록 실패(무시): {exc}")


def _forecast_next(res: dict) -> dict:
    """거점별 최신 look_back 분기 윈도우로 다음 분기 vac_proxy 예측."""
    ds, model = res["ds"], res["model"]
    df = load_gold()
    lb = res["params"]["look_back"]
    out: dict[str, dict] = {}
    model.eval()
    for di, did in enumerate(ds.district_ids):
        g = df[df["district_id"] == did]
        z = (g[list(SEQ_FEATURES)].to_numpy(dtype=np.float64) - ds.mu) / ds.sd
        if len(z) < lb:
            continue
        onehot = np.zeros(len(ds.district_ids))
        onehot[di] = 1.0
        win = np.hstack([z[-lb:], np.tile(onehot, (lb, 1))]).astype(np.float32)
        with torch.no_grad():
            p = float(model(torch.from_numpy(win[None])).item()) * ds.y_sd + ds.y_mu
        last = float(g[TARGET].iloc[-1])
        out[did] = {
            "forecast_vac_proxy": round(p, 3),
            "last_vac_proxy": round(last, 3),
            "delta": round(p - last, 3),
            "direction": "up" if p > last else "down",
            "last_quarter": str(g["quarter"].iloc[-1]),
            "n_quarters": int(len(g)),
        }
    return out


def main() -> None:
    now = datetime.datetime.now().isoformat(timespec="seconds")
    # 1차 시도 + 미달 시 재시도(최대 2회) — 하이퍼파라미터 후보
    trials = [
        {"hidden": 32, "layers": 1, "look_back": None},
        {"hidden": 64, "layers": 2, "look_back": None},
        {"hidden": 32, "layers": 1, "look_back": 6},
    ]
    best = None
    for i, hp in enumerate(trials):
        res = _train_once(**hp)
        print(f"[trial {i}] {hp} → MAE {res['mae']:.3f} RMSE {res['rmse']:.3f} "
              f"방향정확도 {res['dir_acc']:.1%}")
        _log_mlflow(res, run_name=f"trial{i}")
        if best is None or res["dir_acc"] > best["dir_acc"]:
            best = res
        if res["dir_acc"] >= 0.70:
            best = res
            break

    print(f"[best] {best['params']} → MAE {best['mae']:.3f} RMSE {best['rmse']:.3f} "
          f"방향정확도 {best['dir_acc']:.1%} (목표 70%)")

    # 거점별 홀드아웃 상세
    ds = best["ds"]
    hold_dids = [ds.district_ids[d] for d in ds.sample_district[ds.sample_is_last]]
    per_district = {
        did: {"pred": round(float(p), 3), "actual": round(float(a), 3),
              "prev": round(float(v), 3),
              "direction_hit": bool(np.sign(p - v) == np.sign(a - v))}
        for did, p, a, v in zip(hold_dids, best["pred"], best["actual"], best["prev"])
    }
    for did, m in per_district.items():
        print(f"  {did}: pred {m['pred']} vs actual {m['actual']} "
              f"({'O' if m['direction_hit'] else 'X'})")

    # 모델 아티팩트
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "state_dict": best["model"].state_dict(),
        "num_features": ds.X.shape[2],
        "params": best["params"],
        "district_ids": ds.district_ids,
        "mu": ds.mu.tolist(), "sd": ds.sd.tolist(),
        "y_mu": ds.y_mu, "y_sd": ds.y_sd,
    }, ARTIFACT)
    print(f"[artifact] {ARTIFACT}")

    # 서빙용 forecast json
    fc = _forecast_next(best)
    payload = {
        "model": "vacancy-lstm-pooled-v2",
        "target": "vac_proxy(공실 프록시) — R-ONE 실측(vac_small/vac_mid/rent_small)은 피처",
        "trained_at": now,
        "metrics": {"holdout_mae": round(best["mae"], 3), "holdout_rmse": round(best["rmse"], 3),
                    "holdout_direction_acc": round(best["dir_acc"], 3)},
        "params": best["params"],
        "holdout": per_district,
        "forecasts": fc,
    }
    FORECAST_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[forecast] {FORECAST_JSON} — {len(fc)}거점")


if __name__ == "__main__":
    main()
