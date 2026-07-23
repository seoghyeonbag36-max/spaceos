"""[Platform·GNN] 점포 그래프 엣지 — 공간 kNN + 동일 건물 + 체인.

소스: gold/{slug}/platform_store_graph_nodes.parquet (kakao 현존 점포)
산출: gold/{slug}/platform_store_graph_edges.parquet
  src, dst   node_id 쌍 (무방향 — 한 쌍당 1행, GNN 입력 시 양방향 전개)
  dist_m     두 점포 간 거리(m, 등장방형 근사)
  rank       src 기준 최근접 순위(1=최근접) — spatial_knn 만 유효, 그 외 0
  type       엣지 종류 (아래)

엣지 종류
  spatial_knn    k=5 최근접 + 최대 반경 150m. 거점 블록 스케일의 물리적 근접.
  same_building  동일 도로명주소(road_address_name). 같은 건물 입점은 집객·고객 공유의
                 관측 가능한 프록시다. 카카오 주소 보유율 99.6%.
  same_chain     동일 상호 3곳 이상(GS25·스타벅스 등). 150m 캡 때문에 spatial_knn 만으로는
                 그래프가 거점별로 완전히 끊겨 27개 컴포넌트가 된다 — 체인 엣지가 거점 간
                 유일한 연결이다.

⚠️ 라벨 누출 주의: same_chain 은 정의상 같은 업종을 잇는다(GS25 ↔ GS25). same_building 도
   같은 업종대분류 쌍 비율이 61.2%(무작위 쌍 기대 ~42%)로 동종 편향이 있다. 노드 업종
   분류로 학습할 때는 type 으로 필터해 ablation 을 돌리고, same_chain 포함 성능은 낙관
   편향으로 읽어야 한다.

TODO(GNN): 리뷰 유사도 엣지는 보류 — 네이버 블로그 검색 API 가 본문이 아닌 ~150자
   스니펫만 주어 점포명 동시 언급이 8,554건 중 15건(0.2%)뿐이다(2026-07-23 측정).
   점포 단위 리뷰 원문(플레이스 리뷰)은 공식 API 가 없다. LOCALDATA 인허가 노드 통합
   (entity resolution)도 미구현.

실행: python -m data.pipelines.build_store_graph_edges [--platform13]
"""
from __future__ import annotations

import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from data.collectors.common import GOLD
from data.config.garosugil import SLUG

_NODES = GOLD / SLUG / "platform_store_graph_nodes.parquet"
_EDGES = GOLD / SLUG / "platform_store_graph_edges.parquet"

K_NEIGHBORS = 5
MAX_DIST_M = 150.0

# 대형 건물(IFC 46개 점포 등)을 완전 그래프로 이으면 한 건물이 1,035 엣지를 만들어
# 그래프를 지배한다. 이 크기를 넘으면 클리크 대신 링(각 노드를 뒤 2개와 연결, 차수 4)으로
# 잇는다 — 건물의 연결성은 유지하면서 엣지 수는 노드 수에 선형이 된다.
MAX_CLIQUE = 12
RING_SPAN = 2
MIN_CHAIN_STORES = 3  # 이 이상 등장한 상호를 체인으로 본다

# 서울 위도(37.5°) 근방 등장방형 근사 — services/districts.py _dist_m 과 동일 계수
_M_PER_DEG_LAT = 111000.0
_M_PER_DEG_LON = 88300.0

_BRANCH = re.compile(r"(\d+호)?점$")  # "가로수길점"·"신사1호점" 접미사


def _chain_key(name: str) -> str:
    """상호에서 체인 식별자 추출 — 첫 공백 토큰에서 지점 접미사를 뗀다.

    "스타벅스 가로수길점" → "스타벅스" / "GS25 신사역점" → "GS25".
    띄어쓰기 없는 "이마트24신사점" 류는 여기서 못 잡고, 호출부에서 이미 확정된
    체인 토큰으로 prefix 재매칭해 보완한다.
    """
    head = str(name).strip().split()[0] if str(name).strip() else ""
    return _BRANCH.sub("", head).strip()


def _spatial_edges(df: pd.DataFrame) -> list[dict]:
    """cKDTree 기반 k 최근접(≤150m). 노드 2만+ 에서 n² 거리행렬은 메모리가 터진다."""
    xy = np.column_stack([df["lon"].to_numpy() * _M_PER_DEG_LON,
                          df["lat"].to_numpy() * _M_PER_DEG_LAT])
    tree = cKDTree(xy)
    # 자기 자신이 1순위로 잡히므로 k+1 개를 뽑는다
    dist, idx = tree.query(xy, k=min(K_NEIGHBORS + 1, len(df)),
                           distance_upper_bound=MAX_DIST_M)
    node_id = df["node_id"].to_numpy()
    rows: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for i in range(len(df)):
        rank = 0
        for d, j in zip(dist[i], idx[i]):
            if j == i or not np.isfinite(d) or j >= len(df):
                continue  # cKDTree 는 반경 밖을 inf/len(df) 로 채운다
            rank += 1
            key = (min(i, int(j)), max(i, int(j)))
            if key in seen:
                continue
            seen.add(key)
            rows.append({"src": node_id[key[0]], "dst": node_id[key[1]],
                         "dist_m": round(float(d), 1), "rank": rank,
                         "type": "spatial_knn"})
    return rows


def _group_edges(groups: dict[str, list[int]], df: pd.DataFrame, etype: str) -> list[dict]:
    """그룹(동일 건물·동일 체인) 내부를 잇는다. 큰 그룹은 클리크 대신 링."""
    lat = df["lat"].to_numpy()
    lon = df["lon"].to_numpy()
    node_id = df["node_id"].to_numpy()

    def dist_m(a: int, b: int) -> float:
        dy = (lat[a] - lat[b]) * _M_PER_DEG_LAT
        dx = (lon[a] - lon[b]) * _M_PER_DEG_LON
        return float(np.sqrt(dx * dx + dy * dy))

    rows: list[dict] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        members = sorted(members)
        if len(members) <= MAX_CLIQUE:
            pairs = combinations(members, 2)
        else:
            n = len(members)
            pairs = ((members[i], members[(i + s) % n])
                     for i in range(n) for s in range(1, RING_SPAN + 1))
        for a, b in pairs:
            if a == b:
                continue
            rows.append({"src": node_id[min(a, b)], "dst": node_id[max(a, b)],
                         "dist_m": round(dist_m(a, b), 1), "rank": 0, "type": etype})
    return rows


def _building_groups(df: pd.DataFrame) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for i, addr in enumerate(df.get("road_address", pd.Series([""] * len(df)))):
        a = str(addr or "").strip()
        if a:
            groups[a].append(i)
    return groups


def _chain_groups(df: pd.DataFrame) -> dict[str, list[int]]:
    names = df["name"].fillna("").astype(str).to_numpy()
    keys = [_chain_key(n) for n in names]
    counts: dict[str, int] = defaultdict(int)
    for k in keys:
        if len(k) >= 2:
            counts[k] += 1
    chains = {k for k, c in counts.items() if c >= MIN_CHAIN_STORES}
    # 띄어쓰기 없는 표기 보완 — 확정된 체인 토큰으로 prefix 재매칭
    long_chains = sorted((c for c in chains if len(c) >= 3), key=len, reverse=True)
    groups: dict[str, list[int]] = defaultdict(list)
    for i, (k, nm) in enumerate(zip(keys, names)):
        if k in chains:
            groups[k].append(i)
            continue
        for c in long_chains:
            if nm.startswith(c):
                groups[c].append(i)
                break
    return groups


def build_edges(nodes_path: Path = _NODES, edges_path: Path = _EDGES) -> None:
    if not nodes_path.exists():
        print(f"[edges] 노드 없음: {nodes_path} — build_gold(build_store_graph_nodes) 먼저")
        return
    df = pd.read_parquet(nodes_path)
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    bad = df["lat"].isna() | df["lon"].isna()
    if bad.any():
        print(f"[edges] 좌표 결측 {int(bad.sum())}건 제외")
        df = df[~bad]
    df = df.reset_index(drop=True)
    n = len(df)

    rows = _spatial_edges(df)
    n_knn = len(rows)
    rows += _group_edges(_building_groups(df), df, "same_building")
    n_bld = len(rows) - n_knn
    rows += _group_edges(_chain_groups(df), df, "same_chain")
    n_chain = len(rows) - n_knn - n_bld

    out = pd.DataFrame(rows)
    # 종류가 겹치는 쌍(같은 건물이면서 150m 내)은 앞선 종류를 남긴다 — spatial_knn 우선
    out = out.drop_duplicates(subset=["src", "dst"], keep="first").reset_index(drop=True)
    out.to_parquet(edges_path, index=False)

    deg = pd.concat([out["src"], out["dst"]]).value_counts()
    isolated = n - deg.index.nunique()
    print(f"[edges] {edges_path.parent.name}/{edges_path.name}: 노드 {n} → 엣지 {len(out)} (무방향)")
    print(f"  종류별(중복 제거 전): kNN {n_knn} · 동일건물 {n_bld} · 체인 {n_chain}")
    print(f"  중복 제거 후: {dict(out['type'].value_counts())}")
    knn = out[out["type"] == "spatial_knn"]
    if len(knn):
        print(f"  kNN 평균 거리 {knn['dist_m'].mean():.1f}m · 최대 {knn['dist_m'].max():.1f}m")
    print(f"  평균 차수 {2 * len(out) / n:.1f} · 고립 노드 {isolated}")
    _component_report(out, df)


def _component_report(edges: pd.DataFrame, df: pd.DataFrame) -> None:
    """연결 성분 수 — 체인 엣지가 거점 간 단절을 실제로 메웠는지 확인용."""
    idx = {nid: i for i, nid in enumerate(df["node_id"])}
    parent = list(range(len(df)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for s, d in zip(edges["src"], edges["dst"]):
        ra, rb = find(idx[s]), find(idx[d])
        if ra != rb:
            parent[ra] = rb
    comps = len({find(i) for i in range(len(df))})
    sizes = pd.Series([find(i) for i in range(len(df))]).value_counts()
    print(f"  연결 성분 {comps}개 (최대 {int(sizes.iloc[0])}노드 = 전체의 "
          f"{sizes.iloc[0] / len(df) * 100:.0f}%)")


def build_edges_platform13() -> None:
    """27거점 노드(gold/platform13) 기반 엣지."""
    p13 = GOLD / "platform13"
    build_edges(p13 / "platform_store_graph_nodes.parquet",
                p13 / "platform_store_graph_edges.parquet")


if __name__ == "__main__":
    import sys

    if "--platform13" in sys.argv:
        build_edges_platform13()
    else:
        build_edges()
