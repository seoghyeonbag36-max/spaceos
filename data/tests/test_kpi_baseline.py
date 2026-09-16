"""KPI 실력 검정 잠금 — 무정보 베이스라인을 못 이기는 모델이 '달성'으로 새지 않게.

## 이 테스트가 막는 것 (2026-09-16 실측)

`docs/feature-platform.md` 는 LSTM 방향정확도 70.8% 를 "목표 70% 달성"으로 적어 왔다.
같은 홀드아웃에서 **입력을 하나도 안 보는 상수 규칙**(항상 하락)이 78.5% 다. 즉 옛
게이트는 실력 0 인 모델을 통과시킨다. 같은 구멍이 GNN 에도 있었다 — Top-3 ≥70% 인데
거점 사전분포만으로 89.4% 가 나온다.

구멍의 공통 원인은 **임계값을 베이스라인 없이 고정한 것**이다. 여기서 잠그는 것은
숫자가 아니라 그 규칙이다: 판정은 언제나 같은 표본에서 유도된 베이스라인과의 차이로
한다. 실측값을 고정하면 가드 자신이 드리프트의 원인이 되므로(test_progress_docs 의
2026-09-05 교훈) 개별 수치는 고정하지 않는다.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from kpi_baseline import (  # noqa: E402
    check,
    cluster_bootstrap_ci,
    detectability,
    gnn_skill,
    lstm_skill,
    mcnemar_exact,
    skew_robust,
    wilson,
)


# ─────────────────────────── 통계 도구 ───────────────────────────

def test_wilson_bounds_contain_point_estimate() -> None:
    lo, hi = wilson(46, 65)
    assert lo < 46 / 65 < hi
    # n=65 에서 구간 폭이 20%p 를 넘는다 — 점추정으로 70% 선을 가를 수 없다는 근거.
    assert hi - lo > 0.20
    assert lo < 0.70 < hi, "옛 목표 70% 가 구간 안에 있어야 한다(달성 판정 불가의 근거)"


def test_wilson_handles_degenerate_n() -> None:
    assert wilson(0, 0) == (0.0, 0.0)


def test_mcnemar_exact_matches_known_values() -> None:
    assert mcnemar_exact(0, 0) == 1.0
    # b=c 면 완전 무차별 → p=1
    assert mcnemar_exact(5, 5) == pytest.approx(1.0)
    # 한쪽으로 전부 몰리면 2 * (1/2)^n
    assert mcnemar_exact(0, 4) == pytest.approx(2 * (1 / 2) ** 4)


# ─────────────────────────── LSTM ───────────────────────────

def _holdout(rows: list[tuple[float, float, float]]) -> dict:
    """(pred, actual, prev) 목록 → forecast JSON 모양."""
    return {"holdout": {f"h{i}": {"pred": p, "actual": a, "prev": v}
                        for i, (p, a, v) in enumerate(rows)}}


def test_lstm_model_that_loses_to_constant_rule_does_not_pass() -> None:
    """**핵심 잠금.** 임계값을 넘겨도 상수 규칙에 지면 통과하면 안 된다.

    실제가 전부 하락인데 모델이 절반을 상승이라 찍는 경우 — 정확도는 50% 이고
    '항상 하락' 은 100% 다.
    """
    rows = [(2.0, -1.0, 0.0)] * 5 + [(-2.0, -1.0, 0.0)] * 5   # 5 틀리고 5 맞음
    res = lstm_skill(_holdout(rows))
    d = res["direction"]
    assert d["baseline_label"] == "항상 하락"
    assert d["baseline_acc"] == 1.0
    assert d["model_acc"] == 0.5
    assert d["skill_pp"] < 0
    assert d["beats_baseline"] is False


def test_lstm_model_that_beats_constant_rule_passes() -> None:
    """방향이 갈리는 표본에서 전부 맞히면 실력이 양수여야 한다."""
    rows = [(1.0, 1.0, 0.0)] * 5 + [(-1.0, -1.0, 0.0)] * 5     # 상승 5 · 하락 5, 전부 적중
    d = lstm_skill(_holdout(rows))["direction"]
    assert d["model_acc"] == 1.0
    assert d["baseline_acc"] == 0.5          # 어느 상수 규칙도 절반만 맞는다
    assert d["skill_pp"] > 0
    assert d["beats_baseline"] is True


def test_lstm_error_axis_is_measured_against_persistence() -> None:
    """오차 축은 지속성(예측=직전값)과 대조한다 — 방향 축과 답이 다를 수 있다."""
    # 직전값 0, 실제 −1. 모델은 −0.9 로 가깝고 방향도 맞다.
    d = lstm_skill(_holdout([(-0.9, -1.0, 0.0)] * 8))
    assert d["error"]["persistence_mae"] == pytest.approx(1.0)
    assert d["error"]["model_mae"] == pytest.approx(0.1)
    assert d["error"]["beats_persistence"] is True
    assert d["error"]["mae_skill"] > 0


def test_lstm_reports_unavailable_instead_of_guessing() -> None:
    """홀드아웃이 없으면 '못 쟀다'로 물러난다 — 0% 도 100% 도 아니다."""
    res = lstm_skill({"holdout": {}})
    assert res["available"] is False


# ─────────────────────────── GNN ───────────────────────────

def test_gnn_without_baseline_cannot_pass() -> None:
    """베이스라인이 없는 정확도는 판정 근거가 아니다 — 높아도 available=False."""
    res = gnn_skill({"metrics": {"test_top3": 0.99}})
    assert res["available"] is False


def test_gnn_skill_is_difference_from_district_prior() -> None:
    res = gnn_skill({"metrics": {"test_top3": 0.9167,
                                 "baseline_district_prior_top3": 0.8935}})
    assert res["beats_baseline"] is True
    assert res["skill_pp_top3"] == pytest.approx(2.32, abs=0.01)


def test_gnn_at_or_below_prior_fails() -> None:
    """사전분포와 같으면 그래프가 얹은 것이 없다 — 동점은 통과가 아니다."""
    res = gnn_skill({"metrics": {"test_top3": 0.8935,
                                 "baseline_district_prior_top3": 0.8935}})
    assert res["beats_baseline"] is False


# ─────────────────────────── 쏠림에 강한 관측 지표 ───────────────────────────

def test_constant_rule_scores_zero_on_skew_robust_metrics() -> None:
    """**진단의 핵심.** 상수 규칙은 균형정확도 50%·MCC 0 이다 — 정의상.

    원시 정확도로는 상수가 이기지만(78.5%), 이 두 지표로는 못 이긴다. 그래서 모델에
    신호가 있는지를 표본 쏠림과 분리해 볼 수 있다.
    """
    ob = skew_robust(tp=0, fp=0, fn=14, tn=51)   # 전부 하락이라 찍은 경우
    assert ob["balanced_acc"] == pytest.approx(0.5)
    assert ob["mcc"] == 0.0
    assert ob["recall_up"] == 0.0


def test_skew_robust_detects_minority_signal() -> None:
    """서빙 산출물의 실측 혼동행렬에서는 신호가 잡혀야 한다(상승 8/14 적중)."""
    ob = skew_robust(tp=8, fp=13, fn=6, tn=38)
    assert ob["balanced_acc"] > 0.5
    assert ob["mcc"] > 0.0
    assert ob["precision_up"] > 14 / 65, "상승 정밀도가 기저율보다 높아야 신호다"


def test_observed_block_is_not_used_for_the_verdict() -> None:
    """관측 지표가 판정을 뒤집으면 안 된다 — 그게 metric shopping 이다."""
    res = check()
    d = res["lstm"]["direction"]
    assert "observed" in d
    assert d["observed"]["balanced_acc"] > 0.5      # 신호는 있는데
    assert d["beats_baseline"] is False             # 판정은 여전히 미달이다
    assert any("베이스라인" in m for m in res["failures"])


# ─────────────────────────── 롤링 오리진 · 군집 구간 ───────────────────────────

def _holdout_rolling(per_hub: dict) -> dict:
    out = {}
    for hub, rows in per_hub.items():
        for i, (p, a, v) in enumerate(rows):
            out[f"{hub}@q{i}"] = {"hub": hub, "pred": p, "actual": a, "prev": v}
    return {"holdout": out}


def test_rolling_origin_keys_do_not_collapse_samples() -> None:
    """거점당 여러 건이면 표본이 그대로 세어져야 한다 — 키가 겹치면 조용히 1/K 로 준다."""
    res = lstm_skill(_holdout_rolling({"a": [(1, 1, 0)] * 3, "b": [(-1, -1, 0)] * 3}))
    assert res["n"] == 6
    assert res["n_hubs"] == 2
    assert res["samples_per_hub"] == pytest.approx(3.0)


def test_cluster_bootstrap_is_used_when_hubs_repeat() -> None:
    """거점당 표본이 여럿이면 이항 공식이 아니라 군집 부트스트랩을 쓴다."""
    many = _holdout_rolling({f"h{i}": [(1, 1, 0), (-1, 1, 0)] for i in range(8)})
    assert lstm_skill(many)["direction"]["ci_kind"] == "cluster_bootstrap"
    single = _holdout_rolling({f"h{i}": [(1, 1, 0)] for i in range(8)})
    assert lstm_skill(single)["direction"]["ci_kind"] == "wilson"


def test_cluster_bootstrap_is_wider_than_binomial_under_clustering() -> None:
    """군집이 있으면 구간이 이항보다 넓어야 한다 — 좁으면 독립을 가정한 것이다.

    거점 안에서는 결과가 완전히 같고 거점끼리만 갈리는 극단적 군집 표본을 쓴다.
    이항 공식은 20건으로 보지만 실제 정보량은 거점 10곳뿐이다.
    """
    lo_b, hi_b = wilson(10, 20)
    lo_c, hi_c = cluster_bootstrap_ci([[True] * 2] * 5 + [[False] * 2] * 5)
    assert (hi_c - lo_c) > (hi_b - lo_b), "군집 구간이 이항보다 좁다 — 독립 가정이 남아 있다"


def test_legacy_holdout_without_hub_field_still_reads() -> None:
    """옛 산출물(거점명이 곧 키, hub 필드 없음)도 그대로 읽혀야 한다."""
    res = lstm_skill({"holdout": {"anam": {"pred": 1, "actual": 1, "prev": 0}}})
    assert res["available"] and res["n"] == 1 and res["n_hubs"] == 1


# ─────────────────────────── 검정력 ───────────────────────────

def test_detectability_shrinks_with_sample_size() -> None:
    """표본이 커질수록 가를 수 있는 차이가 작아진다 — 1/√n."""
    small = detectability(0.34, 1011)
    big = detectability(0.34, 4399)
    assert small["min_detectable_pp"] > big["min_detectable_pp"]
    # 저장소 자체 스코핑(scope-offprior-sample-2026-09-06)과 같은 눈금이어야 한다.
    assert small["min_detectable_pp"] == pytest.approx(3.0, abs=0.2)
    assert big["min_detectable_pp"] == pytest.approx(1.5, abs=0.2)


def test_detectability_handles_empty_sample() -> None:
    d = detectability(0.5, 0)
    assert d["min_detectable_pp"] is None


def test_gnn_skill_below_resolution_is_flagged_not_claimed() -> None:
    """**핵심.** 실력이 양수라도 분해능 아래면 '말할 수 없는 차이'로 표시돼야 한다.

    2026-08-26 레버 실험이 남긴 교훈이다 — 못 가른 것과 차이가 없는 것은 다르다.
    """
    res = gnn_skill({"metrics": {"test_top3": 0.9167,
                                 "baseline_district_prior_top3": 0.8935,
                                 "test_nodes": 300}})          # 작은 표본
    assert res["beats_baseline"] is True          # 부호는 양수인데
    assert res["skill_is_detectable"] is False    # 크기는 말할 수 없다


def test_gnn_skill_above_resolution_is_detectable() -> None:
    res = gnn_skill({"metrics": {"test_top3": 0.9167,
                                 "baseline_district_prior_top3": 0.8935,
                                 "test_nodes": 9493}})
    assert res["skill_is_detectable"] is True


def test_missing_test_nodes_does_not_get_estimated() -> None:
    """test 표본 수가 없으면 **추정하지 않는다** — 추정한 n 으로 낸 검정력은 근거가 아니다."""
    res = gnn_skill({"metrics": {"test_top3": 0.9167,
                                 "baseline_district_prior_top3": 0.8935,
                                 "nodes": 47442}})             # 전체 그래프뿐
    assert res["test_nodes"] is None
    assert res["skill_is_detectable"] is None
    assert res["detectability"]["min_detectable_pp"] is None


def test_train_gnn_records_test_sample_size() -> None:
    """산출물이 test 표본 수를 남겨야 다음 판정이 검정력을 계산할 수 있다."""
    src = (ROOT / "ml" / "training" / "train_gnn.py").read_text(encoding="utf-8")
    assert '"test_nodes"' in src, "test_nodes 기록이 사라졌다 — 검정력을 못 낸다"


# ─────────────────────────── 서빙 산출물 ───────────────────────────

def test_check_reads_serving_artifacts_and_reports_both_axes() -> None:
    """서빙 산출물로 실제 판정이 돌아야 한다(값은 고정하지 않는다)."""
    res = check()
    assert res["lstm"]["available"], "platform_vacancy_forecast.json 의 holdout 표가 필요하다"
    assert res["gnn"]["available"], "platform_industry_recommend.json 의 baseline 이 필요하다"
    for key in ("model_acc", "baseline_acc", "skill_pp", "beats_baseline", "model_ci95"):
        assert key in res["lstm"]["direction"]
    for key in ("model_mae", "persistence_mae", "mae_skill", "beats_persistence"):
        assert key in res["lstm"]["error"]
    # 판정은 항상 베이스라인 대조를 거친다 — ok 가 True 여도 근거가 남아야 한다.
    assert isinstance(res["failures"], list)
    assert res["ok"] == (not res["failures"])


def test_failures_name_the_baseline_not_just_the_threshold() -> None:
    """실패 문구는 '70% 미달' 이 아니라 **무엇에 졌는지**를 말해야 한다."""
    res = check()
    for msg in res["failures"]:
        assert "베이스라인" in msg or "사전분포" in msg or "지속성" in msg
