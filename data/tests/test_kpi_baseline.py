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
    gnn_skill,
    lstm_skill,
    mcnemar_exact,
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
