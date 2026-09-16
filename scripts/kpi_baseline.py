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


def cluster_bootstrap_ci(hits_by_cluster: list[list[bool]], reps: int = 2000,
                         seed: int = 42) -> tuple[float, float]:
    """거점 단위 군집 부트스트랩 95% 구간.

    롤링 오리진으로 거점당 표본이 여럿이면 **이항 공식을 쓰면 안 된다** — 같은 거점의
    이웃 분기는 상관돼 있어 표본이 독립이 아니고, Wilson 구간은 그만큼 좁게 나온다.
    거점(군집)을 복원추출해 구간을 낸다. 거점당 1건이면 보통 부트스트랩과 같아진다.
    """
    import random

    k = len(hits_by_cluster)
    if k == 0:
        return (0.0, 0.0)
    rng = random.Random(seed)
    accs: list[float] = []
    for _ in range(reps):
        picked = [hits_by_cluster[rng.randrange(k)] for _ in range(k)]
        flat = [h for c in picked for h in c]
        if flat:
            accs.append(sum(flat) / len(flat))
    if not accs:
        return (0.0, 0.0)
    accs.sort()
    return (accs[int(0.025 * len(accs))], accs[min(len(accs) - 1, int(0.975 * len(accs)))])


def skew_robust(tp: int, fp: int, fn: int, tn: int) -> dict:
    """쏠린 이진 표본에서 **상수 규칙이 구조적으로 못 이기는** 지표들.

    원시 정확도는 다수 클래스 비율에 지배된다(실측: 하락 51 · 상승 14 에서 '항상 하락'
    이 78.5%). 균형정확도와 MCC 는 상수 규칙이 각각 정확히 50%·0 이므로, 모델에
    신호가 있는지를 원시 정확도와 **독립적으로** 드러낸다.

    ⚠ 이 값들은 **관측**이다. 판정 지표를 결과를 보고 바꾸면 그 자체가 metric shopping
    이라 이 저장소가 막아 온 누수와 같은 종류가 된다. 판정에 쓰려면 재학습 **전에**
    확정해야 한다 — docs/finding-lstm-direction-diagnosis-2026-09-16.md §무엇을 하면 되나.
    """
    rec_pos = tp / (tp + fn) if tp + fn else 0.0
    rec_neg = tn / (tn + fp) if tn + fp else 0.0
    den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return {
        "recall_up": rec_pos, "recall_down": rec_neg,
        "precision_up": tp / (tp + fp) if tp + fp else 0.0,
        "balanced_acc": (rec_pos + rec_neg) / 2,      # 상수 규칙 = 0.5
        "mcc": ((tp * tn - fp * fn) / den) if den else 0.0,   # 상수 규칙 = 0
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def _sgn(x: float) -> int:
    return (x > 0) - (x < 0)


# ─────────────────────────── LSTM ───────────────────────────

def lstm_skill(forecast: dict) -> dict:
    """공실 예측 — 방향정확도·오차 두 축을 각각 베이스라인에 댄다.

    방향은 베이스라인을 못 이기고(실력 음수), 오차는 이긴다. **두 축이 갈리므로
    하나만 인용하면 어느 쪽이든 거짓이 된다** — 그래서 둘 다 돌려준다.
    """
    hold = forecast.get("holdout") or {}
    # 키는 `거점@분기`(롤링 오리진) 또는 `거점`(단일 원점). 군집 단위는 **거점**이라
    # `hub` 필드를 우선 쓰고, 없으면 키에서 `@` 앞을 떼어 옛 산출물도 읽는다.
    rows = [(v.get("hub") or str(k).split("@")[0],
             v.get("pred"), v.get("actual"), v.get("prev")) for k, v in hold.items()]
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

    # 혼동행렬(상승=양성) — 소수 클래스에 신호가 있는지 본다
    tp = sum(1 for _, p, a, pr in rows if p - pr > 0 and a - pr > 0)
    fp = sum(1 for _, p, a, pr in rows if p - pr > 0 and a - pr <= 0)
    fn = sum(1 for _, p, a, pr in rows if p - pr <= 0 and a - pr > 0)
    tn = n - tp - fp - fn

    # 군집(거점) 단위 적중 목록 → 부트스트랩 구간
    by_hub: dict[str, list[bool]] = {}
    for hub, p, a, pr in rows:
        by_hub.setdefault(hub, []).append(_sgn(p - pr) == _sgn(a - pr))
    n_hubs = len(by_hub)
    per_hub = n / n_hubs if n_hubs else 0.0
    # 거점당 1건이면 Wilson 과 사실상 같으므로 굳이 부트스트랩을 돌리지 않는다.
    ci_kind = "wilson" if per_hub <= 1.0 else "cluster_bootstrap"
    ci = (list(wilson(hits, n)) if ci_kind == "wilson"
          else list(cluster_bootstrap_ci(list(by_hub.values()))))

    acc, base_acc = hits / n, base_hits / n
    return {
        "available": True,
        "n": n,
        "n_hubs": n_hubs,
        "samples_per_hub": per_hub,
        "direction": {
            "model_hits": hits, "model_acc": acc, "model_ci95": ci, "ci_kind": ci_kind,
            "baseline_label": base_label, "baseline_hits": base_hits,
            "baseline_acc": base_acc, "baseline_ci95": list(wilson(base_hits, n)),
            "skill_pp": (acc - base_acc) * 100.0,
            "mcnemar": {"b_model_only": b, "c_baseline_only": c,
                        "p_two_sided": mcnemar_exact(b, c)},
            "actual_up": up, "actual_down": down,
            "beats_baseline": acc > base_acc,
            # 관측 전용 — 판정에 쓰지 않는다(위 skew_robust 독스트링 참조)
            "observed": skew_robust(tp, fp, fn, tn),
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

def detectability(p: float, n: int) -> dict:
    """이 표본으로 **얼마나 작은 차이까지 가를 수 있나**.

    2026-08-26 GNN 레버 실험이 남긴 교훈이 이것이다: +2.05%p 가 McNemar 에서
    p=0.111 이라 "유의하지 않다" 로 끝났는데, 그건 **차이가 없다**가 아니라
    **이 표본으로는 못 가른다**는 뜻이었다. 표본 크기를 옆에 안 적으면 그 둘이
    구분되지 않고, 못 가른 것이 기각으로 읽힌다.

    근사식은 `docs/scope-offprior-sample-2026-09-06.md` 가 쓴 것과 같다(단일 팔
    표준오차의 2배). ⚠ 같은 test 집합 위의 **쌍대** 비교라 올바른 검정은 McNemar
    이고, 그 2×2 표는 노드별 예측을 남겨야 만들 수 있다(`--dump-preds`).
    여기 값은 "표본이 이 정도는 돼야 말할 수 있다" 는 눈금이지 검정 결과가 아니다.
    """
    if n <= 0:
        return {"n": 0, "se_pp": None, "min_detectable_pp": None}
    se = math.sqrt(max(p * (1 - p), 0.0) / n) * 100.0
    return {"n": n, "se_pp": round(se, 2), "min_detectable_pp": round(2 * se, 2)}


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
    skill_pp = (top3 - b3) * 100.0
    # test 표본 수. 옛 산출물에는 `nodes`(전체 그래프)뿐이라 없으면 **추정하지 않고**
    # None 으로 둔다 — 추정한 n 으로 낸 검정력은 근거가 아니다.
    n_test = m.get("test_nodes")
    det = detectability(top3, n_test) if n_test else {"n": None, "se_pp": None,
                                                      "min_detectable_pp": None}
    mdp = det.get("min_detectable_pp")
    out = {
        "available": True,
        "top3": top3, "baseline_top3": b3, "skill_pp_top3": skill_pp,
        "beats_baseline": top3 > b3,
        "detectability": det,
        # 실력이 양수라도 그 크기가 분해능 아래면 **말할 수 없는 차이**다.
        "skill_is_detectable": (abs(skill_pp) >= mdp) if mdp is not None else None,
        "offprior_top3": m.get("test_offprior_top3"),
        "offprior_nodes": m.get("offprior_nodes"),
        "offprior_detectability": (
            detectability(m["test_offprior_top3"], m["offprior_nodes"])
            if m.get("test_offprior_top3") is not None and m.get("offprior_nodes")
            else None),
        "test_nodes": n_test,
        "graph_nodes": m.get("nodes"),
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
        ob = d.get("observed") or {}
        if ob:
            c = ob["confusion"]
            out.append(f"   [관측] 균형정확도 {ob['balanced_acc']:.1%}(상수 50.0%) · "
                       f"MCC {ob['mcc']:+.3f}(상수 0)")
            out.append(f"          상승 재현율 {ob['recall_up']:.1%}"
                       f"({c['tp']}/{c['tp'] + c['fn']}) · "
                       f"정밀도 {ob['precision_up']:.1%} · "
                       f"하락 재현율 {ob['recall_down']:.1%}"
                       f"({c['tn']}/{c['tn'] + c['fp']})")
            out.append("          → 상수 규칙은 균형정확도 50%·MCC 0 이다. 이 둘이 그보다 "
                       "높으면 **모델에 신호는 있다**는 뜻이고,")
            out.append("            원시 정확도가 지는 것은 표본 쏠림 탓이다. "
                       "⚠ 관측일 뿐 판정 지표가 아니다(결과를 보고 바꾸면 metric shopping)")
        if lstm.get("samples_per_hub", 0) > 1:
            out.append(f"   [분할] 거점 {lstm['n_hubs']}곳 × 거점당 "
                       f"{lstm['samples_per_hub']:.1f}건 (롤링 오리진) · "
                       f"구간은 {d['ci_kind']} — 같은 거점의 이웃 분기는 독립이 아니다")
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
        det = gnn.get("detectability") or {}
        if det.get("min_detectable_pp") is not None:
            verdict = ("가를 수 있다" if gnn.get("skill_is_detectable")
                       else "**이 표본으로는 못 가른다**")
            out.append(f"   [검정력] test {det['n']}자리 · SE {det['se_pp']}%p · "
                       f"가별 최소 차이 ≈{det['min_detectable_pp']}%p → {verdict}")
        else:
            out.append("   [검정력] test 표본 수가 산출물에 없다 — 재학습하면 "
                       "`test_nodes` 가 채워진다(추정으로 대신하지 않는다)")
        od = gnn.get("offprior_detectability")
        if od and od.get("min_detectable_pp") is not None:
            out.append(f"   [검정력] off-prior {od['n']}자리 · 가별 최소 차이 "
                       f"≈{od['min_detectable_pp']}%p — 라벨 축(category2)으로 가면 "
                       f"자리가 4.35배가 된다(scope-offprior-sample-2026-09-06)")
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
