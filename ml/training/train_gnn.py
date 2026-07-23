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

from ml.models.gnn.industry_gnn import IndustryGNN  # noqa: E402

_GOLD = _REPO / "data" / "gold"
_ARTIFACT = _REPO / "ml" / "artifacts" / "industry_gnn.pt"
_RECOMMEND_JSON = _GOLD / "platform_industry_recommend.json"
_MLRUNS = _REPO / "ml" / "mlruns"

MIN_CLASS_NODES = 10   # 이보다 작은 업종 대분류는 '기타'로 병합
TOP_K = 3              # 추천 Top-K (KPI: Top-3 70%+)
SEED = 42

_M_PER_DEG_LAT = 111000.0
_M_PER_DEG_LON = 88300.0


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


def _labels(nodes: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """카카오 category 1~2단계를 라벨로 ("음식점 > 양식 > …" → "음식점 > 양식")."""
    raw = nodes["category"].fillna("").map(
        lambda c: " > ".join(str(c).split(" > ")[:2]) or "미분류")
    counts = raw.value_counts()
    small = set(counts[counts < MIN_CLASS_NODES].index)
    merged = raw.map(lambda c: "기타" if c in small else c)
    classes = sorted(merged.unique())
    idx = {c: i for i, c in enumerate(classes)}
    return merged.map(idx).to_numpy(), classes


def _features(nodes: pd.DataFrame, edges: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
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


def _baselines(y: np.ndarray, did: np.ndarray, train: np.ndarray,
               test: np.ndarray, n_cls: int) -> dict[str, float]:
    """모델 없이 얻는 점수 — '20% 향상' 을 재는 기준선."""
    # ① 전역 최빈 클래스
    major = Counter(y[train]).most_common(1)[0][0]
    acc_major = float((y[test] == major).mean())

    # ② 거점별 최빈 클래스(거점 사전분포) — 실질적인 '모델 없음' 답안
    per: dict[str, int] = {}
    for d in np.unique(did):
        m = train & (did == d)
        if m.any():
            per[d] = Counter(y[m]).most_common(1)[0][0]
    pred_prior = np.array([per.get(d, major) for d in did[test]])
    acc_prior = float((pred_prior == y[test]).mean())

    # ③ 거점 사전분포 Top-3
    top3: dict[str, list[int]] = {}
    for d in np.unique(did):
        m = train & (did == d)
        top3[d] = [c for c, _ in Counter(y[m]).most_common(TOP_K)] if m.any() else [major]
    acc_prior_top3 = float(np.mean([
        yt in top3.get(d, [major]) for yt, d in zip(y[test], did[test])]))

    return {"baseline_major_top1": round(acc_major, 4),
            "baseline_district_prior_top1": round(acc_prior, 4),
            "baseline_district_prior_top3": round(acc_prior_top3, 4)}


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
          patience: int = 50, save: bool = True) -> dict:
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)

    nodes, edges = load_graph()
    nodes = nodes.reset_index(drop=True)
    y_np, classes = _labels(nodes)
    x_np, feat_names = _features(nodes, edges)
    ei = _edge_index(nodes, edges, edge_types)
    did = nodes["district_id"].fillna("").astype(str).to_numpy()

    x = torch.tensor(x_np)
    y = torch.tensor(y_np, dtype=torch.long)
    tr, va, te = _split(y_np, rng)
    m_tr, m_va, m_te = (torch.tensor(m) for m in (tr, va, te))

    model = IndustryGNN(x.shape[1], len(classes), hidden=hidden)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    best_val, best_state, bad = -1.0, None, 0
    for ep in range(1, epochs + 1):
        model.train()
        opt.zero_grad()
        out = model(x, ei)
        loss = F.nll_loss(out[m_tr], y[m_tr])
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
        if ep % 50 == 0:
            print(f"  ep{ep:4d} loss {float(loss.detach()):.4f} · val top1 {v:.4f}")

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
    }
    base = metrics["baseline_district_prior_top1"]
    metrics["lift_vs_district_prior_pct"] = (
        round((metrics["test_top1"] - base) / base * 100, 1) if base else None)
    metrics.update({"nodes": len(nodes), "edges_used": int(ei.shape[1] // 2),
                    "classes": len(classes),
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
    a = ap.parse_args()
    if a.report:
        quality_report()
    else:
        types = set(a.edge_types.split(",")) if a.edge_types else None
        train(edge_types=types, epochs=a.epochs, hidden=a.hidden, save=not a.no_save)
