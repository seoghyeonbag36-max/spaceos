"""IndustryGNN 학습 골격 — E단계는 그래프 데이터 품질 확인까지만 (학습 강행 금지).

소스:
  gold/garosugil/platform_store_graph_nodes.parquet  (kakao 현존 점포)
  gold/garosugil/platform_store_graph_edges.parquet  (공간 kNN — build_store_graph_edges)

실행: python -m ml.training.train_gnn → 그래프 요약·품질 리포트 출력.
학습 TODO (데이터 요건 충족 후):
  - 태스크: 노드 업종 대분류 분류(마스킹) — "이 자리에 어떤 업종이 맞는가"의 프록시
  - 엣지 확장: 고객 공유·리뷰 유사도 (현재 공간 근접뿐 — 시너지/잠식 구분 불가)
  - 라벨 희소 클래스 병합 기준: 최소 10노드
  - torch_geometric 설치 후 IndustryGNN(ml/models/gnn/industry_gnn.py) 연결
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

_GOLD = _REPO / "data" / "gold"

MIN_CLASS_NODES = 10  # 이보다 작은 업종 대분류는 '기타'로 병합 예정


def load_graph() -> tuple[pd.DataFrame, pd.DataFrame]:
    """platform13(27거점) 그래프 우선, 없으면 garosugil 단일 거점 폴백."""
    for slug in ("platform13", "garosugil"):
        nodes = _GOLD / slug / "platform_store_graph_nodes.parquet"
        edges = _GOLD / slug / "platform_store_graph_edges.parquet"
        if nodes.exists() and edges.exists():
            print(f"[gnn] 그래프 소스: gold/{slug}")
            return pd.read_parquet(nodes), pd.read_parquet(edges)
    raise FileNotFoundError(
        "그래프 gold 없음 — build_gold + build_store_graph_edges 먼저 실행")


def quality_report() -> dict:
    """학습 가능성 판단용 그래프 품질 요약. train() 전에 반드시 통과 확인."""
    nodes, edges = load_graph()
    n = len(nodes)

    # 라벨 후보: 카카오 category 1~2단계 ("음식점 > 양식 > …" → "음식점 > 양식")
    label = nodes["category"].fillna("").map(
        lambda c: " > ".join(str(c).split(" > ")[:2]) or "미분류")
    counts = label.value_counts()
    small = counts[counts < MIN_CLASS_NODES]

    idx = {nid: i for i, nid in enumerate(nodes["node_id"])}
    ei = np.array([[idx[s], idx[d]] for s, d in zip(edges["src"], edges["dst"])])
    deg = np.bincount(ei.ravel(), minlength=n)

    rep = {
        "nodes": n,
        "edges_undirected": len(edges),
        "classes": int(counts.size),
        "classes_small": int(small.size),
        "mean_degree": round(float(deg.mean()), 2),
        "isolated_nodes": int((deg == 0).sum()),
        "mean_dist_m": round(float(edges["dist_m"].mean()), 1),
    }
    print("[gnn·quality]", rep)
    print(f"  업종 대분류 상위: {dict(counts.head(8))}")
    if small.size:
        print(f"  [주의] {MIN_CLASS_NODES}노드 미만 희소 클래스 {small.size}종 → '기타' 병합 필요")
    if rep["isolated_nodes"]:
        print(f"  [주의] 고립 노드 {rep['isolated_nodes']}개 — 반경/k 재검토")
    return rep


def train() -> None:
    """TODO(GNN): 학습 미구현 — E단계 규칙상 데이터 품질 확인까지만.

    구현 시: quality_report 통과 → 희소 클래스 병합 → 피처(카테고리 원핫+좌표) →
    IndustryGNN 노드 분류(홀드아웃 마스크) → MLflow(industry_gnn 실험) 기록.
    """
    raise NotImplementedError("GNN 학습은 엣지 다양화(고객 공유·리뷰 유사도) 후 진행")


if __name__ == "__main__":
    quality_report()
