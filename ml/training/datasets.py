"""Platform·LSTM 데이터셋 — Gold platform_district_timeseries → 거점×분기 피처 텐서.

소스: data/gold/platform13/platform_district_timeseries.{parquet|csv}
타깃: vac_proxy — 공실 프록시(= clsbiz_rt − opbiz_rt + 점포수 감소율%). 상승 = 공실 압력 증가.
피처(분기 단위): vac_proxy + vac_small·vac_mid·rent_small(R-ONE 실측, rone_rent 조인 필수)
                · log_selng(추정매출) · log_flpop(길단위 유동인구) · stor_idx(점포수 지수)
                · opbiz_rt · clsbiz_rt
  - 타깃을 R-ONE 실측(vac_small)으로 바꾸는 실험은 방향정확도 46.2%로 실패(2026-07-19,
    mlruns 기록) — 2024Q3 표본개편 점프·소표본 0% 값 노이즈 탓. 노이즈 처리 후 재시도 TODO.
  - R-ONE 유의: 일부 거점은 상권 공유 매핑(config/rone_districts.py) — 공유 거점끼리
    R-ONE 피처 동일.
  - garosugil 은 building_vacancy(지상검증 PoC) 실측 공실률이 있으나 단일 시점 스냅샷이라
    시계열 피처 대신 서빙 응답의 참조 앵커(ground_anchor)로 부착한다 —
    ml/inference/predictor.py · apps/backend/app/services/vacancy_forecast.py 의 _anchor().

분기 데이터라 look_back 은 월 단위(30)가 아니라 가용 분기 수에 맞춘다 — 거점당
분기 수가 적으므로 전 거점 통합(pooled) 학습 + 거점 임베딩(정적 원핫) 방식.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
GOLD_TS = _REPO / "data" / "gold" / "platform13" / "platform_district_timeseries"

# 시계열 피처 열 순서 (거점 원핫은 뒤에 붙는다) — 첫 열 = 타깃 (train_lstm 방향 판정이 인덱스 0 참조)
SEQ_FEATURES = ("vac_proxy", "vac_small", "vac_mid", "rent_small",
                "log_selng", "stor_idx", "opbiz_rt", "clsbiz_rt")
TARGET = "vac_proxy"
# ablation 기각 피처 (2026-07-19, mlruns 기록 — gold 컬럼은 유지, 표본 확대 후 재시도 TODO):
#   log_flpop(유동인구)        MAE 0.901→1.018 악화
#   ix_opr_mt/ix_cls_mt(상권변화지표 평균 영업개월)  방향정확도 84.6%→76.9% 악화


def load_gold() -> pd.DataFrame:
    """Gold 테이블 로드 (parquet 우선, csv 폴백) + 파생 피처 계산."""
    if GOLD_TS.with_suffix(".parquet").exists():
        df = pd.read_parquet(GOLD_TS.with_suffix(".parquet"))
    elif GOLD_TS.with_suffix(".csv").exists():
        df = pd.read_csv(GOLD_TS.with_suffix(".csv"))
    else:
        raise FileNotFoundError(f"Gold 없음: {GOLD_TS}.parquet — build_gold 먼저 실행")

    if "vac_small" not in df.columns:
        raise ValueError("gold 에 vac_small 없음 — rone_rent 수집 후 build_gold 재실행 필요")
    df = df.sort_values(["district_id", "quarter"]).reset_index(drop=True)
    out = []
    for did, g in df.groupby("district_id"):
        g = g.copy()
        base_stor = g["stor_co"].iloc[0] or 1.0
        g["stor_idx"] = g["stor_co"] / base_stor * 100.0          # 첫 분기=100 지수
        stor_chg = g["stor_co"].pct_change().fillna(0.0) * 100.0   # 점포수 증감률(%)
        g["vac_proxy"] = (g["clsbiz_rt"] - g["opbiz_rt"]) - stor_chg
        g["log_selng"] = np.log1p(g["selng_amt"].fillna(0.0))
        g["log_flpop"] = np.log1p(g["flpop"].fillna(0.0)) if "flpop" in g else 0.0
        out.append(g)
    return pd.concat(out, ignore_index=True)


@dataclass
class PooledDataset:
    """pooled 슬라이딩 윈도우 데이터셋.

    X: (N, look_back, F+D)  — F=시계열 피처, D=거점 원핫
    y: (N,)                 — 다음 분기 vac_proxy (표준화 스케일)
    """
    X: np.ndarray
    y: np.ndarray
    district_ids: list[str]          # 원핫 인덱스 순서
    sample_district: np.ndarray      # 각 샘플의 거점 인덱스
    sample_is_last: np.ndarray       # 홀드아웃(각 거점 마지막 윈도우) 여부
    mu: np.ndarray                   # 피처 표준화 평균 (F,)
    sd: np.ndarray                   # 피처 표준화 표준편차 (F,)
    y_mu: float
    y_sd: float


def build_dataset(look_back: int | None = None) -> PooledDataset:
    """Gold → pooled 윈도우. look_back 미지정 시 min(8, 최소 가용-1)로 자동 조정."""
    df = load_gold()
    dids = sorted(df["district_id"].unique())
    n_min = int(df.groupby("district_id").size().min())
    if look_back is None:
        look_back = max(2, min(8, n_min - 2))  # 홀드아웃 1분기 확보

    feats = df[list(SEQ_FEATURES)].to_numpy(dtype=np.float64)
    # ⚠ nan 을 무시하고 센다. 2026-09-04 에 여기가 66거점 학습을 통째로 죽였다:
    # 서울 2차 12거점이 붙으면서 R-ONE 계열(vac_small·vac_mid·rent_small)에 결측이
    # 생겼는데(kkachisan 14분기 · sangbong 4분기 — 그 상권의 R-ONE 시계열이 늦게
    # 시작한다), `mean(axis=0)` 은 한 칸만 nan 이어도 **그 열 전체를 nan** 으로 만든다.
    # 그러면 표준화가 모든 거점·모든 샘플을 nan 으로 오염시켜 8 trial 이 전부
    # `MAE nan · 방향정확도 0.0%` 로 나온다 — 결측 18칸이 1,452행 학습을 죽였다.
    mu, sd = np.nanmean(feats, axis=0), np.nanstd(feats, axis=0)
    sd[sd == 0] = 1.0

    Xs, ys, s_did, s_last = [], [], [], []
    dropped = 0
    for di, did in enumerate(dids):
        g = df[df["district_id"] == did]
        z = (g[list(SEQ_FEATURES)].to_numpy(dtype=np.float64) - mu) / sd
        onehot = np.zeros(len(dids))
        onehot[di] = 1.0
        n = len(g)
        for end in range(look_back, n):  # 윈도우 [end-look_back, end) → 타깃 end
            src = z[end - look_back:end]
            tgt = g[TARGET].iloc[end]
            # 결측이 낀 윈도우는 **학습에서 뺀다** — 채워 넣지 않는다. 결측은 R-ONE
            # 시계열의 시작 시점 차이라 거점 앞쪽에 몰려 있고, 뒤쪽(예측 기준 윈도우)은
            # 온전하다. 그래서 버려도 예측을 잃는 거점은 없다(train_lstm._forecast_next
            # 가 마지막 윈도우로 따로 낸다). 평균으로 메우면 안 받은 분기를 받은 것처럼
            # 학습하게 되므로 그렇게 하지 않는다.
            if not np.isfinite(src).all() or not np.isfinite(tgt):
                dropped += 1
                continue
            win = np.hstack([src, np.tile(onehot, (look_back, 1))])
            Xs.append(win)
            ys.append(tgt)
            s_did.append(di)
            s_last.append(end == n - 1)

    if dropped:
        print(f"[dataset] 결측 윈도우 {dropped}개 제외 · 학습 윈도우 {len(Xs)}개")
    X = np.asarray(Xs, dtype=np.float32)
    y_raw = np.asarray(ys, dtype=np.float64)
    y_mu, y_sd = float(y_raw.mean()), float(y_raw.std() or 1.0)
    y = ((y_raw - y_mu) / y_sd).astype(np.float32)
    return PooledDataset(
        X=X, y=y, district_ids=dids,
        sample_district=np.asarray(s_did), sample_is_last=np.asarray(s_last),
        mu=mu, sd=sd, y_mu=y_mu, y_sd=y_sd,
    )


if __name__ == "__main__":
    ds = build_dataset()
    print(f"X={ds.X.shape} y={ds.y.shape} 거점={len(ds.district_ids)} 홀드아웃={int(ds.sample_is_last.sum())}")
