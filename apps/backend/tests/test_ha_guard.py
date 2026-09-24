"""Humanistic Authority 후처리 검증기 테스트 (services/ha_guard.py).

## 이 스위트가 지키는 것 두 가지

1. **위반을 잡는가** — 지어낸 금액·확정 트렌드 역행·있지도 않은 경험 주장은 violation
   으로 응답이 폐기돼야 한다.
2. **정상 산출물을 죽이지 않는가** — 이쪽이 더 중요하다. 사전 기반 규칙은 세게 걸면
   진짜 산출물까지 죽인다(2026-08-01 동명이지 정제에서 체험단 필터를 포기한 것과 같은
   이유). 그래서 오탐이 날 만한 문장을 **음성 대조로 명시해 고정한다** — "손님을 늘리는
   전단"(목표이지 주장이 아니다), "최대한 활용"(최대가 아니다), "경쟁력"(비방이 아니다),
   **"재방문율을 집계한다"(측정이지 주장이 아니다)**.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.marketing import LLMDistrictContents, LLMProgramPlan
from app.services import ha_guard
from tests.conftest import _act, _perf, _signal

client = TestClient(app)
V1 = "/api/v1"


@pytest.fixture(autouse=True)
def _isolate_marketing_cache():
    """상권 콘텐츠 캐시 격리 — 앞 테스트의 캐시를 물면 폐기/생성 판정을 검증하지 못한다."""
    from app.services import marketing as mkt
    mkt.clear_district_cache()
    yield
    mkt.clear_district_cache()


def _plan(online=None, offline=None, signals=None, ha_check="점검 통과") -> LLMProgramPlan:
    return LLMProgramPlan(
        online=online or [_perf(
            channel="인스타그램", content="팝업 예고 릴스 주 2회",
            rationale="검증 기간이 짧아 사전 인지가 필요하다")],
        offline=offline or [_act(
            channel="입간판", content="시식 이벤트",
            rationale="보행 유동객 전환을 노린다")],
        signals=signals if signals is not None else [_signal()],
        ha_check=ha_check,
    )


# 검증 브리프 — 예비창업자가 낸 팝업 계획. 금액의 **유일한** 정본은 예산 구간이다
# (종전에는 점주가 준 메뉴 가격이 그 자리였다 — 2026-09-17 대상 재정의로 사라졌다).
_BRIEF = {
    "item": "산미 중심 스페셜티 원두 팝업",
    "category": "카페",
    "mode": "popup",
    "stage": "pre_founder",
    "district_id": "garosugil",
    "hypothesis": "가로수길 20~30대에게 산미 강한 원두가 통한다",
    "target_customer": "20~30대 직장인",
    "start_date": "2026-10-01",
    "run_days": 7,
    "budget_krw_min": 300000,
    "budget_krw_max": 800000,
    "differentiators": ["주간 단위 원두 교체", "산미 중심 큐레이션"],
}


def _codes(findings) -> set[str]:
    return {f.code for f in findings}


# ── 금액 (violation) ─────────────────────────────────────────────────────────

def test_fabricated_price_is_violation():
    """브리프 예산에 없는 금액을 말하면 위반 — 지어낸 가격은 그대로 전단에 인쇄된다."""
    parsed = _plan(offline=[_act(
        channel="전단", content="런치 세트 12,000원 한정 행사", rationale="점심 수요 공략")])
    findings = ha_guard.check_program(parsed, _BRIEF, None)
    assert "fabricated_price" in _codes(findings)
    assert ha_guard.has_violation(findings)
    assert "12,000원" in next(f for f in findings if f.code == "fabricated_price").evidence


def test_budget_band_quoted_verbatim_passes():
    """창업자가 준 예산 구간을 인용하는 것은 정상이다 (음성 대조).

    이걸 못 지나가면 "예산 800000원 안에서" 같은 정당한 문장이 폐기된다 — 행사 요금을
    컨텍스트에 넣어야 했던 2026-08-06 과 같은 이유다.
    """
    parsed = _plan(offline=[_act(
        channel="입간판", content="800000원 상한 안에서 자재를 맞춘다",
        rationale="브리프에 적힌 예산 상한을 그대로 따른다")])
    assert "fabricated_price" not in _codes(ha_guard.check_program(parsed, _BRIEF, None))


def test_arbitrary_discount_amount_is_violation():
    """할인액도 지어낸 금액이다 — 얼마를 깎을지는 창업자가 정할 몫이다."""
    parsed = _plan(offline=[_act(
        channel="쿠폰", content="첫 방문 3,000원 할인", rationale="초기 유입 유도")])
    assert "fabricated_price" in _codes(ha_guard.check_program(parsed, _BRIEF, None))


def test_man_won_notation_is_caught():
    """'1만원' 표기도 금액이다 — 콤마 표기만 잡으면 우회된다."""
    parsed = _plan(offline=[_act(
        channel="전단", content="1만원 세트 출시", rationale="가격 접근성")])
    assert "fabricated_price" in _codes(ha_guard.check_program(parsed, _BRIEF, None))


def test_no_price_anywhere_passes():
    """금액을 아예 안 쓰면 통과한다 — 금액 없는 제안이 권장 형태다 (음성 대조)."""
    parsed = _plan(offline=[_act(
        channel="쿠폰", content="첫 방문 쿠폰 운영(할인 폭은 창업자가 정한다)",
        rationale="초기 유입 유도")])
    assert "fabricated_price" not in _codes(ha_guard.check_program(parsed, _BRIEF, None))


# ── 미검증 경험 (violation) ──────────────────────────────────────────────────
# 2026-09-17 신설. 대상이 전부 "이 자리에서 이 아이템을 안 해 본 사람"이라 이 검사는
# 조건 없이 항상 켜진다. 종전 `pre_open_visit_claim` 을 대체한다.

def test_unproven_experience_claim_is_violation():
    """단골·기존 고객은 이 자리에 존재하지 않는다 — 있다고 말하면 그대로 거짓이다."""
    parsed = _plan(online=[_perf(
        channel="인스타그램", content="단골 고객에게 먼저 소식을 전한다",
        rationale="기존 관계를 활용한다")])
    findings = ha_guard.check_program(parsed, _BRIEF, None)
    assert "unproven_experience_claim" in _codes(findings)
    assert ha_guard.has_violation(findings)


def test_measuring_revisit_rate_is_not_a_claim():
    """**핵심 음성 대조.** 재방문율은 팝업 검증의 지표다 — 주장이 아니다.

    이걸 잡으면 이 트랙의 결론인 검증 지표가 통째로 폐기된다. 거르는 것은 지표가
    아니라 "이미 있다고 말하는 것"이다.
    """
    parsed = _plan(signals=[_signal(
        name="재방문 고객 비율", method="영수증의 재방문 고객 비율을 일별로 집계한다",
        target="7일차 15%", decision="5% 미만이면 재구매 가설을 기각한다")])
    assert "unproven_experience_claim" not in _codes(
        ha_guard.check_program(parsed, _BRIEF, None))


def test_collecting_reviews_as_a_goal_is_not_a_claim():
    """후기 수집은 가오픈의 목적이다 — 쌓인 후기가 있다는 주장과 다르다 (음성 대조)."""
    parsed = _plan(online=[_perf(
        channel="네이버 플레이스", content="방문객에게 후기 작성을 요청해 응답을 수집한다",
        rationale="검증 기간의 정성 신호를 남긴다")])
    assert "unproven_experience_claim" not in _codes(
        ha_guard.check_program(parsed, _BRIEF, None))


# ── 트렌드 방향 (violation) ──────────────────────────────────────────────────

_CTX_DOWN = "검색 트렌드(최근 6개월, 방향은 계산된 값이다): 가로수길 하락(26.3→21.4, -18.6%)"
_CTX_UP = "검색 트렌드(최근 6개월, 방향은 계산된 값이다): 가로수길 상승(21.4→26.3, +22.9%)"
_CTX_MIXED = _CTX_DOWN + "; 신사동 상승(60.0→70.0, +16.7%)"


def test_trend_contradiction_is_violation():
    """2026-08-01 실사고 문장 그대로 — 하락인데 유입 증가를 주장하면 위반."""
    parsed = _plan(online=[_perf(
        channel="인스타그램",
        content="신사동을 찾는 발걸음이 다시 늘고 있는 요즘, 골목 카페 투어",
        rationale="유입 증가 흐름")])
    findings = ha_guard.check_program(parsed, _BRIEF, _CTX_DOWN)
    assert "trend_contradiction" in _codes(findings)
    assert ha_guard.has_violation(findings)


def test_standalone_surge_word_is_violation():
    """'붐비다'는 유입어와 짝지을 필요 없이 그 자체로 증가 주장이다."""
    parsed = _plan(online=[_perf(
        channel="인스타그램", content="요즘 붐비는 골목", rationale="분위기 소구")])
    assert "trend_contradiction" in _codes(ha_guard.check_program(parsed, _BRIEF, _CTX_DOWN))


def test_growth_goal_is_not_a_claim():
    """'손님을 늘리는 전단'은 목표이지 유입이 늘고 있다는 주장이 아니다 (음성 대조).

    이걸 잡으면 정당한 오프라인 제안이 전부 죽는다 — 규칙을 주장 어미로 좁힌 이유다.
    """
    parsed = _plan(offline=[_act(
        channel="전단", content="손님을 늘리는 골목 안내 전단 배포",
        rationale="보행 동선에서 인지도를 높인다")])
    assert "trend_contradiction" not in _codes(
        ha_guard.check_program(parsed, _BRIEF, _CTX_DOWN))


def test_increase_claim_allowed_when_trend_rises():
    """트렌드가 상승이면 증가 서술은 근거가 있다 (음성 대조)."""
    parsed = _plan(online=[_perf(
        channel="인스타그램", content="찾는 발걸음이 늘고 있는 골목",
        rationale="검색 트렌드 상승")])
    assert "trend_contradiction" not in _codes(
        ha_guard.check_program(parsed, _BRIEF, _CTX_UP))


def test_mixed_trend_does_not_block():
    """상승·하락이 섞이면 증가 서술이 정당할 수 있어 걸지 않는다 (음성 대조)."""
    parsed = _plan(online=[_perf(
        channel="인스타그램", content="찾는 손님이 늘어나는 상권",
        rationale="일부 지표 상승")])
    assert "trend_contradiction" not in _codes(
        ha_guard.check_program(parsed, _BRIEF, _CTX_MIXED))


def test_no_context_means_no_trend_check():
    """컨텍스트가 없으면 방향 자체가 없다 — 위반으로 판정하지 않는다 (음성 대조)."""
    parsed = _plan(online=[_perf(
        channel="인스타그램", content="손님이 늘고 있는 골목", rationale="근거")])
    assert "trend_contradiction" not in _codes(ha_guard.check_program(parsed, _BRIEF, None))


def test_missing_context_is_reported_as_unverified_not_as_a_pass():
    """**fail-open 차단.** 검사를 못 돌린 것과 통과한 것이 같아 보이면 안 된다.

    이 검사는 violation 등급이라 응답을 버리는 힘이 있다. 입력 하나가 비었다고 그
    힘이 조용히 사라지면, 트렌드를 뒤집는 카피가 검증을 통과한 것처럼 나간다.
    """
    parsed = _plan(online=[_perf(
        channel="인스타그램", content="손님이 늘고 있는 골목", rationale="근거")])
    findings = ha_guard.check_program(parsed, _BRIEF, None)
    assert "trend_unverified" in _codes(findings)
    # 등급은 warning — 검사 불가는 허위의 증거가 아니므로 응답을 버릴 근거가 못 된다.
    assert not ha_guard.has_violation(findings)


def test_context_without_trend_labels_is_also_unverified():
    """컨텍스트는 있는데 트렌드 라벨만 비어도 같다 — 수집이 비면 여기로 온다."""
    parsed = _plan(online=[_perf(
        channel="인스타그램", content="손님이 늘고 있는 골목", rationale="근거")])
    findings = ha_guard.check_program(parsed, _BRIEF, "신사동 상권 · 키워드: 브런치")
    assert "trend_unverified" in _codes(findings)


def test_ran_and_clean_does_not_emit_unverified():
    """실제로 돌아서 깨끗한 경우에는 흔적을 남기지 않는다 (음성 대조)."""
    parsed = _plan(online=[_perf(
        channel="인스타그램", content="조용한 골목의 원두 팝업", rationale="자리 근거")])
    assert "trend_unverified" not in _codes(
        ha_guard.check_program(parsed, _BRIEF, _CTX_DOWN))


# ── 최상급 (warning) ─────────────────────────────────────────────────────────

def test_unsupported_superlative_is_warning():
    parsed = _plan(online=[_perf(
        channel="인스타그램", content="강남 최고의 원두", rationale="분위기")])
    findings = ha_guard.check_program(parsed, _BRIEF, None)
    assert "unsupported_superlative" in _codes(findings)
    assert not ha_guard.has_violation(findings), "최상급은 경고이지 폐기 사유가 아니다"


def test_superlative_in_brief_is_exempt():
    """창업자가 낸 차별점에 '최고'가 있으면 인용할 근거가 있다 (음성 대조)."""
    brief = {**_BRIEF, "differentiators": [*_BRIEF["differentiators"], "최고 등급 생두"]}
    parsed = _plan(online=[_perf(
        channel="인스타그램", content="브리프가 말하는 '최고 등급 생두'를 그대로 인용",
        rationale="창업자가 제출한 차별점 인용")])
    assert "unsupported_superlative" not in _codes(
        ha_guard.check_program(parsed, brief, None))


def test_choedaehan_is_not_superlative():
    """'최대한'은 '최대'가 아니다 (음성 대조)."""
    parsed = _plan(online=[_perf(
        channel="인스타그램", content="사진을 최대한 활용한 피드", rationale="시각 소구")])
    assert "unsupported_superlative" not in _codes(
        ha_guard.check_program(parsed, _BRIEF, None))


# ── 비방 (warning) ───────────────────────────────────────────────────────────

def test_disparagement_is_warning():
    parsed = _plan(offline=[_act(
        channel="전단", content="주변보다 저렴한 가격 강조", rationale="가격 경쟁")])
    findings = ha_guard.check_program(parsed, _BRIEF, None)
    assert "competitor_disparagement" in _codes(findings)
    assert not ha_guard.has_violation(findings)


def test_competitiveness_word_is_not_disparagement():
    """'경쟁력'은 비방이 아니다 (음성 대조)."""
    parsed = _plan(offline=[_act(
        channel="전단", content="메뉴 경쟁력을 살린 안내", rationale="강점 소구")])
    assert "competitor_disparagement" not in _codes(
        ha_guard.check_program(parsed, _BRIEF, None))


# ── 채널 편중 · 근거 (warning) ───────────────────────────────────────────────

def test_channel_concentration_is_warning():
    """온라인 제안이 전부 같은 계열이면 균형 원칙 위반이다."""
    parsed = _plan(online=[
        _perf(channel="인스타그램 피드", content="a", rationale="근거를 충분히 적었다",
              budget_share=50),
        _perf(channel="인스타그램 릴스", content="b", rationale="근거를 충분히 적었다",
              budget_share=50),
    ])
    findings = ha_guard.check_program(parsed, _BRIEF, None)
    assert "channel_concentration" in _codes(findings)
    assert not ha_guard.has_violation(findings)


def test_mixed_channels_pass():
    """계열이 다르면 통과 (음성 대조)."""
    parsed = _plan(online=[
        _perf(channel="인스타그램", content="a", rationale="근거를 충분히 적었다",
              budget_share=50),
        _perf(channel="네이버 블로그", content="b", rationale="근거를 충분히 적었다",
              budget_share=50),
    ])
    assert "channel_concentration" not in _codes(ha_guard.check_program(parsed, _BRIEF, None))


def test_single_online_plan_is_not_concentration():
    """1건뿐이면 편중을 논할 수 없다 (음성 대조)."""
    parsed = _plan(online=[_perf(
        channel="인스타그램", content="a", rationale="근거를 충분히 적었다")])
    assert "channel_concentration" not in _codes(ha_guard.check_program(parsed, _BRIEF, None))


def test_missing_rationale_is_warning():
    parsed = _plan(offline=[_act(channel="전단", content="시식", rationale="응")])
    findings = ha_guard.check_program(parsed, _BRIEF, None)
    assert "missing_rationale" in _codes(findings)
    assert not ha_guard.has_violation(findings)


# ── 검증 지표 (warning) — 2026-09-17 신설 ────────────────────────────────────
# 팝업·가오픈·MVP 는 홍보가 아니라 판정이 목적이다. 판정에 쓸 수 없는 지표는 밝힌다.
# 등급이 warning 인 것이 설계다 — 여기서 응답을 버리면 멀쩡한 채널안까지 함께 사라진다.

def test_missing_signals_is_warning():
    """지표가 아예 없으면 검증이 아니라 지출이다."""
    parsed = _plan(signals=[])
    findings = ha_guard.check_program(parsed, _BRIEF, None)
    assert "missing_validation_signal" in _codes(findings)
    assert not ha_guard.has_violation(findings)


def test_signal_without_number_is_warning():
    """목표선에 셀 수 있는 값이 없으면 사후에 말을 맞추게 된다."""
    parsed = _plan(signals=[_signal(
        target="많이 오면 성공", method="현장에서 체감으로 판단")])
    assert "unmeasurable_signal" in _codes(ha_guard.check_program(parsed, _BRIEF, None))


def test_signal_without_decision_rule_is_warning():
    """기각 조건은 검증을 시작하기 **전에** 적어야 한다."""
    parsed = _plan(signals=[_signal(decision="좋음")])
    assert "missing_decision_rule" in _codes(ha_guard.check_program(parsed, _BRIEF, None))


def test_countable_signal_passes():
    """숫자가 방법 쪽에 있어도 셀 수 있으면 통과한다 (음성 대조)."""
    parsed = _plan(signals=[_signal(
        name="사전 예약 전환율", method="신청 폼 유입 대비 결제 완료 비율을 7일간 집계",
        target="전환율 8%", decision="4% 미만이면 아이템 가설을 기각한다")])
    codes = _codes(ha_guard.check_program(parsed, _BRIEF, _CTX_DOWN))
    assert "unmeasurable_signal" not in codes
    assert "missing_decision_rule" not in codes


def test_clean_output_has_no_findings():
    """정상 생성물은 findings 가 0건이어야 한다 — 규칙이 늘 뭔가를 잡으면 쓸모가 없다."""
    parsed = _plan(online=[
        _perf(channel="인스타그램", content="팝업 준비 과정을 담은 릴스 주 2회",
              rationale="검증 기간이 짧아 사전 인지가 필요하다", budget_share=50),
        _perf(channel="네이버 블로그", content="팝업 일정 안내 글 + 지역 키워드",
              rationale="지도 검색 유입 동선을 연다", budget_share=50),
    ])
    assert ha_guard.check_program(parsed, _BRIEF, _CTX_DOWN) == []


# ── 배선 (검증 프로그램) ─────────────────────────────────────────────────────

def test_violation_falls_back_to_stub(monkeypatch):
    """허위가 확정되면 LLM 응답을 버리고 스텁으로 내려간다 — 정책의 핵심."""
    from app.core.config import settings
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    bad = _plan(offline=[_act(
        channel="전단", content="런치 세트 12,000원", rationale="점심 수요")])
    monkeypatch.setattr(mkt, "_call_llm", lambda brief, ctx, site=None, brief_ctx=None: bad)

    body = client.post(f"{V1}/marketing/generate", json=_BRIEF).json()
    assert body["source"] == "rule-stub", "위반인데 생성물이 그대로 나갔다"
    codes = {f["code"] for f in body["ha_findings"]}
    assert "fabricated_price" in codes, "폐기 사유가 응답에 없다 — 왜 스텁인지 알 수 없다"
    # 생성물의 문구가 새어나가면 안 된다
    assert "12,000원" not in str(body["online"]) + str(body["offline"]) + str(body["signals"])


def test_warning_keeps_llm_output(monkeypatch):
    """경고 등급은 응답을 살리고 밝히기만 한다."""
    from app.core.config import settings
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    warn = _plan(online=[_perf(
        channel="인스타그램", content="강남 최고의 원두", rationale="산미가 좋다는 자체 평가")])
    monkeypatch.setattr(mkt, "_call_llm", lambda brief, ctx, site=None, brief_ctx=None: warn)

    # 컨텍스트 결합을 끊어 이 테스트가 Gold 적재 상태에 좌우되지 않게 한다.
    monkeypatch.setattr(mkt, "_district_context", lambda d: None)
    body = client.post(f"{V1}/marketing/generate", json=_BRIEF).json()
    assert body["source"] == "llm", "경고인데 응답을 버렸다"
    codes = {f["code"] for f in body["ha_findings"]}
    assert "unsupported_superlative" in codes
    # 2026-09-16: 이 픽스처의 컨텍스트에는 트렌드 라벨이 없다. 종전에는 그 사실이
    # 아무 흔적도 남기지 않아 "트렌드 검사를 통과했다"처럼 보였다 — 실제로는 검사가
    # 돌지 않았다. 지금은 trend_unverified 가 그 자리를 밝힌다.
    assert codes <= {"unsupported_superlative", "trend_unverified"}, codes


def test_stub_without_llm_has_empty_findings(monkeypatch):
    """키가 없어 스텁이 나온 경우와 폐기된 경우는 findings 로 구분된다."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "")
    body = client.post(f"{V1}/marketing/generate", json=_BRIEF).json()
    assert body["source"] == "rule-stub"
    assert body["ha_findings"] == []


# ── 배선 (상권 단위) ─────────────────────────────────────────────────────────

def test_district_violation_falls_back_to_seed(monkeypatch):
    """상권 카피가 확정 트렌드를 뒤집으면 시드로 내려간다 (08-01 사고의 회귀 방지)."""
    from app.core.config import settings
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(mkt, "_district_context", lambda d: _CTX_DOWN)
    bad = LLMDistrictContents(
        online_contents=["신사동을 찾는 발걸음이 다시 늘고 있는 요즘 #가로수길 #산책"],
        ha_check="점검 통과")
    monkeypatch.setattr(mkt, "_call_district_llm", lambda name, sub, ctx: bad)

    body = client.get(f"{V1}/marketing/garosugil").json()
    assert body["source"] == "seed", "위반인데 생성 카피가 그대로 나갔다"
    assert "trend_contradiction" in {f["code"] for f in body["ha_findings"]}
    assert not any("늘고 있는" in c for c in body["online_contents"])


def test_district_violation_is_cached(monkeypatch):
    """폐기된 결과도 캐시한다 — 안 그러면 호출마다 같은 위반을 다시 생성하며 크레딧을 태운다."""
    from app.core.config import settings
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(mkt, "_district_context", lambda d: _CTX_DOWN)
    calls: list[int] = []

    def spy(name, sub, ctx):
        calls.append(1)
        return LLMDistrictContents(
            online_contents=["붐비는 골목 #가로수길 #카페"], ha_check="ok")

    monkeypatch.setattr(mkt, "_call_district_llm", spy)

    first = client.get(f"{V1}/marketing/garosugil").json()
    second = client.get(f"{V1}/marketing/garosugil").json()
    assert len(calls) == 1, "폐기된 결과가 캐시되지 않아 LLM 을 다시 쳤다"
    assert first["source"] == second["source"] == "seed"
    assert second["ha_findings"], "캐시 경로가 폐기 사유를 잃었다"


def test_district_clean_output_is_served(monkeypatch):
    """정상 카피는 그대로 나가고 findings 는 비어 있다 (음성 대조)."""
    from app.core.config import settings
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(mkt, "_district_context", lambda d: _CTX_DOWN)
    good = LLMDistrictContents(
        online_contents=["골목마다 다른 커피 취향 #가로수길 #카페투어"], ha_check="ok")
    monkeypatch.setattr(mkt, "_call_district_llm", lambda name, sub, ctx: good)

    body = client.get(f"{V1}/marketing/garosugil").json()
    assert body["source"] == "llm"
    assert body["ha_findings"] == []
