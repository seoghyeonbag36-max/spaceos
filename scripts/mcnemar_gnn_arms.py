"""GNN off-prior Top-3 두 팔을 McNemar 쌍대검정으로 비교한다.

## 왜 필요한가

2026-08-26 집계구 배선 런이 off-prior Top-3 를 35.92%→37.97%(+2.05%p)로 올렸다.
단일 팔 표준오차(≈1.63%p)로는 판정이 안 된다 — 두 값은 **같은 test 877자리** 위에서
난 것이라 독립 표본 검정(z-test 근사)이 아니라 **쌍대(paired)** 검정을 써야 한다.
McNemar 검정은 "두 모델이 갈리는 자리"만 보고, 둘 다 맞거나 둘 다 틀린 자리는
정보가 없다고 버린다 — 그게 정확히 이 비교에 맞는 통계량이다.

## 전제 — 깨지면 비교 자체가 무의미하다

두 덤프가 **같은 노드 집합**(같은 test 분할)이어야 한다. train_gnn.SEED=42 로 고정된
rng 가 라벨(y)에만 의존해 분할하므로, 그래프·라벨이 같으면 어느 피처 블록을 켜든
분할은 같다 — 이 스크립트가 그것도 확인한다(node_id 집합 불일치 시 에러).

실행: python scripts/mcnemar_gnn_arms.py <arm_a.json> <arm_b.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _load(p: str) -> dict[str, dict]:
    doc = json.loads(Path(p).read_text(encoding="utf-8"))
    return {r["node_id"]: r for r in doc["rows"]}


def mcnemar(a: dict[str, dict], b: dict[str, dict]) -> dict:
    ids = set(a) & set(b)
    if ids != set(a) or ids != set(b):
        raise ValueError(
            f"두 덤프의 node_id 집합이 다르다 — 같은 test 분할이 아니다 "
            f"(a only: {len(set(a) - ids)}, b only: {len(set(b) - ids)}). "
            f"같은 SEED·같은 라벨 입도로 돌렸는지 확인할 것.")
    n01 = n10 = n00 = n11 = 0
    for k in ids:
        ha, hb = a[k]["hit_top3"], b[k]["hit_top3"]
        if ha and hb:
            n11 += 1
        elif ha and not hb:
            n10 += 1
        elif not ha and hb:
            n01 += 1
        else:
            n00 += 1
    # 연속성 보정 McNemar 카이제곱(1자유도). b01+b10 이 작을 때는(<25) 이항검정이
    # 더 정확하지만, 여기서는 표본 877 이라 카이제곱 근사가 무난하다.
    disc = n01 + n10
    chi2 = ((abs(n01 - n10) - 1) ** 2 / disc) if disc else 0.0
    # 카이제곱(1자유도) → p값. scipy 없이 표준정규 근사(sqrt(chi2) ~ |Z|)로 충분하다.
    import math
    z = math.sqrt(chi2)
    # erf 기반 양측 p값
    p = math.erfc(z / math.sqrt(2))
    return {
        "n": len(ids), "both_hit": n11, "both_miss": n00,
        "a_only_hit": n10, "b_only_hit": n01,
        "a_rate": round((n11 + n10) / len(ids), 4),
        "b_rate": round((n11 + n01) / len(ids), 4),
        "delta_pp": round(((n11 + n01) - (n11 + n10)) / len(ids) * 100, 2),
        "discordant": disc, "chi2": round(chi2, 3), "p_value": round(p, 4),
        "significant_at_0.05": p < 0.05,
    }


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    a, b = _load(sys.argv[1]), _load(sys.argv[2])
    r = mcnemar(a, b)
    print(f"[mcnemar] n={r['n']} · both_hit={r['both_hit']} · both_miss={r['both_miss']} · "
          f"a_only={r['a_only_hit']} · b_only={r['b_only_hit']}")
    print(f"[mcnemar] a_rate={r['a_rate']:.2%} · b_rate={r['b_rate']:.2%} · "
          f"Δ={r['delta_pp']:+.2f}pp")
    print(f"[mcnemar] discordant={r['discordant']} · chi2={r['chi2']} · "
          f"p={r['p_value']} · {'유의함(p<0.05)' if r['significant_at_0.05'] else '유의하지 않음'}")
    print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
