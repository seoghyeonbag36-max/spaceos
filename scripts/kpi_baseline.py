"""KPI 실력 검정 — 모델이 **무정보 베이스라인**을 실제로 이기는지 잰다.

## 왜 필요한가 (2026-09-15 실측으로 드러난 구멍)

KPI① 이 "AI 정확도 70%+" 한 줄이라 **임계값만 넘으면 달성**으로 찍혀 왔다. 그런데
임계값 자체가 모델을 보증하지 못한다 — 같은 홀드아웃에서 입력을 **하나도 안 보는**
규칙이 그 임계값을 이미 넘는다:

| KPI | 모델 | 무정보 베이스라인 | 판정 |
|---|---|---|---|
| LSTM 방향정확도 ≥70% | 70.8% (46/65) | **항상 하락 78.5% (51/65)** | 베이스라인이 **7.7%p 더 높다** |
| GNN 업종추천 Top-3 ≥70% | 91.7% | **거점 사전분포 89.4%** | 베이스라인이 임계값을 19.4%p 초과 |

즉 두 게이트 모두 **0 짜리 모델도 통과**한다. 임계값을 넘었다는 사실에는 정보가 없고,
정보는 **베이스라인과의 차이**에만 있다. 이 모듈은 그 차이를 잰다.

## 무엇을 재나 — 세 겹

1. **실력(skill)** — 모델 − 베이스라인. 0 이하면 모델이 기여한 것이 없다.
2. **불확실성** — Wilson 95% 신뢰구간. 점추정으로 달성/미달을 가르면 표본 65개에서
   ±11%p 를 무시하게 된다(70.8% 의 구간은 [58.8%, 80.4%] 라 목표 70% 를 품는다).
3. **쌍대 검정** — 같은 홀드아웃 위의 비교라 독립표본 검정이 아니라 McNemar 정확검정을
   쓴다. "유의하지 않다"는 "차이가 없다"가 아니라 "이 표본으로는 못 가른다"는 뜻이다.

## 베이스라인을 어떻게 고르나

- **LSTM 방향** — `{항상 상승, 항상 하락}` 중 **홀드아웃에서 더 잘 맞는 쪽**을 쓴다.
  사후적 선택이라 모델에 불리하지만, 그래서 **모델이 이기면 진짜로 이긴 것**이다.
  방어선으로 쓰기에 이쪽이 옳다.
- **LSTM 오차** — 지속성(persistence, 예측=직전 분기값). 시계열에서 표준 대조군이다.
- **GNN** — 거점 사전분포(`baseline_district_prior_*`). 학습이 이미 남겨 둔 값을 읽는다.

읽기만 한다. 네트워크·파일 쓰기 없음. 표준 라이브러리만 쓴다(numpy·torch 불필요).

실행: python scripts/kpi_baseline.py          사람용
      python scripts/kpi_baseline.py --json   기계 판독용
반환 코드: 0 = 전부 베이스라인 초과 · 1 = 하나라도 미달(CI 에서 잡으라고 비-0)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "data" / "gold"
FORECAST = GOLD / "platform_vacancy_forecast.json"
RECOMMEND = GOLD / "platform_industry_recommend.json"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ─────────────────────────── 통계 ───────────────────────────

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """이항 비율의 Wilson 신뢰구간. n 이 작을 때 정규근사보다 정직하다."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    den = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar_exact(b: int, c: int) -> float:
    """McNemar 정확검정(양측) p값. b·c 는 불일치 칸.

    카이제곱 근사는 b+c 가 작으면 못 쓴다(여기 실측이 21 이다). 정확검정은
    b+c 를 시행수, 0.5 를 성공확률로 보는 이항검정이다.
    """
    n = b + c
    if n == 0:
        return 1.0
    lo = min(b, c)
    tail = sum(math.comb(n, i) for i in range(lo + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def _sgn(x: float) -> int:
    return (x > 0) - (x < 0)


# ─────────────────────────── LSTM ───────────────────────────

def lstm_skill(forecast: dict) -> dict:
    """공실 예측 — 방향정확도·오차 두 축을 각각 베이스라인에 댄다.

    방향은 베이스라인을 못 이기고(실력 음수), 오차는 이긴다. **두 축이 갈리므로
    하나만 인용하면 어느 쪽이든 거짓이 된다** — 그래서 둘 다 돌려준다.
    """
    hold = forecast.get("holdout") or {}
    rows = [(k, v.get("pred"), v.get("actual"), v.get("prev")) for k, v in hold.items()]
    rows = [r for r in rows if None not in r[1:]]
    n = len(rows)
    if n == 0:
        return {"available": False, "reason": "holdout 표가 비어 있다"}

    hits = sum(1 for _, p, a, pr in rows if _sgn(p - pr) == _sgn(a - pr))
    up = sum(1 for _, _, a, pr in rows if a - pr > 0)
    down = sum(1 for _, _, a, pr in rows if a - pr < 0)
    # 사후적 다수 방향 — 모델에 불리한(즉 방어에 적합한) 베이스라인
    base_hits, base_label = (down, "항상 하락") if down >= up else (up, "항상 상승")

    # 쌍대 비교: 모델만 맞은 칸 b · 베이스라인만 맞은 칸 c
    b = c = 0
    base_down = base_hits == down
    for _, p, a, pr in rows:
        m_hit = _sgn(p - pr) == _sgn(a - pr)
        base_hit = (a - pr < 0) if base_down else (a - pr > 0)
        b += int(m_hit and not base_hit)
        c += int(base_hit and not m_hit)

    mae_m = sum(abs(p - a) for _, p, a, _ in rows) / n
    rmse_m = math.sqrt(sum((p - a) ** 2 for _, p, a, _ in rows) / n)
    mae_p = sum(abs(pr - a) for _, _, a, pr in rows) / n        # 지속성
    rmse_p = math.sqrt(sum((pr - a) ** 2 for _, _, a, pr in rows) / n)

    acc, base_acc = hits / n, base_hits / n
    return {
        "available": True,
        "n": n,
        "direction": {
            "model_hits": hits, "model_acc": acc, "model_ci95": list(wilson(hits, n)),
            "baseline_label": base_label, "baseline_hits": base_hits,
            "baseline_acc": base_acc, "baseline_ci95": list(wilson(base_hits, n)),
            "skill_pp": (acc - base_acc) * 100.0,
            "mcnemar": {"b_model_only": b, "c_baseline_only": c,
                        "p_two_sided": mcnemar_exact(b, c)},
            "actual_up": up, "actual_down": down,
            "beats_baseline": acc > base_acc,
        },
        "error": {
            "model_mae": mae_m, "model_rmse": rmse_m,
            "persistence_mae": mae_p, "persistence_rmse": rmse_p,
            # 기술점수(skill score) — 1 − 모델/베이스라인. 양수면 베이스라인보다 낫다.
            "mae_skill": (1.0 - mae_m / mae_p) if mae_p else 0.0,
            "rmse_skill": (1.0 - rmse_m / rmse_p) if rmse_p else 0.0,
            "beats_persistence": mae_m < mae_p,
        },
    }


# ─────────────────────────── GNN ───────────────────────────

def gnn_skill(recommend: dict) -> dict:
    """업종추천 — 학습이 남긴 거점 사전분포 기준선에 댄다.

    off-prior 는 사전분포가 **원리적으로 못 맞히는** 자리만 모은 표본이라 여기서
    실력이 가장 정직하게 드러난다. 값은 있는 그대로 싣고 판정에는 쓰지 않는다
    (게이트는 2026-08-26 에 관측 전용으로 강등됐다).
    """
    m = (recommend or {}).get("metrics") or {}
    top3, top1 = m.get("test_top3"), m.get("test_top1")
    b3 = m.get("baseline_district_prior_top3")
    b1 = m.get("baseline_district_prior_top1")
    if top3 is None or b3 is None:
        return {"available": False, "reason": "metrics 에 test_top3/baseline 이 없다"}
    out = {
        "available": True,
        "top3": top3, "baseline_top3": b3, "skill_pp_top3": (top3 - b3) * 100.0,
        "beats_baseline": top3 > b3,
        "offprior_top3": m.get("test_offprior_top3"),
        "offprior_nodes": m.get("offprior_nodes"),
        "test_nodes": m.get("nodes"),
    }
    if top1 is not None and b1 is not None:
        out.update({"top1": top1, "baseline_top1": b1,
                    "skill_pp_top1": (top1 - b1) * 100.0})
    return out


# ─────────────────────────── 종합 ───────────────────────────

def check(forecast_path: Path = FORECAST, recommend_path: Path = RECOMMEND) -> dict:
    def _load(p: Path) -> dict | None:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    fc, rec = _load(forecast_path), _load(recommend_path)
    lstm = lstm_skill(fc) if fc else {"available": False, "reason": f"{forecast_path.name} 없음"}
    gnn = gnn_skill(rec) if rec else {"available": False, "reason": f"{recommend_path.name} 없음"}

    failures: list[str] = []
    if lstm.get("available"):
        d = lstm["direction"]
        if not d["beats_baseline"]:
            failures.append(
                f"LSTM 방향정확도 {d['model_acc']:.1%} < 베이스라인({d['baseline_label']}) "
                f"{d['baseline_acc']:.1%} — 실력 {d['skill_pp']:+.1f}%p")
        if not lstm["error"]["beats_persistence"]:
            failures.append("LSTM MAE 가 지속성 베이스라인보다 나쁘다")
    if gnn.get("available") and not gnn["beats_baseline"]:
        failures.append(
            f"GNN Top-3 {gnn['top3']:.1%} ≤ 거점 사전분포 {gnn['baseline_top3']:.1%}")

    return {"lstm": lstm, "gnn": gnn, "failures": failures, "ok": not failures}


def _fmt(res: dict) -> str:
    out: list[str] = []
    out.append("KPI 실력 검정 — 모델 vs 무정보 베이스라인")
    out.append("=" * 78)

    lstm = res["lstm"]
    out.append("\n[LSTM] 공실 예측")
    if not lstm.get("available"):
        out.append(f"   재지 못했다 — {lstm.get('reason')}")
    else:
        d, e = lstm["direction"], lstm["error"]
        lo, hi = d["model_ci95"]
        mark = "✅" if d["beats_baseline"] else "❌"
        out.append(f"   방향정확도  모델 {d['model_acc']:.1%} "
                   f"({d['model_hits']}/{lstm['n']}) · 95%CI [{lo:.1%}, {hi:.1%}]")
        out.append(f"               베이스라인({d['baseline_label']}) {d['baseline_acc']:.1%} "
                   f"({d['baseline_hits']}/{lstm['n']})")
        out.append(f"   {mark} 실력 {d['skill_pp']:+.1f}%p · McNemar "
                   f"b={d['mcnemar']['b_model_only']} c={d['mcnemar']['c_baseline_only']} "
                   f"p={d['mcnemar']['p_two_sided']:.3f}")
        out.append(f"      실제 방향 상승 {d['actual_up']} · 하락 {d['actual_down']} "
                   f"— 한쪽으로 쏠려 있어 상수 규칙이 강하다")
        mark2 = "✅" if e["beats_persistence"] else "❌"
        out.append(f"   오차        모델 MAE {e['model_mae']:.3f} · "
                   f"지속성 {e['persistence_mae']:.3f}")
        out.append(f"   {mark2} 기술점수 MAE {e['mae_skill']:+.1%} · RMSE {e['rmse_skill']:+.1%}"
                   f"  ← **여기에 실력이 있다**")

    gnn = res["gnn"]
    out.append("\n[GNN] 업종 추천")
    if not gnn.get("available"):
        out.append(f"   재지 못했다 — {gnn.get('reason')}")
    else:
        mark = "✅" if gnn["beats_baseline"] else "❌"
        out.append(f"   Top-3       모델 {gnn['top3']:.1%} · "
                   f"거점 사전분포 {gnn['baseline_top3']:.1%}")
        out.append(f"   {mark} 실력 {gnn['skill_pp_top3']:+.2f}%p")
        if "top1" in gnn:
            out.append(f"   Top-1       모델 {gnn['top1']:.1%} · "
                       f"사전분포 {gnn['baseline_top1']:.1%} "
                       f"(실력 {gnn['skill_pp_top1']:+.2f}%p)")
        if gnn.get("offprior_top3") is not None:
            out.append(f"   off-prior   {gnn['offprior_top3']:.1%} "
                       f"({gnn.get('offprior_nodes')}자리) — 사전분포가 못 맞히는 자리")

    out.append("\n" + "=" * 78)
    if res["ok"]:
        out.append("✅ 두 모델 모두 베이스라인을 넘는다(넘는 축 기준).")
    else:
        out.append("❌ 베이스라인 미달 — 이 축의 '목표 달성' 표기는 근거가 없다:")
        out.extend(f"   · {f}" for f in res["failures"])
    out.append("\n⚠ 임계값(70%)만 넘긴 것은 달성이 아니다. 같은 홀드아웃에서 무정보 규칙이")
    out.append("  그 임계값을 넘는지 먼저 본다 — 넘으면 그 게이트는 모델을 보증하지 못한다.")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    res = check()
    if "--json" in argv:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(_fmt(res))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
