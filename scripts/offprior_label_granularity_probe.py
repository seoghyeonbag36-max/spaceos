"""off-prior 표본(현재 877자리)을 라벨 세분화로 늘리면 McNemar 검정력이 얼마나
좋아지는지 — **GNN 을 학습하지 않고** 값싼 프로브로 먼저 잰다.

## 배경

docs/feature-platform.md §0-Q 결정: off-prior Top-3 ≥50% 게이트를 폐기하고 관측
전용으로 강등했다. 독립 레버 4종(이웃 라벨·조기종료·행정동·집계구)이 전부 37%대에
몰렸는데, n=877(test 877자리)의 discordant 88~114개로는 McNemar 검정력이 낮아
3~4%p 아래 차이를 원리적으로 못 가른다(jipgyegu vs control +2.05%p, p=0.111 —
유의하지 않다). "차이가 없다"가 아니라 "이 표본으로는 못 가른다"는 뜻이라, 표본을
늘려야 다음 레버(집계구 등)의 판정을 낼 수 있다.

늘리는 방법은 둘: 거점 확대(자료 신규 수집) 또는 **라벨 세분화**(같은 데이터에서
off-prior 정의상 문턱을 낮춘다). 이 스크립트는 후자를 택한 뒤의 **첫 걸음** —
실제로 얼마나 늘어나는지를 600ep 학습 없이 재는 값싼 프로브다.

## 왜 학습이 필요 없는가

off-prior 여부는 "test 노드의 정답이 그 거점 train 라벨의 top-3 안에 있는가"로
정의된다(`train_gnn._district_top3`/`_offprior_top3`) — **모델의 예측과 무관**하다.
즉 off-prior 표본의 **크기**는 라벨 분포·거점 분할만으로 정해지고, GNN 이 그 안에서
얼마나 맞히는지(37%대)는 별개 질문이다. 크기만 알고 싶으면 학습을 돌릴 필요가 없다.

## 주의 — 이 프로브가 답하지 않는 것

category2 라벨은 이미 실측돼 있다(docs/feature-platform.md §0-A): Top-3 58.4%로
서빙 KPI(70%)에 못 미친다. 그래서 category2 를 **서빙 라벨로 바꾸자는 게 아니다** —
여기서는 순전히 "레버 비교용 진단 지표"로만 쓴다(off-prior 게이트 자체가 이미
관측 전용으로 강등됐으므로 서빙에는 영향 없다). 이 프로브는 그 진단 표본이 통계적으로
쓸 만큼 커지는지만 잰다.

실행: python scripts/offprior_label_granularity_probe.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ml.training.train_gnn import SEED, _district_top3, _labels, _split, load_graph

_OUT = Path(__file__).resolve().parents[1] / "reports" / "offprior_granularity_probe_2026-08-27.json"


def _se(p: float, n: int) -> float:
    return float(np.sqrt(p * (1 - p) / n)) if n else float("nan")


def probe(level: str, nodes, rng: np.random.Generator) -> dict:
    y, classes = _labels(nodes, level=level)
    did = nodes["district_id"].fillna("").astype(str).to_numpy()
    train, val, test = _split(y, rng)
    top3, major = _district_top3(y, did, train)

    # off-prior = test 자리 중 정답이 거점 top-3 밖인 것 (_offprior_top3 와 같은 정의,
    # 모델 로짓이 없어도 마스크는 동일하게 구할 수 있다)
    off_mask = np.array([
        yt not in top3.get(d, [major]) for yt, d in zip(y[test], did[test])])
    n_test = int(test.sum())
    n_off = int(off_mask.sum())
    frac = n_off / n_test if n_test else 0.0

    return {
        "level": level, "n_classes": len(classes),
        "n_test": n_test, "n_off_prior": n_off, "off_prior_frac": round(frac, 4),
        "se_at_p37": round(_se(0.37, n_off) * 100, 2),
    }


def main() -> None:
    nodes, _edges = load_graph()
    rng = np.random.default_rng(SEED)
    group = probe("group", nodes, rng)
    rng = np.random.default_rng(SEED)  # 두 라벨 입도가 같은 rng 상태에서 갈리도록 리셋
    cat2 = probe("category2", nodes, rng)

    for r in (group, cat2):
        print(f"[probe] {r['level']:10s} 클래스 {r['n_classes']:3d} · "
              f"test {r['n_test']:5d} · off-prior {r['n_off_prior']:5d} "
              f"({r['off_prior_frac']:.1%}) · SE(p≈37%) ≈ ±{r['se_at_p37']}pp")

    gain = cat2["n_off_prior"] / group["n_off_prior"] if group["n_off_prior"] else float("nan")
    print(f"[probe] off-prior 표본 배율 group→category2: {gain:.2f}x")
    print(f"[probe] 대조: 실서빙 group off-prior n(877) 재현 여부는 위 group 행으로 확인할 것"
          f" — SEED·TOP_K·분할 로직이 같으면 카운트가 소수점(정수) 단위까지 같아야 한다")

    out = {"group": group, "category2": cat2, "gain_x": round(gain, 2)}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[probe] 저장: {_OUT}")


if __name__ == "__main__":
    main()
