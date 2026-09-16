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

# ── 롤링 오리진 분할 (2026-09-16) ────────────────────────────────────────────
# 거점당 분기 22개 · look_back 8 → 윈도우 14개인데 **종전에는 그중 1개만** 홀드아웃으로
# 썼다. 홀드아웃 65건에서 이항 표준오차가 5.7%p 라 3~5%p 짜리 차이를 원리적으로 못
# 가른다 — KPI 판정이 "베이스라인 대비 실력" 인데 그 실력을 잴 분해능이 없었다는 뜻이다.
#
# 거점을 늘려 해결하려면 3%p 를 가리는 데 약 900거점이 필요하다(현재 66). 대신 **이미
# 가진 분기를 쓴다**: 거점마다 마지막 K분기를 차례로 홀드아웃 원점으로 삼는다.
#   test 3 → 홀드아웃 198건 · val 2 → 132건 · train 9윈도우/거점(594건)
#
# ⚠ 표준오차가 √3 배로 좁아지지는 않는다 — 같은 거점의 이웃 분기는 상관돼 있어
#   표본이 독립이 아니다. 그래서 `scripts/kpi_baseline.py` 는 홀드아웃에 거점당
#   표본이 여럿이면 **거점 단위 군집 부트스트랩**으로 구간을 낸다(이항 공식이 아니라).
# ⚠ train 윈도우가 13 → 9 로 줄어든다. 그 대가가 얼마인지는 **재학습 전에는 모른다** —
#   재학습할 때 `--test-quarters 1 --val-quarters 1` 대조군을 같이 돌려 비교할 것.
TEST_QUARTERS = 3
VAL_QUARTERS = 2
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
    sample_is_last: np.ndarray       # test(각 거점 뒤쪽 test_quarters 윈도우) 여부
    sample_is_val: np.ndarray        # val(그 앞 val_quarters 윈도우) 여부
    sample_quarter: np.ndarray       # 각 샘플의 타깃 분기 — 홀드아웃 기록의 키가 된다
    mu: np.ndarray                   # 피처 표준화 평균 (F,) — **train 행에서만** 계산
    sd: np.ndarray                   # 피처 표준화 표준편차 (F,) — 위와 같다
    y_mu: float
    y_sd: float


def build_dataset(look_back: int | None = None,
                  test_quarters: int = TEST_QUARTERS,
                  val_quarters: int = VAL_QUARTERS) -> PooledDataset:
    """Gold → pooled 윈도우. look_back 미지정 시 가용 분기 수에 맞춰 자동 조정.

    ## 홀드아웃이 둘인 이유 (2026-09-16 누수 차단)

    종전에는 거점별 **마지막 1분기**만 떼어 그것으로 하이퍼파라미터를 고르고 **같은
    것으로** 지표를 보고했다. 그러면 보고값이 test 가 아니라 val 이다 —
    `train_lstm.main` 이 8개 조합을 돌려 그중 가장 좋은 것을 고르고, 방향정확도가
    0.70 을 넘는 순간 멈추기까지 했다. 그렇게 나온 70.8% 는 "이 모델의 성능"이 아니라
    "8번 뽑아 목표를 넘긴 값"이라 위로 편향된다.

    그래서 뒤쪽 분기를 **val**(선택용)과 **test**(보고용)로 가른다. 시계열이므로
    무작위 분할이 아니라 시간 순서를 지킨다 — 거점마다 시간축 뒤에서부터
    `test_quarters` 개가 test, 그 앞 `val_quarters` 개가 val, 나머지가 train 이다
    (롤링 오리진). 기본값의 근거는 위 `TEST_QUARTERS` 주석에 있다.

    ## 표준화 통계도 train 에서만 낸다

    `mu`·`sd`·`y_mu`·`y_sd` 를 전체 행에서 내면 **미래(홀드아웃)가 전처리에 샌다.**
    분기 시계열에서 이건 고전적인 누수다 — 평가 시점에는 알 수 없는 값으로 스케일을
    맞춰 놓고 그 스케일로 복원한 예측을 채점하게 된다. 방향 판정이 `pred - prev` 의
    부호라 `y_mu` 이동이 그대로 판정을 흔든다(불변이 아니다).

    ⚠ 이 함수를 고치면 **재학습 전까지 `ml/artifacts/vacancy_lstm.pt` 와 그 지표는
    옛 규약(누수 포함)이다.** 산출물에 규약 표기를 남기는 것은 `train_lstm.main` 이
    한다(`protocol` 블록).
    """
    df = load_gold()
    dids = sorted(df["district_id"].unique())
    n_min = int(df.groupby("district_id").size().min())
    if test_quarters < 1 or val_quarters < 1:
        raise ValueError("test_quarters·val_quarters 는 1 이상이어야 한다 — "
                         "둘 중 하나가 0 이면 선택과 보고가 다시 한 표본에서 난다")
    holdout_q = test_quarters + val_quarters
    if look_back is None:
        # 홀드아웃을 떼고도 train 윈도우가 최소 1개 남아야 한다.
        look_back = max(2, min(8, n_min - holdout_q - 1))

    # 표준화 통계의 모집단 = **각 거점의 마지막 holdout_q 분기를 뺀 행**(= val·test
    # 타깃 분기). 그 앞 분기들은 train 윈도우의 입력으로 실제로 쓰이므로 남긴다.
    train_row = np.ones(len(df), dtype=bool)
    for did in dids:
        idx = np.flatnonzero((df["district_id"] == did).to_numpy())
        train_row[idx[-holdout_q:]] = False

    feats = df[list(SEQ_FEATURES)].to_numpy(dtype=np.float64)
    # ⚠ nan 을 무시하고 센다. 2026-09-04 에 여기가 66거점 학습을 통째로 죽였다:
    # 서울 2차 12거점이 붙으면서 R-ONE 계열(vac_small·vac_mid·rent_small)에 결측이
    # 생겼는데(kkachisan 14분기 · sangbong 4분기 — 그 상권의 R-ONE 시계열이 늦게
    # 시작한다), `mean(axis=0)` 은 한 칸만 nan 이어도 **그 열 전체를 nan** 으로 만든다.
    # 그러면 표준화가 모든 거점·모든 샘플을 nan 으로 오염시켜 8 trial 이 전부
    # `MAE nan · 방향정확도 0.0%` 로 나온다 — 결측 18칸이 1,452행 학습을 죽였다.
    mu = np.nanmean(feats[train_row], axis=0)
    sd = np.nanstd(feats[train_row], axis=0)
    sd[sd == 0] = 1.0

    Xs, ys, s_did, s_last, s_val, s_quarter = [], [], [], [], [], []
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
            s_quarter.append(str(g["quarter"].iloc[end]))
            # 시간축 뒤에서부터 test → val 순. 겹치지 않는다.
            s_last.append(end >= n - test_quarters)                  # test — 보고 전용
            s_val.append(n - holdout_q <= end < n - test_quarters)   # val — 선택용

    if dropped:
        print(f"[dataset] 결측 윈도우 {dropped}개 제외 · 학습 윈도우 {len(Xs)}개")
    X = np.asarray(Xs, dtype=np.float32)
    y_raw = np.asarray(ys, dtype=np.float64)
    is_last = np.asarray(s_last, dtype=bool)
    is_val = np.asarray(s_val, dtype=bool)
    # 타깃 표준화도 **train 윈도우만**으로 낸다. `_train_once` 가 이 상수로 예측을
    # 원단위로 되돌리고 방향을 `pred - prev` 로 판정하므로, 여기에 홀드아웃이 섞이면
    # 판정 자체가 미래를 보고 내려진다.
    y_train = y_raw[~(is_last | is_val)]
    if y_train.size == 0:        # 거점당 분기가 극단적으로 적을 때만 — 전부로 물러난다
        y_train = y_raw
    y_mu, y_sd = float(y_train.mean()), float(y_train.std() or 1.0)
    y = ((y_raw - y_mu) / y_sd).astype(np.float32)
    return PooledDataset(
        X=X, y=y, district_ids=dids,
        sample_district=np.asarray(s_did), sample_is_last=is_last, sample_is_val=is_val,
        sample_quarter=np.asarray(s_quarter, dtype=object),
        mu=mu, sd=sd, y_mu=y_mu, y_sd=y_sd,
    )


if __name__ == "__main__":
    ds = build_dataset()
    n_tr = int((~(ds.sample_is_val | ds.sample_is_last)).sum())
    print(f"X={ds.X.shape} y={ds.y.shape} 거점={len(ds.district_ids)} "
          f"train={n_tr} val={int(ds.sample_is_val.sum())} test={int(ds.sample_is_last.sum())}")
