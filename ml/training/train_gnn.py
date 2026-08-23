"""IndustryGNN 학습 — 점포 노드의 업종 대분류 분류 (업종 추천의 프록시 태스크).

소스:
  gold/platform13/platform_store_graph_nodes.parquet  (kakao 현존 점포)
  gold/platform13/platform_store_graph_edges.parquet  (spatial_knn + same_building + same_chain)
산출:
  ml/artifacts/industry_gnn.pt                        체크포인트(+ 라벨·피처 메타)
  data/gold/platform_industry_recommend.json          서빙용 배치 추천(토치 없는 Vercel 경로)
  ml/mlruns                                           MLflow 실험 industry_gnn

태스크 정의 — "이 자리에 어떤 업종이 맞는가"를 노드 분류로 근사한다. 어떤 점포의 업종을
가리고 주변 구조·입지만으로 맞히도록 학습하면, 같은 모델을 공실 유닛(업종이 비어 있는
자리)에 그대로 적용해 Top-K 업종을 뽑을 수 있다.

결과 해석(현행 = 2026-08-16 수요신호 반영본, 40,388노드·7 대분류·95피처·edge_types=all):
  Top-1 63.84% / Top-3 90.80% (KPI Top-3 70% 달성) · macro-F1 0.2124 · lift +4.4%
  ※ '거점 사전분포'(그 거점 학습셋 최빈 업종)만으로도 Top-1 61.16%/Top-3 89.15% 다.
     게다가 54거점 **전부**에서 최빈 업종이 음식점(전체 61.2%)이라 사전분포는 사실상
     '무조건 음식점'과 같은 답안 — lift +4.4% 는 '거점 정보를 넘어선 이득'이 아니라
     **다수 클래스를 넘어선 이득**으로 읽어야 한다. 그래도 GNN 은 거점 평균이 못 주는
     '자리별' 점수를 주므로(공실 유닛 단위 추천) 제품 가치는 사전분포와 별개다.
  엣지 ablation(2026-07-24, 23,250노드 시절): spatial_knn 만 62.16%/90.8% →
     +same_building 61.66%/90.9% → +same_chain(all) 62.2%/91.1%. 엣지 다양화의
     한계 기여는 대분류 태스크에선 작다.
  라벨을 category 2단계로 내리면 lift 는 +19.8% 로 커지지만 Top-3 는 58.4% 로
     KPI 미달 — 세분 업종은 그래프 정보가 더 필요하나 절대 정확도가 낮다(_labels 주석 참조).

macro-F1 0.21 의 원인 — '편중'이 아니라 '피처 부족'이다 (2026-08-17 --class-weight 실측):
  종전 주석은 "macro-F1 이 낮은 건 음식점 61% 편중 탓"이라고 적었으나, 빈도 역수 균형
  손실로 편중을 제거해 봐도 **macro-F1 은 0.2124 → 0.2286 (+7.6%) 에 그쳤다.** 대신
  Top-1 은 0.6384 → 0.2830, Top-3 는 0.9080 → 0.7791 로 무너져 사전분포(0.6116/0.8915)
  아래로 내려갔다(lift −53.7%). 음식점 가중치를 0.07 까지 눌러 희소 업종을 강제로
  뽑게 했는데도 회수가 거의 없다는 건, 손실 함수가 아니라 **입지 피처에 약국·문화시설을
  가려낼 정보가 애초에 없다**는 뜻이다. → 희소 업종 회수는 손실 재조정이 아니라 새 피처
  (약국↔병원 인접, 문화시설↔se_tourist 상호작용 등)로 풀어야 한다.
  ⚠ 이 수치는 균형 손실에 불리하게 측정됐다 — 조기 종료 기준이 val **Top-1** 이라
     (아래 학습 루프) macro-F1 최고점이 아닌 지점에서 체크포인트가 잡힌다. 즉 0.2286 은
     하한이다. 다만 Top-1/Top-3 붕괴는 손실 정의상 되돌아오지 않으므로 결론은 그대로.

⚠️ 피처는 '공실 상태에서도 관측 가능한 것'만 쓴다. 점포명·체인 여부·자기 카테고리는
   빈 자리에는 존재하지 않으므로 제외했다(넣으면 검증 점수만 오르고 실제 추천에는 못 쓴다).
   남는 것은 입지뿐 — 거점 내 상대좌표·건물 규모·주변 밀집도·거점 원핫.

⚠️ same_chain 엣지는 정의상 같은 업종을 잇고(GS25↔GS25), same_building 도 동종 편향이
   있다(같은 업종대분류 쌍 61.2% vs 무작위 기대 ~42%). --edge-types 로 ablation 을 돌려
   구조 이득과 누출을 분리해 읽는다.

실행:
  python -m ml.training.train_gnn                    학습 + 평가 + 산출물 저장
  python -m ml.training.train_gnn --report           그래프 품질 리포트만
  python -m ml.training.train_gnn --edge-types spatial_knn,same_building   ablation
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

# 출력이 파이프·파일로 가면 Windows 기본 인코딩이 cp949 로 잡혀 로그의 '—' 하나에
# UnicodeEncodeError 로 죽는다 — train_lstm 이 2026-07-22 에 같은 이유로 고친 자리다.
# 여기만 빠져 있어서, 로그를 파일로 남기는 무인 재시도 루프가 **재개 안내 줄에서**
# 매 회 같은 지점에 걸렸다(2026-08-19, 6회 연속). 재개 경로에서만 실행되는 줄이라
# 콘솔로 돌리던 동안에는 드러나지 않았다.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # 재설정 불가 스트림이면 그대로 둔다
    pass

from ml.models.gnn.industry_gnn import IndustryGNN  # noqa: E402

_GOLD = _REPO / "data" / "gold"
_ARTIFACT = _REPO / "ml" / "artifacts" / "industry_gnn.pt"
_RESUME = _REPO / "ml" / "artifacts" / ".train_gnn_resume.pt"
_RECOMMEND_JSON = _GOLD / "platform_industry_recommend.json"
_TRDAR_DEMAND = _GOLD / "features" / "trdar_demand.parquet"
_PAGE_BUILDING = _GOLD / "features" / "page_building.parquet"
_MLRUNS = _REPO / "ml" / "mlruns"

MIN_CLASS_NODES = 10   # 이보다 작은 업종 대분류는 '기타'로 병합
TOP_K = 3              # 추천 Top-K (KPI: Top-3 70%+)
SEED = 42

_M_PER_DEG_LAT = 111000.0
_M_PER_DEG_LON = 88300.0

# TRDAR 상권 단위 공공 수요신호 — build_trdar_demand 산출물에서 쓸 컬럼.
# 명시 목록으로 고정한다: 파케이 컬럼이 늘어도 피처 차원이 조용히 바뀌지 않도록
# (체크포인트의 in_dim 과 어긋나면 서빙이 깨진다).
_DEMAND_COLS: list[str] = [
    # 규모(로그) — 상권이 얼마나 큰가
    "log_flpop", "log_selng", "log_stor", "log_trdar_area",
    # 밀도(로그) — 얼마나 빽빽한 자리인가. 규모와 다른 축이다
    "log_flpop_density", "log_selng_density", "log_stor_density",
    # 상권 성격
    "flpop_fml_share", "flpop_wkend_share", "selng_wkend_share",
    "stor_frc_share", "stor_opbiz_rt", "stor_clsbiz_rt", "has_selng",
    # 연령 구성비 (6)
    "flpop_agrde_10_share", "flpop_agrde_20_share", "flpop_agrde_30_share",
    "flpop_agrde_40_share", "flpop_agrde_50_share", "flpop_agrde_60_above_share",
    # 유동인구 시간대 구성비 (6) — 카페/음식점/편의점의 체류 시간대가 다르다
    "flpop_tmzon_00_06_share", "flpop_tmzon_06_11_share", "flpop_tmzon_11_14_share",
    "flpop_tmzon_14_17_share", "flpop_tmzon_17_21_share", "flpop_tmzon_21_24_share",
    # 매출 시간대 구성비 (6) — 유동인구보다 거점 내 변동이 크다(within 비율 0.44~0.56)
    "selng_tmzon_00_06_share", "selng_tmzon_06_11_share", "selng_tmzon_11_14_share",
    "selng_tmzon_14_17_share", "selng_tmzon_17_21_share", "selng_tmzon_21_24_share",
    # 상권 유형 원핫 — 골목/발달/전통시장/관광특구
    "se_golmok", "se_baldal", "se_market", "se_tourist",
]

# Page 건물 마스터에서 온 자리 단위 물리·대장 피처 — build_page_building_features 산출.
# 수요 컬럼과 같은 이유로 명시 목록으로 고정한다(차원이 조용히 바뀌면 서빙이 깨진다).
_BUILDING_COLS: list[str] = [
    "bld_vacancy_rate",       # 건물 공실률 (Page 핵심 산출)
    "log_bld_capacity",       # 수용 호수
    "bld_floors", "bld_height",
    "bld_com_floor_n", "bld_com_floor_max", "bld_has_ground_floor",
    "bld_licensed", "log_bld_unknown_n",
    "bld_matched",            # 조인 지시자 — 미조인을 0 으로 채우므로 필요하다
]


def load_graph() -> tuple[pd.DataFrame, pd.DataFrame]:
    """platform13(33거점) 그래프 우선, 없으면 garosugil 단일 거점 폴백."""
    for slug in ("platform13", "garosugil"):
        nodes = _GOLD / slug / "platform_store_graph_nodes.parquet"
        edges = _GOLD / slug / "platform_store_graph_edges.parquet"
        if nodes.exists() and edges.exists():
            print(f"[gnn] 그래프 소스: gold/{slug}")
            return pd.read_parquet(nodes), pd.read_parquet(edges)
    raise FileNotFoundError(
        "그래프 gold 없음 — build_gold + build_store_graph_edges 먼저 실행")


def _labels(nodes: pd.DataFrame, level: str = "group") -> tuple[np.ndarray, list[str]]:
    """업종 라벨. `level` 로 태스크 입도를 고른다.

    - `group`(기본) — 수집 기준인 category_group(7종). 서빙이 쓰는 라벨 체계다.
      category_group_name = 음식점/카페/편의점/병원/약국/숙박/문화시설. 이게 없는 옛
      노드(garosugil 단일 거점 gold)는 category 2단계로 폴백한다 — category 1단계는
      카카오의 다른 분류체계(카페가 음식점 하위)라 음식점 78% 로 degenerate 하다.
    - `category2` — category 2단계(≈30클래스) 세분 라벨. Top-1 천장이 피처가 아니라
      태스크 입도 때문이라는 가설을 재는 자리다(feature-platform.md §0). 라벨 체계가
      바뀌므로 **산출물을 저장하지 않는다** — `train()` 이 강제로 save 를 끈다.
    """
    if level not in ("group", "category2"):
        raise ValueError(f"label level 은 group|category2 — 받은 값 {level!r}")
    use_group = (level == "group"
                 and "category_group" in nodes
                 and nodes["category_group"].fillna("").str.len().gt(0).any())
    if use_group:
        raw = nodes["category_group"].fillna("").replace("", "미분류")
    else:
        raw = nodes["category"].fillna("").map(
            lambda c: " > ".join(str(c).split(" > ")[:2]) or "미분류")
    counts = raw.value_counts()
    small = set(counts[counts < MIN_CLASS_NODES].index)
    merged = raw.map(lambda c: "기타" if c in small else c)
    classes = sorted(merged.unique())
    idx = {c: i for i, c in enumerate(classes)}
    return merged.map(idx).to_numpy(), classes


def _demand_block(nodes: pd.DataFrame) -> tuple[np.ndarray, list[str]] | None:
    """노드 → 소속 TRDAR 상권의 공공 수요신호 블록.

    **왜 거점이 아니라 상권 단위인가**: 아래 _features 는 이미 거점 원핫을 넣는다. 거점
    안에서 상수인 값은 원핫이 완전히 표현하므로 붙여도 정보가 0 이다. 서울 상권분석의
    TRDAR 상권은 54거점을 190개로 쪼개므로(거점당 3.5개) 거점 내 변동이 생긴다 —
    실측 within-district 분산 비율 평균 0.46 (build_trdar_demand 참조).

    귀속 규칙: **같은 거점 안에서** 상권 중심좌표가 가장 가까운 상권. 상권 폴리곤이 아니라
    중심점 기준이므로 근사다 — 정확한 PIP 는 폴리곤(TbgisTrdarRelm geometry) 확보 후 과제.
    거점을 넘어선 매칭은 막는다(거점 경계가 상권 경계보다 제품상 우선이다).

    스케일: 이 블록만 z-score 표준화한다. 기존 피처(dx/dy·log_bld_size…)는 건드리지
    않으므로 --no-demand 가 종전 파이프라인을 그대로 재현하고 ablation 이 깨끗해진다.

    반환 None = 수요 테이블 부재(신규 클론 등) → 학습은 종전 피처로 계속한다.
    """
    if not _TRDAR_DEMAND.exists():
        print(f"[gnn] 수요 테이블 없음({_TRDAR_DEMAND.name}) — "
              f"python -m data.pipelines.build_trdar_demand 먼저. 수요 피처 없이 진행")
        return None
    dem = pd.read_parquet(_TRDAR_DEMAND)
    missing = [c for c in _DEMAND_COLS if c not in dem.columns]
    if missing:
        print(f"[gnn] 수요 테이블에 컬럼 없음 {missing} — 수요 피처 없이 진행")
        return None

    lat = pd.to_numeric(nodes["lat"], errors="coerce").fillna(0.0).to_numpy()
    lon = pd.to_numeric(nodes["lon"], errors="coerce").fillna(0.0).to_numpy()
    did = nodes["district_id"].fillna("").astype(str).to_numpy()

    vals = dem[_DEMAND_COLS].astype(float).to_numpy()
    block = np.zeros((len(nodes), len(_DEMAND_COLS)), dtype=np.float64)
    dist_m = np.zeros(len(nodes), dtype=np.float64)
    matched = np.zeros(len(nodes), dtype=bool)

    for d, grp in dem.groupby("district_id"):
        sel = np.flatnonzero(did == str(d))
        if sel.size == 0:
            continue
        # 등장방형 근사 — services/districts.py _dist_m 과 동일 계수(서울 위도 37.5°)
        gy = (lat[sel][:, None] - grp["trdar_lat"].to_numpy()[None, :]) * _M_PER_DEG_LAT
        gx = (lon[sel][:, None] - grp["trdar_lon"].to_numpy()[None, :]) * _M_PER_DEG_LON
        dd = np.hypot(gx, gy)
        near = dd.argmin(axis=1)
        block[sel] = vals[grp.index.to_numpy()[near]]
        dist_m[sel] = dd[np.arange(sel.size), near]
        matched[sel] = True

    if not matched.all():
        lost = sorted(set(did[~matched]))
        print(f"[gnn] ⚠️ 수요 테이블에 없는 거점 {len(lost)}곳 → 0 채움: {lost[:5]}")

    # 상권 중심까지의 거리 = '상권 코어에서 얼마나 벗어난 자리인가'. 거점 원핫이 못 주는
    # 자리 단위 신호라 함께 넣는다.
    block = np.column_stack([block, np.log1p(dist_m)])
    names = list(_DEMAND_COLS) + ["log_dist_to_trdar_m"]

    mu = block.mean(axis=0)
    sd = block.std(axis=0)
    sd[sd == 0] = 1.0
    return np.nan_to_num((block - mu) / sd), names


def _building_block(nodes: pd.DataFrame) -> tuple[np.ndarray, list[str]] | None:
    """노드 → 자리가 속한 **건물의 물리·대장 특성** 블록 (Page 산출).

    **왜 이 블록인가**: 종전 95피처 중 자리마다 값이 달라지는 것은 5개뿐이고
    (dx·dy·상권중심거리·주변밀집도·건물규모) 나머지 90개는 거점 상수다. 그래서 거점
    사전분포가 원리적으로 못 맞히는 자리의 Top-3 회수율(off-prior)이 낮았다. 이 블록은
    거점 안에서 건물마다 변하는 첫 실데이터다.

    **실측(2026-08-17, 동일 조건 600에포크·patience 80 ablation)**:

      지표              95열      105열     변화
      test Top-1       0.6397 →  0.6512    +1.2%p
      test Top-3       0.9082 →  0.9182    +1.0%p  (방어 게이트 통과 유지)
      test macro-F1    0.2185 →  0.2593   +18.7%
      test off-prior   0.2805 →  0.3592   +28.1%  ← 상대 최대폭
      lift vs 사전분포    4.6%  →   6.5%

    off-prior 가 가장 크게 올랐다는 것이 **§9 순도 분석의 검증**이다 — 순도 100% 인
    지표가 자리 신호에 가장 민감하고, 순도 2.3% 인 Top-3 정확도는 +1.0%p 만 움직였다.
    macro-F1 +18.7% 는 균형 손실의 한계(+7.6%)를 크게 넘어, 병목이 손실 함수가 아니라
    **피처**였다는 진단(커밋 32c9673)을 확인해 준다.
    단 값싼 규칙 하한(42.42%)은 아직 못 넘었다 — 남은 레버는 Platform 감성(막힘 6번)과
    약국↔병원 인접 구조다.
    → docs/finding-sequence-and-accuracy-2026-08-17.md §9·§10

    누출 방지: 건물 마스터의 `industry`(대표 업종)·`occ_floors`·`active`·`stores` 는
    **쓰지 않는다** — 현재 입주 업종에서 파생된 값이라 라벨이다. 남기는 것은 그 자리가
    공실이어도 관측 가능한 대장·물리 속성뿐이다(build_page_building_features docstring).

    스케일: 이 블록만 z-score 표준화한다(수요 블록과 같은 방식) — `--no-building` 이
    종전 파이프라인을 그대로 재현해 ablation 이 깨끗해진다.

    반환 None = 피처 테이블 부재 → 학습은 종전 피처로 계속한다.
    """
    if not _PAGE_BUILDING.exists():
        print(f"[gnn] 건물 피처 테이블 없음({_PAGE_BUILDING.name}) — "
              f"python -m data.pipelines.build_page_building_features 먼저. "
              f"건물 피처 없이 진행")
        return None
    tbl = pd.read_parquet(_PAGE_BUILDING)
    missing = [c for c in _BUILDING_COLS if c not in tbl.columns]
    if missing:
        print(f"[gnn] 건물 테이블에 컬럼 없음 {missing} — 건물 피처 없이 진행")
        return None

    # node_id 로 정렬 결합한다. 좌표 재조인이 아니라 키 조인이라 순서가 어긋날 수 없다.
    m = tbl.set_index("node_id").reindex(nodes["node_id"].to_numpy())
    block = m[_BUILDING_COLS].astype(float).to_numpy()
    block = np.nan_to_num(block)          # 테이블에 없는 노드 = 미조인(전부 0)

    hit = float(block[:, _BUILDING_COLS.index("bld_matched")].mean())
    sd = block.std(axis=0)
    sd[sd == 0] = 1.0
    block = (block - block.mean(axis=0)) / sd
    print(f"[gnn] 건물 피처 {len(_BUILDING_COLS)}열 결합 · 건물 조인율 {hit:.1%}")
    return block, list(_BUILDING_COLS)


def _features(nodes: pd.DataFrame, edges: pd.DataFrame,
              use_demand: bool = True,
              use_building: bool = True) -> tuple[np.ndarray, list[str]]:
    """공실 상태에서도 관측 가능한 입지 피처만 구성한다."""
    lat = pd.to_numeric(nodes["lat"], errors="coerce").to_numpy()
    lon = pd.to_numeric(nodes["lon"], errors="coerce").to_numpy()
    did = nodes["district_id"].fillna("").astype(str)

    # 거점 중심 기준 상대좌표(km) — 절대좌표를 그대로 쓰면 거점 식별자와 중복된다
    cen_lat = did.map(pd.Series(lat).groupby(did.to_numpy()).mean()).to_numpy()
    cen_lon = did.map(pd.Series(lon).groupby(did.to_numpy()).mean()).to_numpy()
    dy = (lat - cen_lat) * _M_PER_DEG_LAT / 1000.0
    dx = (lon - cen_lon) * _M_PER_DEG_LON / 1000.0

    # 건물 규모 — 같은 도로명주소를 공유하는 점포 수(빈 자리도 건물은 관측된다)
    addr = nodes.get("road_address", pd.Series([""] * len(nodes))).fillna("").astype(str)
    bld_size = addr.map(addr.value_counts()).to_numpy()
    bld_size = np.where(addr.to_numpy() == "", 1, bld_size)

    # 주변 밀집도 — 공간 엣지 차수(입지 특성이라 공실이어도 관측 가능)
    sp = edges[edges["type"] == "spatial_knn"] if "type" in edges else edges
    deg = Counter(sp["src"]) + Counter(sp["dst"])
    knn_deg = nodes["node_id"].map(lambda n: deg.get(n, 0)).to_numpy()

    dist_oh = pd.get_dummies(did, prefix="d").astype(float)
    x = np.column_stack([dx, dy, np.log1p(bld_size), np.log1p(knn_deg),
                         dist_oh.to_numpy()])
    names = ["dx_km", "dy_km", "log_bld_size", "log_knn_deg"] + list(dist_oh.columns)

    if use_demand:
        block = _demand_block(nodes)
        if block is not None:
            x = np.column_stack([x, block[0]])
            names += block[1]
            print(f"[gnn] 수요 피처 {len(block[1])}열 결합 → 총 {len(names)}열")
    if use_building:
        block = _building_block(nodes)
        if block is not None:
            x = np.column_stack([x, block[0]])
            names += block[1]
            print(f"[gnn] 건물 피처 결합 → 총 {len(names)}열")
    return np.nan_to_num(x).astype(np.float32), names


def _edge_index(nodes: pd.DataFrame, edges: pd.DataFrame,
                keep: set[str] | None) -> torch.Tensor:
    idx = {nid: i for i, nid in enumerate(nodes["node_id"])}
    e = edges
    if keep is not None and "type" in e:
        e = e[e["type"].isin(keep)]
    src = e["src"].map(idx).to_numpy()
    dst = e["dst"].map(idx).to_numpy()
    # 무방향 → 양방향 전개
    ei = np.concatenate([np.stack([src, dst]), np.stack([dst, src])], axis=1)
    return torch.tensor(ei, dtype=torch.long)


def _split(y: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, ...]:
    """클래스별 층화 60/20/20 분할 — 희소 클래스가 한 쪽에 몰리지 않게."""
    train = np.zeros(len(y), bool)
    val = np.zeros(len(y), bool)
    test = np.zeros(len(y), bool)
    for c in np.unique(y):
        i = np.flatnonzero(y == c)
        rng.shuffle(i)
        n_tr, n_va = int(len(i) * 0.6), int(len(i) * 0.8)
        train[i[:n_tr]] = True
        val[i[n_tr:n_va]] = True
        test[i[n_va:]] = True
    return train, val, test


def _neighbor_label_block(ei: torch.Tensor, y: np.ndarray, train_mask: np.ndarray,
                          n_cls: int, n_nodes: int) -> tuple[np.ndarray, list[str]]:
    """이웃의 업종 분포 — **학습 라벨만** 집계한다 (2026-08-23).

    §9 순도 분석이 남긴 레버 중 하나가 "약국↔병원 인접 구조"였다. 지금 피처 105개 중
    자리마다 값이 달라지는 것은 입지·건물 15개뿐이고 나머지 90개는 거점 상수라
    (원핫 54 + TRDAR 36), off-prior 자리에서 모델이 기댈 것이 거의 없다.
    이웃이 무슨 업종인가는 **자리마다 다르고 거점 원핫이 표현할 수 없는** 신호다.

    ## 누출을 막는 두 가지

    1. **train 마스크의 라벨만 센다.** val/test 노드의 업종을 이웃으로 세면 평가
       대상의 정답이 입력에 흘러든다. 여기서 트인 구멍은 지표가 조용히 좋아지는
       쪽이라 눈치채기 어렵다.
    2. **자기 자신을 뺀다.** self-loop 가 섞이면 자기 라벨이 그대로 입력이 되어
       off-prior 가 100% 로 튄다 — 그건 학습이 아니라 정답 복사다.

    GNN 의 message passing 과 겹치지 않는가: 겹치지 않는다. 컨볼루션은 이웃의
    **피처**를 섞지 라벨을 섞지 않는다. 라벨 전파는 여기서만 들어온다.

    ## 실측 결과 (2026-08-23) — **개선 없음. 기본값 off.**

    | 지표 | 105열(기존) | 113열(+이웃) | |
    |---|---|---|---|
    | off-prior Top-3 | 37.63% | **36.49%** | −1.14%p |
    | Top-3 | 91.86% | 91.40% | −0.46%p |
    | macro-F1 | 0.2622 | **0.2803** | +6.9% |

    off-prior 표본 877 에서 표준오차 ≈1.63%p 이므로 −1.14%p 는 **1σ 이내 — 유의하지
    않다.** 올리지도 내리지도 못했다는 것이 정직한 결론이고, 게이트 지표가 나아지지
    않았으므로 산출물은 되돌렸다.

    왜 안 올랐는가에 대한 가설 둘(둘 다 미검증):
    ① GNN 의 message passing 이 이미 같은 정보를 쓰고 있어 입력단 라벨 전파가
       중복이다. 그렇다면 이 피처로는 영영 안 오른다.
    ② **조기 종료 기준이 이 지표에 안 맞는다.** val top1 로 멈추는데(ep113 종료)
       top1 은 거점 사전분포에 지배되는 지표다 — off-prior 가 최적화되기 전에 멈췄을
       수 있다. 이쪽이면 `--neighbor` 에 off-prior 기준 조기종료를 붙여 재시도할 값이
       있다. macro-F1 만 +6.9% 오른 것이 ②를 약하게 지지한다.

    반환: (n_nodes × (n_cls+1)) 블록 — 클래스별 비율 + 이웃 수 log.
    """
    src = ei[0].numpy()
    dst = ei[1].numpy()
    keep = train_mask[src] & (src != dst)
    counts = np.zeros((n_nodes, n_cls), dtype=np.float64)
    np.add.at(counts, (dst[keep], y[src[keep]]), 1.0)
    total = counts.sum(axis=1, keepdims=True)
    frac = counts / np.maximum(total, 1.0)     # 이웃 0 이면 전부 0 — "모른다"로 남는다
    block = np.hstack([frac, np.log1p(total)])
    names = [f"nb_frac_{c}" for c in range(n_cls)] + ["log_nb_n"]
    print(f"[gnn] 이웃 라벨 피처 {len(names)}열 결합 · 이웃 있는 노드 "
          f"{float((total > 0).mean()):.1%} (train 라벨만, self 제외)")
    return block, names


def _topk_acc(logits: torch.Tensor, y: torch.Tensor, k: int) -> float:
    k = min(k, logits.shape[1])
    top = logits.topk(k, dim=1).indices
    return float((top == y.unsqueeze(1)).any(dim=1).float().mean())


def _macro_f1(pred: np.ndarray, y: np.ndarray, n_cls: int) -> float:
    f1s = []
    for c in range(n_cls):
        tp = int(((pred == c) & (y == c)).sum())
        fp = int(((pred == c) & (y != c)).sum())
        fn = int(((pred != c) & (y == c)).sum())
        if tp + fp + fn == 0:
            continue
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return float(np.mean(f1s)) if f1s else 0.0


def _district_top3(y: np.ndarray, did: np.ndarray,
                   train: np.ndarray) -> tuple[dict[str, list[int]], int]:
    """거점별 상위 TOP_K 업종 — **train 으로만** 센다(누출 방지).

    `_baselines` 와 `_offprior_top3` 가 같은 표를 쓴다. 두 곳에서 따로 세면 한쪽만
    고쳐졌을 때 '기준선은 0 인데 off-prior 는 0 이 아닌' 모순이 조용히 생긴다.
    반환: (거점→업종코드 상위 K, 전역 최빈 업종코드)
    """
    major = Counter(y[train]).most_common(1)[0][0]
    out: dict[str, list[int]] = {}
    for d in np.unique(did):
        m = train & (did == d)
        out[d] = [c for c, _ in Counter(y[m]).most_common(TOP_K)] if m.any() else [major]
    return out, major


def _baselines(y: np.ndarray, did: np.ndarray, train: np.ndarray,
               test: np.ndarray, n_cls: int) -> dict[str, float]:
    """모델 없이 얻는 점수 — '20% 향상' 을 재는 기준선."""
    top3, major = _district_top3(y, did, train)

    # ① 전역 최빈 클래스
    acc_major = float((y[test] == major).mean())

    # ② 거점별 최빈 클래스(거점 사전분포) — 실질적인 '모델 없음' 답안
    pred_prior = np.array([top3.get(d, [major])[0] for d in did[test]])
    acc_prior = float((pred_prior == y[test]).mean())

    # ③ 거점 사전분포 Top-3
    acc_prior_top3 = float(np.mean([
        yt in top3.get(d, [major]) for yt, d in zip(y[test], did[test])]))

    return {"baseline_major_top1": round(acc_major, 4),
            "baseline_district_prior_top1": round(acc_prior, 4),
            "baseline_district_prior_top3": round(acc_prior_top3, 4)}


def _offprior_top3(logits: torch.Tensor, y: np.ndarray, did: np.ndarray,
                   train: np.ndarray, test: np.ndarray) -> dict[str, float | int]:
    """거점 사전분포가 **원리적으로 못 맞히는** 자리에서의 Top-3 회수율.

    test 자리 중 실제 업종이 그 거점의 상위 TOP_K 밖인 것만 남겨서 Top-3 회수율을 잰다.
    거점 사전분포의 이 부분집합 점수는 **정의상 0** 이므로, 값 전부가 '자리별 신호'에서
    온다 — 지표에서 거점 평균의 몫을 제거한 것이다.

    왜 이 지표인가 (2026-08-17 분석):
      피처 95개 중 자리마다 값이 달라지는 것은 **5개**뿐이고(dx·dy·상권중심거리·주변밀집도
      ·건물규모) 나머지 90개는 거점 상수다(원핫 54 + TRDAR 36). 그래서 집계 지표는 거의
      전부 거점 평균으로 설명된다 — Top-3 정확도는 값의 **97.7%** 가 거점 사전분포
      몫이어서, Platform·Page 에 무엇을 넣어도 숫자가 안 움직인다. Top-1 70% 가 실패한
      구조와 같다. 이 지표는 그 몫이 0 이라 두 트랙의 배선 성과만 잡아낸다.
      → docs/finding-sequence-and-accuracy-2026-08-17.md

    ⚠ 단독으로 게이트에 쓰면 안 된다. 희소 업종을 무조건 Top-3 에 밀어 넣어 올릴 수
      있으므로, 방어용으로 `test_top3`(≥70%) 게이트를 반드시 함께 유지한다.
    """
    top3, major = _district_top3(y, did, train)
    off = np.array([yt not in top3.get(d, [major])
                    for yt, d in zip(y, did)]) & test
    n = int(off.sum())
    if n == 0:
        # 모든 test 자리가 거점 top-3 안 — 라벨 입도가 낮으면 실제로 일어난다.
        return {"test_offprior_top3": None, "offprior_nodes": 0}
    k = min(TOP_K, logits.shape[1])
    hit = (logits[torch.tensor(off)].topk(k, dim=1).indices
           == torch.tensor(y[off]).unsqueeze(1)).any(dim=1).float().mean()
    return {"test_offprior_top3": round(float(hit), 4), "offprior_nodes": n}


def quality_report() -> dict:
    """학습 가능성 판단용 그래프 품질 요약."""
    nodes, edges = load_graph()
    n = len(nodes)
    y, classes = _labels(nodes)
    counts = Counter(y)
    idx = {nid: i for i, nid in enumerate(nodes["node_id"])}
    ei = np.array([[idx[s], idx[d]] for s, d in zip(edges["src"], edges["dst"])])
    deg = np.bincount(ei.ravel(), minlength=n)
    rep = {
        "nodes": n, "edges_undirected": len(edges), "classes": len(classes),
        "mean_degree": round(float(deg.mean()), 2),
        "isolated_nodes": int((deg == 0).sum()),
        "mean_dist_m": round(float(edges["dist_m"].mean()), 1),
    }
    if "type" in edges:
        rep["by_type"] = {k: int(v) for k, v in edges["type"].value_counts().items()}
    print("[gnn·quality]", rep)
    top = [(classes[c], n_) for c, n_ in counts.most_common(8)]
    print(f"  업종 대분류 상위: {dict(top)}")
    return rep


def train(edge_types: set[str] | None = None, epochs: int = 400,
          hidden: int = 128, lr: float = 0.01, weight_decay: float = 5e-4,
          patience: int = 50, save: bool = True, use_demand: bool = True,
          use_building: bool = True, use_neighbor: bool = False,
          resume: bool = True, ckpt_every: int = 25,
          label_level: str = "group", class_weight: bool = False) -> dict:
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)

    if save and class_weight:
        # 균형 손실은 다수 클래스(음식점 61%)를 일부러 덜 맞힌다 — 그 대가로 얻는
        # macro-F1 은 실측 +7.6% 뿐인데 top-1 은 0.64→0.28 로 무너진다(docstring 참조).
        # 진단용 런이므로 서빙 산출물과 섞지 않는다.
        print("[gnn] class_weight=True — 실험 런이므로 산출물 저장을 끈다")
        save = False
    if save and label_level != "group":
        # 서빙(json·체크포인트)은 7종 대분류 어휘를 전제한다. 세분 라벨 런이 그걸
        # 덮어쓰면 /recommend-industry 응답의 업종명이 조용히 바뀐다.
        print(f"[gnn] label_level={label_level} — 실험 런이므로 산출물 저장을 끈다")
        save = False

    nodes, edges = load_graph()
    nodes = nodes.reset_index(drop=True)
    y_np, classes = _labels(nodes, level=label_level)
    x_np, feat_names = _features(nodes, edges, use_demand=use_demand,
                                 use_building=use_building)
    ei = _edge_index(nodes, edges, edge_types)
    did = nodes["district_id"].fillna("").astype(str).to_numpy()

    y = torch.tensor(y_np, dtype=torch.long)
    tr, va, te = _split(y_np, rng)
    # 이웃 라벨 블록은 **분할을 안 뒤에야** 만들 수 있다(train 라벨만 쓰므로).
    # 그래서 _features 안이 아니라 여기서 붙인다.
    if use_neighbor:
        nb, nb_names = _neighbor_label_block(ei, y_np, tr, len(classes), len(nodes))
        x_np = np.hstack([x_np, nb]).astype(np.float32)
        feat_names = feat_names + nb_names
    x = torch.tensor(x_np)
    m_tr, m_va, m_te = (torch.tensor(m) for m in (tr, va, te))

    model = IndustryGNN(x.shape[1], len(classes), hidden=hidden)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    # 균형 손실 가중치 — 학습셋 빈도의 역수(정규화). train 마스크로만 세서 누출을 막는다.
    w = None
    if class_weight:
        cnt = np.bincount(y_np[tr], minlength=len(classes)).astype(np.float64)
        inv = np.divide(1.0, cnt, out=np.zeros_like(cnt), where=cnt > 0)
        w = torch.tensor((inv / inv.sum() * len(classes)), dtype=torch.float32)
        print(f"[gnn] class_weight: {dict(zip(classes, w.round(decimals=2).tolist()))}")

    # ── 크래시 내성: 주기적 체크포인트 + 재개 ──────────────────────────
    # 이 머신에서 학습이 무작위 지점(ep0~300)에서 세그폴트한다 — 105열·95열 양쪽에서
    # 나고 스레드 변수를 전부 1로 묶어도 재현된다(2026-08-17 기준 105열 11회 중 1회 완주).
    # 원인 규명 전까지는 **진행이 날아가지 않게** 하는 것이 우선이라, ckpt_every 에포크마다
    # 상태를 떨어뜨리고 다음 실행이 이어받는다. 모델에 dropout 이 있으므로 torch RNG 상태도
    # 같이 저장해야 재개 궤적이 연속 실행과 어긋나지 않는다.
    # sig 가 다르면 이어붙이지 않는다 — 피처 수·라벨 입도가 바뀐 재개 파일을 물면
    # 엉뚱한 모델을 학습하면서 조용히 성공한 것처럼 보인다.
    sig = {"in_dim": int(x.shape[1]), "classes": len(classes),
           "label_level": label_level, "class_weight": int(class_weight),
           "hidden": hidden, "epochs": epochs, "patience": patience}
    start_ep, best_val, best_state, bad = 1, -1.0, None, 0
    if resume and _RESUME.exists():
        # 저장 도중 죽으면 파일이 깨진다 — 무인 재시도 루프에서 그게 매 회 예외가 되면
        # 크래시 내성을 넣은 의미가 사라지므로, 못 읽으면 버리고 처음부터 간다.
        try:
            ck = torch.load(_RESUME, map_location="cpu", weights_only=False)
        except Exception as e:
            print(f"[gnn] 재개 파일이 손상됐다({type(e).__name__}) — 버리고 처음부터 학습")
            _RESUME.unlink(missing_ok=True)
            ck = {}
        if ck.get("sig") == sig:
            model.load_state_dict(ck["model"])
            opt.load_state_dict(ck["opt"])
            torch.set_rng_state(ck["rng"])
            start_ep, best_val, bad = ck["ep"] + 1, ck["best_val"], ck["bad"]
            best_state = ck["best_state"]
            print(f"[gnn] 재개 — ep{ck['ep']} 다음부터 (best val {best_val:.4f})")
        else:
            print("[gnn] 재개 파일이 현재 설정과 달라 무시한다 — 처음부터 학습")

    for ep in range(start_ep, epochs + 1):
        model.train()
        opt.zero_grad()
        out = model(x, ei)
        loss = F.nll_loss(out[m_tr], y[m_tr], weight=w)
        loss.backward()
        opt.step()

        model.eval()
        with torch.no_grad():
            logits = model(x, ei)
            v = _topk_acc(logits[m_va], y[m_va], 1)
        if v > best_val:
            best_val, bad = v, 0
            best_state = {k: t.clone() for k, t in model.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                print(f"  조기 종료 ep{ep} (val top1 {best_val:.4f})")
                break
        if ckpt_every and ep % ckpt_every == 0:
            # 임시 파일에 쓰고 원자적으로 바꿔친다 — 저장 중 죽어도 직전 체크포인트는 산다
            _RESUME.parent.mkdir(parents=True, exist_ok=True)
            tmp = _RESUME.with_suffix(".tmp")
            torch.save({"sig": sig, "ep": ep, "model": model.state_dict(),
                        "opt": opt.state_dict(), "rng": torch.get_rng_state(),
                        "best_val": best_val, "bad": bad,
                        "best_state": best_state}, tmp)
            tmp.replace(_RESUME)
        if ep % 50 == 0:
            print(f"  ep{ep:4d} loss {float(loss.detach()):.4f} · val top1 {v:.4f}")

    # 여기 왔으면 완주(또는 조기 종료)다 — 재개 파일은 다음 학습을 오염시키므로 지운다
    _RESUME.unlink(missing_ok=True)
    if best_state:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        logits = model(x, ei)
    pred = logits.argmax(1).numpy()

    metrics = {
        "test_top1": round(_topk_acc(logits[m_te], y[m_te], 1), 4),
        f"test_top{TOP_K}": round(_topk_acc(logits[m_te], y[m_te], TOP_K), 4),
        "test_macro_f1": round(_macro_f1(pred[te], y_np[te], len(classes)), 4),
        "val_top1": round(best_val, 4),
        **_baselines(y_np, did, tr, te, len(classes)),
        **_offprior_top3(logits, y_np, did, tr, te),
    }
    base = metrics["baseline_district_prior_top1"]
    metrics["lift_vs_district_prior_pct"] = (
        round((metrics["test_top1"] - base) / base * 100, 1) if base else None)
    metrics.update({"nodes": len(nodes), "edges_used": int(ei.shape[1] // 2),
                    "classes": len(classes), "features": len(feat_names),
                    "label_level": label_level,
                    "class_weight": int(class_weight),
                    "demand_features": int(any(n in feat_names for n in _DEMAND_COLS)),
                    "building_features": int(any(n in feat_names
                                                 for n in _BUILDING_COLS)),
                    "neighbor_label_features": int(any(n.startswith("nb_frac_")
                                                       for n in feat_names)),
                    "edge_types": ",".join(sorted(edge_types)) if edge_types else "all"})
    print("[gnn·metrics]", metrics)

    if save:
        _save_artifacts(model, nodes, classes, feat_names, logits, metrics,
                        hidden=hidden)
    _log_mlflow(metrics, {"hidden": hidden, "lr": lr, "epochs": epochs,
                          "weight_decay": weight_decay})
    return metrics


def _save_artifacts(model: IndustryGNN, nodes: pd.DataFrame, classes: list[str],
                    feat_names: list[str], logits: torch.Tensor,
                    metrics: dict, hidden: int) -> None:
    _ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "classes": classes,
                "feature_names": feat_names, "hidden": hidden,
                "in_dim": len(feat_names), "metrics": metrics}, _ARTIFACT)
    print(f"[gnn] 체크포인트: {_ARTIFACT}")

    # 서빙용 배치 추천 — Vercel 서버리스에는 torch 를 싣지 않으므로 LSTM forecast json 과
    # 같은 방식으로 미리 계산해 둔다. 키는 공실 유닛이 아니라 그래프 노드(=현존 점포 자리)
    # 이므로, 백엔드는 조회 좌표에서 가장 가까운 노드의 추천을 쓴다.
    prob = torch.exp(logits)
    topk = prob.topk(min(TOP_K, len(classes)), dim=1)
    out: dict[str, dict] = {}
    for i, (nid, did) in enumerate(zip(nodes["node_id"], nodes["district_id"])):
        out.setdefault(str(did), {})[str(nid)] = {
            "lat": float(pd.to_numeric(nodes["lat"].iloc[i], errors="coerce") or 0.0),
            "lon": float(pd.to_numeric(nodes["lon"].iloc[i], errors="coerce") or 0.0),
            "top": [{"industry": classes[int(c)], "score": round(float(p), 4)}
                    for c, p in zip(topk.indices[i], topk.values[i])],
        }
    _RECOMMEND_JSON.parent.mkdir(parents=True, exist_ok=True)
    _RECOMMEND_JSON.write_text(
        json.dumps({"model": "industry-gnn", "metrics": metrics, "districts": out},
                   ensure_ascii=False), encoding="utf-8")
    print(f"[gnn] 서빙 json: {_RECOMMEND_JSON} ({len(nodes)}노드)")


def _log_mlflow(metrics: dict, params: dict) -> None:
    try:
        import mlflow
    except ImportError:
        return
    mlflow.set_tracking_uri(_MLRUNS.as_uri())
    mlflow.set_experiment("industry_gnn")
    with mlflow.start_run():
        mlflow.log_params(params)
        mlflow.log_metrics({k: v for k, v in metrics.items()
                            if isinstance(v, (int, float)) and v is not None})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="품질 리포트만 출력")
    ap.add_argument("--edge-types", default=None,
                    help="쉼표 구분 (spatial_knn,same_building,same_chain)")
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--hidden", type=int, default=128)
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--neighbor", action="store_true",
                    help="이웃 업종 분포 피처를 켠다(실험 — 08-23 실측에서 off-prior "
                         "37.63%%→36.49%% 로 유의한 개선 없음. _neighbor_label_block 참조)")
    ap.add_argument("--no-demand", action="store_true",
                    help="TRDAR 공공 수요신호 제외 — 종전 파이프라인 재현(ablation 기준선)")
    ap.add_argument("--no-resume", action="store_true",
                    help="재개 파일을 무시하고 처음부터 학습(기본은 이어받는다)")
    ap.add_argument("--ckpt-every", type=int, default=25,
                    help="N에포크마다 재개 체크포인트 저장. 0 이면 끈다")
    ap.add_argument("--no-building", action="store_true",
                    help="Page 건물 물리·대장 피처 제외 — 08-17 이전 95피처 재현(ablation)")
    ap.add_argument("--label-level", default="group", choices=("group", "category2"),
                    help="라벨 입도. category2 는 세분 업종 실험(산출물 저장 안 함)")
    ap.add_argument("--patience", type=int, default=50)
    ap.add_argument("--class-weight", action="store_true",
                    help="빈도 역수 균형 손실 — macro-F1 이 낮은 원인이 라벨 편중인지 "
                         "피처 부족인지 가르는 진단용. 2026-08-17 실측 결과 '피처 부족' "
                         "쪽이라 회수 효과는 미미하다(모듈 docstring 참조). 산출물 저장 안 함")
    a = ap.parse_args()
    if a.report:
        quality_report()
    else:
        types = set(a.edge_types.split(",")) if a.edge_types else None
        train(edge_types=types, epochs=a.epochs, hidden=a.hidden,
              save=not a.no_save, use_demand=not a.no_demand,
              use_neighbor=a.neighbor,
              use_building=not a.no_building,
              resume=not a.no_resume, ckpt_every=a.ckpt_every,
              label_level=a.label_level, patience=a.patience,
              class_weight=a.class_weight)
