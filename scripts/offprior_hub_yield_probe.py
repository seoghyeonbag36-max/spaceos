"""거점 확대가 off-prior 표본을 얼마나 늘리는지 — **수집을 사기 전에** 값싸게 잰다.

## 배경

§0-N(2026-08-27)이 라벨 세분화 쪽 절반을 닫았다: category2 로 표본을 4.32배(877→3,785)
늘려 검정력을 확보했더니, 레버 간 델타가 오히려 0.03~0.26pp 로 줄어 "표본이 작아서 못
갈랐다"가 아니라 "가를 차이가 없다"가 확인됐다. 남은 절반이 **거점 확대**다.

거점 확대는 라벨 세분화와 달리 **신규 수집**이 든다 — 그래서 사기 전에 "몇 개를 어떤
종류로 늘려야 표본이 의미 있게 커지는가"를 먼저 알아야 한다. 이 스크립트가 그걸 잰다.

## 무엇을 재는가

off-prior 자리는 "test 노드의 정답이 그 거점 train 라벨 top-3 밖"인 자리다
(`train_gnn._district_top3`). 즉 **거점 안 업종 구성이 다양할수록** 많이 나온다 —
음식점·카페·병원만 있는 거점은 top-3 가 전부를 덮어 off-prior 가 0 에 가깝고,
꼬리 업종이 두꺼운 거점일수록 많이 낸다.

그래서 "노드를 늘리면 off-prior 도 비례해 는다"는 순진한 가정이 틀릴 수 있다.
거점별 수율(off-prior/노드)을 실측해 **분산이 얼마나 큰지**, 그리고 수율이 높은
거점이 어떤 성격인지 보면, 신규 거점 선정 기준과 필요 개수가 나온다.

## 왜 학습이 필요 없는가

§0-N 프로브와 같은 이유 — off-prior 마스크는 라벨·분할만으로 정해지고 모델 예측과
무관하다. `_split`/`_district_top3` 를 학습 코드에서 그대로 import 해 쓴다.

실행: python -u -m scripts.offprior_hub_yield_probe
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

from ml.training.train_gnn import SEED, TOP_K, _district_top3, _labels, _split, load_graph

_OUT = Path(__file__).resolve().parents[1] / "reports" / "offprior_hub_yield_probe_2026-08-27.json"


def main() -> None:
    nodes, _edges = load_graph()
    y, classes = _labels(nodes, level="group")
    did = nodes["district_id"].fillna("").astype(str).to_numpy()
    rng = np.random.default_rng(SEED)
    train, _val, test = _split(y, rng)
    top3, major = _district_top3(y, did, train)

    off = np.array([yt not in top3.get(d, [major])
                    for yt, d in zip(y, did)]) & test

    rows = []
    for d in sorted(set(did)):
        m = did == d
        n_nodes = int(m.sum())
        n_test = int((m & test).sum())
        n_off = int((m & off).sum())
        # 거점 안 업종 다양성 — top-3 가 덮는 비율(낮을수록 꼬리가 두껍다)
        cnt = Counter(y[m & train])
        tot = sum(cnt.values())
        top3_share = (sum(n for _c, n in cnt.most_common(TOP_K)) / tot) if tot else 0.0
        rows.append({
            "district_id": d, "nodes": n_nodes, "test": n_test, "off_prior": n_off,
            "off_per_node": round(n_off / n_nodes, 4) if n_nodes else 0.0,
            "off_per_test": round(n_off / n_test, 4) if n_test else 0.0,
            "train_top3_share": round(top3_share, 4),
            "n_classes_present": len(cnt),
        })

    rows.sort(key=lambda r: -r["off_per_node"])
    tot_nodes = sum(r["nodes"] for r in rows)
    tot_off = sum(r["off_prior"] for r in rows)
    mean_yield = tot_off / tot_nodes

    print(f"[probe] 거점 {len(rows)} · 노드 {tot_nodes} · off-prior {tot_off} "
          f"· 전체 수율 {mean_yield:.4f} (off-prior/노드)")
    print(f"[probe] 수율 상위 8 ─────────────────────────────────────────")
    for r in rows[:8]:
        print(f"  {r['district_id']:16s} 노드{r['nodes']:5d} off{r['off_prior']:4d} "
              f"수율 {r['off_per_node']:.4f} · top3점유 {r['train_top3_share']:.1%} "
              f"· 업종{r['n_classes_present']}")
    print(f"[probe] 수율 하위 8 ─────────────────────────────────────────")
    for r in rows[-8:]:
        print(f"  {r['district_id']:16s} 노드{r['nodes']:5d} off{r['off_prior']:4d} "
              f"수율 {r['off_per_node']:.4f} · top3점유 {r['train_top3_share']:.1%} "
              f"· 업종{r['n_classes_present']}")

    ys = np.array([r["off_per_node"] for r in rows])
    ns = np.array([r["nodes"] for r in rows])
    print(f"[probe] 수율 분포: 중앙 {np.median(ys):.4f} · 평균 {ys.mean():.4f} "
          f"· 최소 {ys.min():.4f} · 최대 {ys.max():.4f} · 변동계수 {ys.std()/ys.mean():.2f}")
    print(f"[probe] 거점 크기 분포: 중앙 {np.median(ns):.0f} 노드 · 최소 {ns.min()} · 최대 {ns.max()}")

    # 필요 거점 수 — off-prior 를 2배로 늘리려면 몇 개가 필요한가.
    # ① 평균 수율·중앙 크기의 거점을 더한다고 볼 때  ② 상위 4분위 수율 거점만 고를 때
    med_nodes = float(np.median(ns))
    q75 = float(np.percentile(ys, 75))
    need_avg = tot_off / (med_nodes * mean_yield)
    need_q75 = tot_off / (med_nodes * q75)
    print(f"[probe] off-prior 2배(+{tot_off})에 필요한 신규 거점 수 —")
    print(f"          평균 수율 거점이면 {need_avg:.0f}곳 · 상위4분위 수율 거점이면 {need_q75:.0f}곳")

    out = {
        "total": {"hubs": len(rows), "nodes": tot_nodes, "off_prior": tot_off,
                  "yield_off_per_node": round(mean_yield, 4),
                  "median_hub_nodes": med_nodes,
                  "yield_median": round(float(np.median(ys)), 4),
                  "yield_q75": round(q75, 4),
                  "yield_cv": round(float(ys.std() / ys.mean()), 3)},
        "need_hubs_to_double_offprior": {"at_mean_yield": round(need_avg, 1),
                                         "at_q75_yield": round(need_q75, 1)},
        "hubs": rows,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[probe] 저장: {_OUT}")


if __name__ == "__main__":
    main()
