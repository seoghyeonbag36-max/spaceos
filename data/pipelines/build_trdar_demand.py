"""[Platform·GNN] TRDAR 상권 단위 공공 수요신호 테이블 — build_gold §9 TODO 구현.

산출: gold/features/trdar_demand.parquet (190상권 × 수요 피처)

## 왜 거점(district)이 아니라 상권(TRDAR) 단위인가

train_gnn 의 피처 행렬에는 이미 **거점 원핫**(`dist_oh`)이 들어 있다. 거점 안에서 상수인
값은 원핫이 이미 완전히 표현하므로, 거점 단위 생활인구·매출을 그대로 붙이면 모델에
새 정보가 **0** 이다. 실제로 GNN 의 거점 사전분포 대비 lift 가 +3.1% 에 그친 이유가
이것이다 — 모델이 쓸 수 있는 신호가 사실상 거점 정체성뿐이었다.

서울 상권분석서비스의 TRDAR 상권은 54거점을 190개로 쪼갠다(거점당 평균 3.5개). 이
단위로 붙여야 **거점 안에서 변하는** 수요 신호가 생긴다. 상권이 1개뿐인 거점
(nokdu·garak 2곳)은 여전히 거점 상수라 이득이 없다 — 한계로 기록해 둔다.

## 누출 방지 원칙

train_gnn 은 "업종을 가리고 입지만으로 맞히는" 태스크다. 따라서 **업종별(SVC_INDUTY)
분해는 절대 넣지 않는다** — 상권의 업종 구성비는 곧 라벨 분포다. 여기서는 업종 전체를
합산한 총량·비율만 만든다. 총 유동인구·시간대 프로파일·총매출·총점포수는 그 자리가
공실이어도 관측 가능하므로 train_gnn._features 의 기존 원칙과 어긋나지 않는다.

## 소스 (bronze/platform13, seoul_trdar 수집분)
  seoul_trdar_relm    상권 폴리곤 중심좌표(EPSG:5181)·면적·상권유형   190행
  seoul_trdar_flpop   길단위 유동인구 — 성/연령/시간대/요일 분해      190상권 × 21분기
  seoul_trdar_stor    점포수·개폐업률 (업종별 → 합산)                 190상권 × 21분기
  seoul_trdar_selng   추정매출 — 요일/시간대 분해 (업종별 → 합산)     185상권 × 21분기

분기 노이즈를 줄이려고 **최근 4분기 평균**을 쓴다(단일 분기는 표본개편·계절성에 흔들린다).

실행: python -m data.pipelines.build_trdar_demand
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

from data.collectors.common import GOLD, load_latest
from data.config.platform_districts import SLUG as SLUG13

_OUT_DIR = GOLD / "features"
_OUT_NAME = "trdar_demand"

# 상권 중심좌표는 EPSG:5181(Korea 2000 / 중부원점 TM). LOCALDATA(EPSG:2097)와 다르다 —
# platform_districts.py 헤더 경고 참조. 검증: 체부동(197340, 453202) → 37.578N/126.970E(종로구).
_TM_TO_WGS84 = Transformer.from_crs("EPSG:5181", "EPSG:4326", always_xy=True)

_RECENT_QUARTERS = 4  # 최근 N분기 평균 — 단일 분기의 표본개편·계절성 흔들림 완화

# 상권 유형 — 업종 구성과 직결되는 범주다(전통시장의 업종 분포는 발달상권과 다르다).
# 라벨이 아니라 자리의 성격이므로 공실 상태에서도 관측 가능하다.
_SE_CODES = {"A": "golmok", "D": "baldal", "R": "market", "U": "tourist"}

_AGE_COLS = ["AGRDE_10", "AGRDE_20", "AGRDE_30", "AGRDE_40", "AGRDE_50", "AGRDE_60_ABOVE"]
_TMZON = ["00_06", "06_11", "11_14", "14_17", "17_21", "21_24"]
_WEEKDAY = ["MON", "TUES", "WED", "THUR", "FRI"]
_WEEKEND = ["SAT", "SUN"]


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    """숫자 변환 — 원본이 문자열로 오는 필드가 섞여 있다."""
    return pd.to_numeric(df.get(col), errors="coerce").fillna(0.0)


def _recent(df: pd.DataFrame) -> pd.DataFrame:
    """최근 _RECENT_QUARTERS 분기만 남긴다."""
    quarters = sorted(df["STDR_YYQU_CD"].astype(str).unique())[-_RECENT_QUARTERS:]
    return df[df["STDR_YYQU_CD"].astype(str).isin(quarters)]


def _shares(df: pd.DataFrame, cols: list[str], total: pd.Series, prefix: str) -> pd.DataFrame:
    """구성비 컬럼 묶음 — 총량으로 나눠 규모 효과를 제거한다.

    총량(로그)과 구성비를 함께 넣는 이유: 규모와 성격은 다른 축이다. 유동인구 10만의
    발달상권과 1만의 골목상권이 같은 야간 비중을 가질 수 있다.
    """
    safe = total.replace(0, np.nan)
    out = pd.DataFrame(index=df.index)
    for c in cols:
        out[f"{prefix}_{c.lower()}_share"] = (df[c] / safe).fillna(0.0)
    return out


def _load(name: str) -> pd.DataFrame | None:
    rows = load_latest(SLUG13, f"{name}.json")
    if not rows:
        print(f"[trdar_demand] bronze 없음: {name}.json — seoul_trdar 수집 먼저")
        return None
    df = pd.DataFrame(rows)
    df["TRDAR_CD"] = df["TRDAR_CD"].astype(str)
    return df


def build_relm() -> pd.DataFrame | None:
    """상권 기하 — 중심좌표(WGS84)·면적·유형 원핫."""
    df = _load("seoul_trdar_relm")
    if df is None:
        return None
    x = _num(df, "XCNTS_VALUE").to_numpy()
    y = _num(df, "YDNTS_VALUE").to_numpy()
    lon, lat = _TM_TO_WGS84.transform(x, y)

    area = _num(df, "RELM_AR").replace(0, np.nan)
    out = pd.DataFrame({
        "trdar_cd": df["TRDAR_CD"],
        "trdar_nm": df.get("TRDAR_CD_NM", ""),
        "district_id": df.get("district_id", ""),
        "adstrd_cd": df.get("ADSTRD_CD", "").astype(str),
        "trdar_lat": lat,
        "trdar_lon": lon,
        "trdar_area_m2": area,
        "log_trdar_area": np.log1p(area.fillna(0.0)),
    })
    se = df["TRDAR_SE_CD"].astype(str)
    for code, label in _SE_CODES.items():
        out[f"se_{label}"] = (se == code).astype(float)
    return out


def build_flpop() -> pd.DataFrame | None:
    """유동인구 — 총량 로그 + 성/연령/시간대/주말 구성비.

    시간대·연령 프로파일이 이 테이블의 핵심이다. 대분류 업종(카페·음식점·편의점·병원…)은
    체류 시간대와 연령 구성이 다르므로, 거점 원핫이 못 주는 자리별 판별 신호가 된다.
    """
    df = _load("seoul_trdar_flpop")
    if df is None:
        return None
    df = _recent(df)

    tot = _num(df, "TOT_FLPOP_CO")
    feat = pd.DataFrame({"trdar_cd": df["TRDAR_CD"], "flpop_tot": tot})
    feat["flpop_fml_share"] = (_num(df, "FML_FLPOP_CO") / tot.replace(0, np.nan)).fillna(0.0)

    age = pd.DataFrame({c: _num(df, f"{c}_FLPOP_CO") for c in _AGE_COLS}, index=df.index)
    feat = pd.concat([feat, _shares(age, _AGE_COLS, age.sum(axis=1), "flpop")], axis=1)

    tm_cols = [f"TMZON_{t}" for t in _TMZON]
    tm = pd.DataFrame({c: _num(df, f"{c}_FLPOP_CO") for c in tm_cols}, index=df.index)
    feat = pd.concat([feat, _shares(tm, tm_cols, tm.sum(axis=1), "flpop")], axis=1)

    wk = _num(df, "SAT_FLPOP_CO") + _num(df, "SUN_FLPOP_CO")
    allday = wk + sum(_num(df, f"{d}_FLPOP_CO") for d in _WEEKDAY)
    feat["flpop_wkend_share"] = (wk / allday.replace(0, np.nan)).fillna(0.0)

    return feat.groupby("trdar_cd", as_index=False).mean()


def build_selng() -> pd.DataFrame | None:
    """추정매출 — 업종 전체 합산 후 총량 로그 + 시간대/주말 구성비.

    ⚠️ 업종별(SVC_INDUTY) 분해는 만들지 않는다 — 라벨 누출이다.
    """
    df = _load("seoul_trdar_selng")
    if df is None:
        return None
    df = _recent(df)

    amt_cols = ["THSMON_SELNG_AMT", "WKEND_SELNG_AMT", "MDWK_SELNG_AMT"]
    amt_cols += [f"TMZON_{t}_SELNG_AMT" for t in _TMZON]
    agg = pd.DataFrame({c: _num(df, c) for c in amt_cols}, index=df.index)
    agg["trdar_cd"] = df["TRDAR_CD"]
    agg["STDR_YYQU_CD"] = df["STDR_YYQU_CD"]
    # 업종 행 → 상권×분기 합계, 그 다음 분기 평균
    q = agg.groupby(["trdar_cd", "STDR_YYQU_CD"], as_index=False).sum()
    s = q.groupby("trdar_cd", as_index=False).mean(numeric_only=True)

    tot = s["THSMON_SELNG_AMT"]
    out = pd.DataFrame({"trdar_cd": s["trdar_cd"], "selng_tot": tot})
    denom = (s["WKEND_SELNG_AMT"] + s["MDWK_SELNG_AMT"]).replace(0, np.nan)
    out["selng_wkend_share"] = (s["WKEND_SELNG_AMT"] / denom).fillna(0.0)

    tm_cols = [f"TMZON_{t}_SELNG_AMT" for t in _TMZON]
    tm_tot = s[tm_cols].sum(axis=1)
    for c in tm_cols:
        out[f"selng_{c.lower().replace('_selng_amt', '')}_share"] = (
            s[c] / tm_tot.replace(0, np.nan)).fillna(0.0)
    return out


def build_stor() -> pd.DataFrame | None:
    """점포 — 총 점포수·프랜차이즈 비율·개폐업률(점포수 가중).

    ⚠️ 업종별 점포수 분해는 만들지 않는다 — 라벨 누출이다.
    """
    df = _load("seoul_trdar_stor")
    if df is None:
        return None
    df = _recent(df)

    work = pd.DataFrame({
        "trdar_cd": df["TRDAR_CD"],
        "STDR_YYQU_CD": df["STDR_YYQU_CD"],
        "stor_co": _num(df, "STOR_CO"),
        "frc_stor_co": _num(df, "FRC_STOR_CO"),
        # 개폐업률은 업종별 비율이라 단순 합산이 불가 — 점포수 가중합 후 총점포수로 나눈다
        "_opbiz_w": _num(df, "OPBIZ_RT") * _num(df, "STOR_CO"),
        "_clsbiz_w": _num(df, "CLSBIZ_RT") * _num(df, "STOR_CO"),
    })
    q = work.groupby(["trdar_cd", "STDR_YYQU_CD"], as_index=False).sum()
    s = q.groupby("trdar_cd", as_index=False).mean(numeric_only=True)

    safe = s["stor_co"].replace(0, np.nan)
    out = pd.DataFrame({
        "trdar_cd": s["trdar_cd"],
        "stor_co": s["stor_co"],
        "stor_frc_share": (s["frc_stor_co"] / safe).fillna(0.0),
        "stor_opbiz_rt": (s["_opbiz_w"] / safe).fillna(0.0),
        "stor_clsbiz_rt": (s["_clsbiz_w"] / safe).fillna(0.0),
    })
    return out


def build() -> pd.DataFrame | None:
    relm = build_relm()
    if relm is None:
        return None
    out = relm
    for part in (build_flpop(), build_selng(), build_stor()):
        if part is not None:
            out = out.merge(part, on="trdar_cd", how="left")

    # 밀도 = 총량 / 면적(ha). 규모가 아니라 '얼마나 빽빽한 자리인가'가 업종을 가른다.
    ha = (out["trdar_area_m2"] / 10_000.0).replace(0, np.nan)
    for src, name in (("flpop_tot", "log_flpop_density"),
                      ("selng_tot", "log_selng_density"),
                      ("stor_co", "log_stor_density")):
        if src in out.columns:
            out[name] = np.log1p((out[src].fillna(0.0) / ha).fillna(0.0))
    for src, name in (("flpop_tot", "log_flpop"), ("selng_tot", "log_selng"),
                      ("stor_co", "log_stor")):
        if src in out.columns:
            out[name] = np.log1p(out[src].fillna(0.0))

    # selng 은 185/190 상권만 존재 — 결측 상권은 0 으로 두되 관측 여부를 플래그로 남긴다
    # (0 매출과 '데이터 없음'을 모델이 구분할 수 있어야 한다).
    out["has_selng"] = out["selng_tot"].notna().astype(float) if "selng_tot" in out else 0.0
    return out


def main() -> None:
    df = build()
    if df is None:
        return
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = _OUT_DIR / f"{_OUT_NAME}.parquet"
    try:
        df.to_parquet(path, index=False)
    except Exception:
        path = _OUT_DIR / f"{_OUT_NAME}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
    n_dist = df["district_id"].nunique()
    per = df.groupby("district_id").size()
    print(f"[gold] {path.name}: {len(df)}행 × {len(df.columns)}열 "
          f"/ {n_dist}거점 (거점당 상권 평균 {per.mean():.1f}, 최소 {per.min()})")
    single = sorted(per[per <= 1].index)
    if single:
        print(f"[trdar_demand] ⚠️ 상권 1개뿐 → 거점 상수라 GNN 이득 없음: {single}")


if __name__ == "__main__":
    main()
