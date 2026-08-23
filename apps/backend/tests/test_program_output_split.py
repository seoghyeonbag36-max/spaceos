"""Program 출력 분리 — 퍼포먼스(온라인) / 상권활성화(오프라인) 계약 검증.

## 왜 갈랐나

`ChannelPlan` 은 channel·kind·content·rationale 넷뿐이었다. 그 넷으로는
**타겟·예산배분·협업주체**를 담을 자리가 없다. 특히 협업주체가 빠지면 오프라인
제안이 "상권 플리마켓 참여하세요"가 되는데, 신규 창업자는 혼자 축제를 열 수 없다 —
실측으로 상권 행사 785건 중 57%가 공공·준공공 주최다(docs/feature-program.md §0-B).

## 두 출력은 대칭이 아니다. **주체가 다르다**

| | 온라인 | 오프라인 |
|---|---|---|
| 주체 | 창업 기업 단독 | 기업 + 상권 주체 협업 |
| 필드 | target · budget_share · kpi | timing · actors · mode |

## 행사: 금지가 아니라 분리

2026-08-06 에는 신규 행사 제안을 **통째로 금지**해 지어낸 행사를 막았다. 그런데
대상이 공실 창업 기업으로 바뀌면서 신규 제안이 이 출력의 **목적**이 됐다. 금지를
없애면 지어낸 행사가 돌아오고, 두면 새 출력을 못 만든다. 그래서 `mode` 로 가른다 —
`cite`(기존 행사 인용)는 사실 주장이라 검증하고, `propose`(신규 제안)는 계획이라
허용하되 빈 시간대 수치 인용을 요구한다.
"""
from __future__ import annotations

from app.schemas.marketing import ChannelPlan, LLMStoreMarketing
from app.services import ha_guard, marketing
from tests.conftest import _act, _perf

_PROFILE = {"name": "테스트가게", "category": "F&B", "reviews": ["분위기가 좋다"]}
_NO_EVENT_CTX = ("상권 행사: 확인된 예정 행사가 없다(공공 문화행사 기준). "
                 "행사 참여·연계를 제안하지 말 것 — 없는 행사를 지어내는 셈이다.")


def _store(online=None, offline=None) -> LLMStoreMarketing:
    return LLMStoreMarketing(
        tone_keywords=["키워드"],
        online=online or [_perf("인스타그램", "릴스 주 2회", "리뷰에 분위기 언급이 반복된다")],
        offline=offline or [_act("공동 프로모션", "스탬프 연계",
                                 "6~11시 유동 19.2 / 매출 10.7 = +8.5%p 로 비어 있다")],
        ha_check="점검 통과")


def _codes(f) -> set[str]:
    return {x.code for x in f}


# ── 계약: 두 출력이 서로 다른 필드를 갖는다 ─────────────────────────────────

def test_online_carries_performance_fields():
    p = _perf("인스타그램", "릴스", "근거를 충분히 적었다",
              target="20~30대 직장인", budget_share=60, kpi="저장 수")
    assert (p.target, p.budget_share, p.kpi) == ("20~30대 직장인", 60, "저장 수")


def test_offline_carries_activation_fields():
    p = _act("플리마켓", "주말 공동 부스", "6~11시 +8.5%p",
             timing="주말 오전", actors=["상인회", "구청"], mode="propose")
    assert p.actors == ["상인회", "구청"] and p.mode == "propose"


def test_budget_share_cannot_hold_absolute_amount():
    """예산은 **비율(int)** 이라 '월 30만원' 같은 절대액이 구조적으로 못 들어간다.

    "얼마를 쓸지는 기업 몫"(§0-B 원칙 2)을 프롬프트 문구가 아니라 타입으로 강제한다.
    """
    import pydantic
    try:
        _perf("인스타그램", "릴스", "근거", budget_share="월 30만원")
    except pydantic.ValidationError:
        return
    raise AssertionError("budget_share 에 문자열 금액이 들어갔다")


def test_channel_plan_keeps_four_original_fields():
    """프론트가 받던 네 필드는 그대로다 — 새 필드는 전부 선택이라 기존 소비가 안 깨진다."""
    c = ChannelPlan(channel="인스타그램", kind="online", content="릴스", rationale="근거")
    assert c.target is None and c.actors == [] and c.mode is None


# ── 행사: 인용(cite) 은 검증하고 제안(propose) 은 허용한다 ──────────────────

def test_cite_when_context_says_no_events_is_violation():
    parsed = _store(offline=[_act("지역 행사 참여", "인근 축제 부스 참여",
                                  "상권 공동 활성화 근거", mode="cite")])
    f = ha_guard.check_store(parsed, _PROFILE, _NO_EVENT_CTX)
    assert "fabricated_event" in _codes(f)
    assert ha_guard.has_violation(f)


def test_propose_when_context_says_no_events_is_allowed():
    """신규 제안은 금지되지 않는다 — 이게 이번 변경의 요점이다."""
    parsed = _store(offline=[_act("플리마켓", "주말 공동 부스를 새로 열자고 제안",
                                  "6~11시 유동 19.2 / 매출 10.7 = +8.5%p", mode="propose")])
    f = ha_guard.check_store(parsed, _PROFILE, _NO_EVENT_CTX)
    assert "fabricated_event" not in _codes(f)
    assert not ha_guard.has_violation(f)


def test_cite_is_fine_when_context_has_events():
    ctx = "상권 행사(공공 문화행사 실데이터, 걸어갈 거리 안): 서울아트위크(59m, 무료)"
    parsed = _store(offline=[_act("행사 연계", "서울아트위크 기간 공동 배너",
                                  "59m 거리에서 열린다", mode="cite")])
    assert "fabricated_event" not in _codes(ha_guard.check_store(parsed, _PROFILE, ctx))


def test_propose_without_gap_figure_warns():
    parsed = _store(offline=[_act("플리마켓", "주말 부스를 제안한다",
                                  "상권 공동 활성화에 도움이 된다", mode="propose")])
    f = ha_guard.check_store(parsed, _PROFILE, None)
    assert "unsupported_event_proposal" in _codes(f)
    assert not ha_guard.has_violation(f)      # 경고이지 폐기가 아니다


# ── 협업 주체 · 예산 배분 ───────────────────────────────────────────────────

def test_offline_without_actors_warns():
    """공동 행사(propose)인데 함께할 주체가 없으면 경고. own 은 이 검사에서 빠진다."""
    parsed = _store(offline=[_act("플리마켓", "부스 운영", "6~11시 +8.5%p",
                                  actors=[], mode="propose")])
    assert "missing_actors" in _codes(ha_guard.check_store(parsed, _PROFILE, None))


def test_offline_with_actors_is_clean():
    parsed = _store(offline=[_act("플리마켓", "부스 운영", "6~11시 +8.5%p",
                                  actors=["상인회", "구청"])])
    assert "missing_actors" not in _codes(ha_guard.check_store(parsed, _PROFILE, None))


def test_budget_shares_must_sum_to_100():
    parsed = _store(online=[
        _perf("인스타그램", "릴스", "근거를 충분히 적었다", budget_share=30),
        _perf("네이버 블로그", "포스팅", "근거를 충분히 적었다", budget_share=30)])
    assert "budget_share_mismatch" in _codes(ha_guard.check_store(parsed, _PROFILE, None))


def test_budget_shares_summing_to_100_is_clean():
    parsed = _store(online=[
        _perf("인스타그램", "릴스", "근거를 충분히 적었다", budget_share=60),
        _perf("네이버 블로그", "포스팅", "근거를 충분히 적었다", budget_share=40)])
    assert "budget_share_mismatch" not in _codes(ha_guard.check_store(parsed, _PROFILE, None))


# ── 폴백 스텁도 새 계약을 채운다 ────────────────────────────────────────────

def test_rule_stub_fills_both_contracts():
    out = marketing.generate_store_marketing(dict(_PROFILE))
    assert out["source"] == "rule-stub"
    assert sum(p["budget_share"] for p in out["online"]) == 100
    for p in out["online"]:
        assert p["target"] and p["kpi"]
    modes = [p["mode"] for p in out["offline"]]
    # 스텁은 실제 행사를 모르므로 cite 를 쓰지 않는다. 공동 제안 1건 + 매장 자체 1건.
    assert "cite" not in modes and "propose" in modes
    for p in out["offline"]:
        assert p["actors"], "오프라인 제안에 협업 주체가 비었다"


def test_rule_stub_does_not_claim_visits_for_a_vacancy():
    """리뷰가 없는 입력(= 아직 영업하지 않는 자리)에 '방문 후기형'을 제안하지 않는다.

    2026-08-16 에 실측한 증상이다 — 공실에 방문 후기를 제안하면 있지도 않은 방문을
    전제하는 거짓이 된다.
    """
    out = marketing.generate_store_marketing(
        {"name": "새가게", "category": "F&B", "reviews": []})
    assert not any("방문 후기" in p["content"] for p in out["online"])
