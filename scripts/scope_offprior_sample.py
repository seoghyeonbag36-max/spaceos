"""off-prior 표본 확대 스코핑 — 학습을 돌리지 않고 **검정력**만 센다.

`유닛 면적 입도`(Posting)와 달리 여기서 막힌 것은 정확도가 아니라 **표본**이다.
Platform `off-prior Top-3` 는 2026-08-26 에 게이트가 폐기되면서 이렇게 남겼다:

    n=877·discordant 88~114개는 검정력이 낮아 3~4%p 아래 차이는 이 표본으로
    원리적으로 못 잰다 — '유의하지 않다'는 '차이가 없다'가 아니라 '이 표본으로는
    못 가른다'는 뜻이고, 가르려면 off-prior 자리 자체를 늘려야 한다
    (거점 확대 또는 라벨 세분화).

이 스크립트는 그 두 축이 각각 표본을 얼마나 늘리는지를 **학습 없이** 센다.
off-prior 자리는 라벨과 분할만으로 정해지므로(SEED 고정) 600ep 을 살 필요가 없다.

    python -m scripts.scope_offprior_sample

⚠ 이 스크립트는 정확도를 재지 않는다. "표본이 커진다"는 "성능이 오른다"가 아니다 —
  커진 표본은 **가릴 수 있게** 해 줄 뿐이고, 무엇이 갈릴지는 실제로 돌려 봐야 안다.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath("."))

from ml.training.train_gnn import (  # noqa: E402
    SEED, TOP_K, _district_top3, _labels, _split, load_graph,
)

# 기존 실측 off-prior 정확도 — 표준오차 계산의 기준점(2026-08-26 세 팔의 중앙 부근).
_P_HAT = 0.376


def _masks(parts) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """_split 반환에서 train/val/test bool 마스크를 길이·dtype 으로 집는다."""
    ms = [p for p in parts
          if isinstance(p, np.ndarray) and p.dtype == bool]
    if len(ms) < 3:
        raise SystemExit(f"_split 반환을 못 읽었다: {[getattr(p, 'shape', None) for p in parts]}")
    return ms[0], ms[1], ms[2]


def measure_level(nodes, did: np.ndarray, level: str) -> dict:
    y, classes = _labels(nodes, level=level)
    tr, _va, te = _masks(_split(y, np.random.default_rng(SEED)))
    top3, major = _district_top3(y, did, tr)
    off = np.array([yt not in top3.get(d, [major]) for yt, d in zip(y, did)])
    n = int((off & te).sum())
    n_te = int(te.sum())
    se = 100 * float(np.sqrt(_P_HAT * (1 - _P_HAT) / n)) if n else float("nan")
    return {
        "level": level,
        "classes": len(classes),
        "test_nodes": n_te,
        "offprior_nodes": n,
        "offprior_share_of_test_pct": round(100 * n / n_te, 1) if n_te else 0.0,
        "se_pp": round(se, 2),
        # 대략의 가별 최소 차이 — 단일 팔 2σ. McNemar 는 쌍대라 이보다 약간 유리하다.
        "min_detectable_pp_approx": round(2 * se, 2),
    }


def main() -> None:
    nodes, _edges = load_graph()
    did = nodes["district_id"].to_numpy()
    out: dict = {
        "probe": "offprior-sample-scoping",
        "date": "2026-09-06",
        "nodes": int(len(nodes)),
        "districts": int(nodes["district_id"].nunique()),
        "top_k": TOP_K,
        "levels": {},
    }
    for lv in ("group", "category2"):
        out["levels"][lv] = measure_level(nodes, did, lv)

    g = out["levels"]["group"]
    c = out["levels"]["category2"]
    out["label_axis"] = {
        "sample_multiplier": round(c["offprior_nodes"] / g["offprior_nodes"], 2),
        "min_detectable_pp": [g["min_detectable_pp_approx"], c["min_detectable_pp_approx"]],
        "already_implemented": "--label-level category2 (train_gnn.py)",
        "caveat": "라벨 체계가 바뀌므로 train() 이 산출물 저장을 강제로 끈다 — 서빙 교체가 아니라 계측 도구다",
    }
    per_hub = g["offprior_nodes"] / out["districts"]
    out["hub_axis"] = {
        "offprior_per_hub": round(per_hub, 1),
        # 표준오차는 1/sqrt(n) — 절반으로 줄이려면 표본 4배, 즉 거점도 대략 4배
        "hubs_for_half_se": int(round(out["districts"] * 4)),
        "paused_hubs_would_add": round(per_hub * 20),
        "caveat": "고양·파주 20거점은 서빙 보류 — 이 스코핑은 수만 세고 서빙 결정을 하지 않는다",
    }
    os.makedirs("reports", exist_ok=True)
    dest = "reports/offprior_sample_scoping_2026-09-06.json"
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\n저장: {dest}")


if __name__ == "__main__":
    main()
