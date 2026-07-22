"""[Platform·GNN] 점포 그래프 엣지 — 공간 kNN (E단계 골격).

소스: gold/garosugil/platform_store_graph_nodes.parquet (kakao 현존 점포)
산출: gold/garosugil/platform_store_graph_edges.parquet — 신규 파일 (기존 gold 덮어쓰기 아님)
  src, dst   node_id 쌍 (무방향 — 한 쌍당 1행, GNN 입력 시 양방향 전개)
  dist_m     두 점포 간 거리(m, 등장방형 근사)
  rank       src 기준 최근접 순위(1=최근접)

규칙: k=5 최근접 + 최대 반경 150m(가로수길 블록 스케일) — 반경 초과 이웃은 버린다.
TODO(GNN): 고객 공유·리뷰 유사도 엣지 추가, LOCALDATA 인허가 노드 통합(entity resolution).

실행: python -m data.pipelines.build_store_graph_edges
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pathlib import Path

from data.collectors.common import GOLD
from data.config.garosugil import SLUG

_NODES = GOLD / SLUG / "platform_store_graph_nodes.parquet"
_EDGES = GOLD / SLUG / "platform_store_graph_edges.parquet"

K_NEIGHBORS = 5
MAX_DIST_M = 150.0

# 서울 위도(37.5°) 근방 등장방형 근사 — services/districts.py _dist_m 과 동일 계수
_M_PER_DEG_LAT = 111000.0
_M_PER_DEG_LON = 88300.0


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

    y = df["lat"].to_numpy() * _M_PER_DEG_LAT
    x = df["lon"].to_numpy() * _M_PER_DEG_LON
    # n≈200 브루트포스면 충분 (n² 거리 행렬) — 확장 시 scipy cKDTree 로 교체
    dist = np.sqrt((y[:, None] - y[None, :]) ** 2 + (x[:, None] - x[None, :]) ** 2)
    np.fill_diagonal(dist, np.inf)

    rows: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for i in range(n):
        order = np.argsort(dist[i])[:K_NEIGHBORS]
        for rank, j in enumerate(order, start=1):
            d = float(dist[i, j])
            if d > MAX_DIST_M:
                break  # argsort 순이므로 이후는 전부 반경 초과
            key = (min(i, int(j)), max(i, int(j)))
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "src": df["node_id"].iloc[key[0]],
                "dst": df["node_id"].iloc[key[1]],
                "dist_m": round(d, 1),
                "rank": rank,
            })

    out = pd.DataFrame(rows)
    out.to_parquet(edges_path, index=False)

    # 품질 리포트 — 고립 노드(엣지 0개)가 많으면 반경/k 재검토
    deg = pd.concat([out["src"], out["dst"]]).value_counts()
    isolated = n - deg.index.nunique()
    print(f"[edges] {edges_path.parent.name}/{edges_path.name}: 노드 {n} → 엣지 {len(out)} (무방향)")
    print(f"  평균 거리 {out['dist_m'].mean():.1f}m · 최대 {out['dist_m'].max():.1f}m"
          f" · 평균 차수 {2 * len(out) / n:.1f} · 고립 노드 {isolated}")


def build_edges_platform13() -> None:
    """27거점 노드(gold/platform13) 기반 엣지 — 150m 캡이 사실상 거점 내 연결만 남긴다."""
    p13 = GOLD / "platform13"
    build_edges(p13 / "platform_store_graph_nodes.parquet",
                p13 / "platform_store_graph_edges.parquet")


if __name__ == "__main__":
    import sys

    if "--platform13" in sys.argv:
        build_edges_platform13()
    else:
        build_edges()
