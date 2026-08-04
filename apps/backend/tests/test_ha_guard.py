"""Humanistic Authority 후처리 검증기 테스트 (services/ha_guard.py).

## 이 스위트가 지키는 것 두 가지

1. **위반을 잡는가** — 지어낸 금액·확정 트렌드 역행은 violation 으로 응답이 폐기돼야 한다.
2. **정상 카피를 죽이지 않는가** — 이쪽이 더 중요하다. 사전 기반 규칙은 세게 걸면 진짜
   산출물까지 죽인다(2026-08-01 동명이지 정제에서 체험단 필터를 포기한 것과 같은 이유).
   그래서 오탐이 날 만한 문장을 **음성 대조로 명시해 고정한다** — "손님을 늘리는 전단"
   (목표이지 주장이 아니다), "최대한 활용"(최대가 아니다), "경쟁력"(비방이 아니다).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.marketing import LLMChannelPlan, LLMDistrictContents, LLMStoreMarketing
from app.services import ha_guard

client = TestClient(app)
V1 = "/api/v1"


@pytest.fixture(autouse=True)
def _isolate_marketing_cache():
    """상권 콘텐츠 캐시 격리 — 앞 테스트의 캐시를 물면 폐기/생성 판정을 검증하지 못한다."""
    from app.services import marketing as mkt
    mkt.clear_district_cache()
    yield
    mkt.clear_district_cache()


def _store(online=None, offline=None, ha_check="점검 통과") -> LLMStoreMarketing:
    return LLMStoreMarketing(
        tone_keywords=["키워드"],
        online=online or [LLMChannelPlan(
            channel="인스타그램", content="시그니처 메뉴 릴스 주 2회",
            rationale="리뷰에 분위기 언급이 반복된다")],
        offline=offline or [LLMChannelPlan(
            channel="입간판", content="시식 이벤트",
            rationale="보행 유동객 전환을 노린다")],
        ha_check=ha_check,
    )


_PROFILE = {
    "name": "맡기다",
    "category": "F&B",
    "reviews": ["사장님 손맛이 담긴 특제 소스", "우니 사시미가 인상적"],
    "menu": ["우니 사시미 32,000원", "맡김술상 55,000원"],
}


def _codes(findings) -> set[str]:
    return {f.code for f in findings}


# ── 금액 (violation) ─────────────────────────────────────────────────────────

def test_fabricated_price_is_violation():
    """입력 메뉴에 없는 금액을 말하면 위반 — 지어낸 가격은 그대로 전단에 인쇄된다."""
    parsed = _store(offline=[LLMChannelPlan(
        channel="전단", content="런치 세트 12,000원 한정 행사", rationale="점심 수요 공략")])
    findings = ha_guard.check_store(parsed, _PROFILE, None)
    assert "fabricated_price" in _codes(findings)
    assert ha_guard.has_violation(findings)
    assert "12,000원" in next(f for f in findings if f.code == "fabricated_price").evidence


def test_menu_price_quoted_verbatim_passes():
    """입력에 적힌 금액을 그대로 인용하는 것은 정상이다 (음성 대조)."""
    parsed = _store(offline=[LLMChannelPlan(
        channel="입간판", content="맡김술상 55,000원 구성을 그대로 안내",
        rationale="메뉴에 적힌 품목·가격을 인용")])
    assert "fabricated_price" not in _codes(ha_guard.check_store(parsed, _PROFILE, None))


def test_arbitrary_discount_amount_is_violation():
    """할인액도 지어낸 금액이다 — 얼마를 깎을지는 점주가 정할 몫이다."""
    parsed = _store(offline=[LLMChannelPlan(
        channel="쿠폰", content="재방문 시 3,000원 할인", rationale="재방문 유도")])
    assert "fabricated_price" in _codes(ha_guard.check_store(parsed, _PROFILE, None))


def test_man_won_notation_is_caught():
    """'1만원' 표기도 금액이다 — 콤마 표기만 잡으면 우회된다."""
    parsed = _store(offline=[LLMChannelPlan(
        channel="전단", content="1만원 세트 출시", rationale="가격 접근성")])
    assert "fabricated_price" in _codes(ha_guard.check_store(parsed, _PROFILE, None))


def test_no_price_anywhere_passes():
    """금액을 아예 안 쓰면 통과한다 — 금액 없는 할인 제안이 권장 형태다 (음성 대조)."""
    parsed = _store(offline=[LLMChannelPlan(
        channel="쿠폰", content="재방문 쿠폰 운영(할인 폭은 점주가 정한다)",
        rationale="재방문 유도")])
    assert "fabricated_price" not in _codes(ha_guard.check_store(parsed, _PROFILE, None))


# ── 트렌드 방향 (violation) ──────────────────────────────────────────────────

_CTX_DOWN = "검색 트렌드(최근 6개월, 방향은 계산된 값이다): 가로수길 하락(26.3→21.4, -18.6%)"
_CTX_UP = "검색 트렌드(최근 6개월, 방향은 계산된 값이다): 가로수길 상승(21.4→26.3, +22.9%)"
_CTX_MIXED = _CTX_DOWN + "; 신사동 상승(60.0→70.0, +16.7%)"


def test_trend_contradiction_is_violation():
    """2026-08-01 실사고 문장 그대로 — 하락인데 유입 증가를 주장하면 위반."""
    parsed = _store(online=[LLMChannelPlan(
        channel="인스타그램",
        content="신사동을 찾는 발걸음이 다시 늘고 있는 요즘, 골목 카페 투어",
        rationale="유입 증가 흐름")])
    findings = ha_guard.check_store(parsed, _PROFILE, _CTX_DOWN)
    assert "trend_contradiction" in _codes(findings)
    assert ha_guard.has_violation(findings)


def test_standalone_surge_word_is_violation():
    """'붐비다'는 유입어와 짝지을 필요 없이 그 자체로 증가 주장이다."""
    parsed = _store(online=[LLMChannelPlan(
        channel="인스타그램", content="요즘 붐비는 골목", rationale="분위기 소구")])
    assert "trend_contradiction" in _codes(ha_guard.check_store(parsed, _PROFILE, _CTX_DOWN))


def test_growth_goal_is_not_a_claim():
    """'손님을 늘리는 전단'은 목표이지 유입이 늘고 있다는 주장이 아니다 (음성 대조).

    이걸 잡으면 정당한 오프라인 제안이 전부 죽는다 — 규칙을 주장 어미로 좁힌 이유다.
    """
    parsed = _store(offline=[LLMChannelPlan(
        channel="전단", content="손님을 늘리는 골목 안내 전단 배포",
        rationale="보행 동선에서 인지도를 높인다")])
    assert "trend_contradiction" not in _codes(
        ha_guard.check_store(parsed, _PROFILE, _CTX_DOWN))


def test_increase_claim_allowed_when_trend_rises():
    """트렌드가 상승이면 증가 서술은 근거가 있다 (음성 대조)."""
    parsed = _store(online=[LLMChannelPlan(
        channel="인스타그램", content="찾는 발걸음이 늘고 있는 골목",
        rationale="검색 트렌드 상승")])
    assert "trend_contradiction" not in _codes(
        ha_guard.check_store(parsed, _PROFILE, _CTX_UP))


def test_mixed_trend_does_not_block():
    """상승·하락이 섞이면 증가 서술이 정당할 수 있어 걸지 않는다 (음성 대조)."""
    parsed = _store(online=[LLMChannelPlan(
        channel="인스타그램", content="찾는 손님이 늘어나는 상권",
        rationale="일부 지표 상승")])
    assert "trend_contradiction" not in _codes(
        ha_guard.check_store(parsed, _PROFILE, _CTX_MIXED))


def test_no_context_means_no_trend_check():
    """컨텍스트가 없으면 방향 자체가 없다 — 판정하지 않는다 (음성 대조)."""
    parsed = _store(online=[LLMChannelPlan(
        channel="인스타그램", content="손님이 늘고 있는 골목", rationale="근거")])
    assert "trend_contradiction" not in _codes(ha_guard.check_store(parsed, _PROFILE, None))


# ── 최상급 (warning) ─────────────────────────────────────────────────────────

def test_unsupported_superlative_is_warning():
    parsed = _store(online=[LLMChannelPlan(
        channel="인스타그램", content="강남 최고의 이자카야", rationale="분위기")])
    findings = ha_guard.check_store(parsed, _PROFILE, None)
    assert "unsupported_superlative" in _codes(findings)
    assert not ha_guard.has_violation(findings), "최상급은 경고이지 폐기 사유가 아니다"


def test_superlative_in_input_is_exempt():
    """리뷰에 '최고'가 있으면 인용할 근거가 있다 (음성 대조)."""
    profile = {**_PROFILE, "reviews": [*_PROFILE["reviews"], "분위기 최고예요"]}
    parsed = _store(online=[LLMChannelPlan(
        channel="인스타그램", content="리뷰가 말하는 '분위기 최고'를 그대로 인용",
        rationale="리뷰 원문 인용")])
    assert "unsupported_superlative" not in _codes(ha_guard.check_store(parsed, profile, None))


def test_choedaehan_is_not_superlative():
    """'최대한'은 '최대'가 아니다 (음성 대조)."""
    parsed = _store(online=[LLMChannelPlan(
        channel="인스타그램", content="사진을 최대한 활용한 피드", rationale="시각 소구")])
    assert "unsupported_superlative" not in _codes(
        ha_guard.check_store(parsed, _PROFILE, None))


# ── 비방 (warning) ───────────────────────────────────────────────────────────

def test_disparagement_is_warning():
    parsed = _store(offline=[LLMChannelPlan(
        channel="전단", content="주변보다 저렴한 가격 강조", rationale="가격 경쟁")])
    findings = ha_guard.check_store(parsed, _PROFILE, None)
    assert "competitor_disparagement" in _codes(findings)
    assert not ha_guard.has_violation(findings)


def test_competitiveness_word_is_not_disparagement():
    """'경쟁력'은 비방이 아니다 (음성 대조)."""
    parsed = _store(offline=[LLMChannelPlan(
        channel="전단", content="메뉴 경쟁력을 살린 안내", rationale="강점 소구")])
    assert "competitor_disparagement" not in _codes(
        ha_guard.check_store(parsed, _PROFILE, None))


# ── 채널 편중 · 근거 (warning) ───────────────────────────────────────────────

def test_channel_concentration_is_warning():
    """온라인 제안이 전부 같은 계열이면 균형 원칙 위반이다."""
    parsed = _store(online=[
        LLMChannelPlan(channel="인스타그램 피드", content="a", rationale="근거를 충분히 적었다"),
        LLMChannelPlan(channel="인스타그램 릴스", content="b", rationale="근거를 충분히 적었다"),
    ])
    findings = ha_guard.check_store(parsed, _PROFILE, None)
    assert "channel_concentration" in _codes(findings)
    assert not ha_guard.has_violation(findings)


def test_mixed_channels_pass():
    """계열이 다르면 통과 (음성 대조)."""
    parsed = _store(online=[
        LLMChannelPlan(channel="인스타그램", content="a", rationale="근거를 충분히 적었다"),
        LLMChannelPlan(channel="네이버 블로그", content="b", rationale="근거를 충분히 적었다"),
    ])
    assert "channel_concentration" not in _codes(ha_guard.check_store(parsed, _PROFILE, None))


def test_single_online_plan_is_not_concentration():
    """1건뿐이면 편중을 논할 수 없다 (음성 대조)."""
    parsed = _store(online=[LLMChannelPlan(
        channel="인스타그램", content="a", rationale="근거를 충분히 적었다")])
    assert "channel_concentration" not in _codes(ha_guard.check_store(parsed, _PROFILE, None))


def test_missing_rationale_is_warning():
    parsed = _store(offline=[LLMChannelPlan(channel="전단", content="시식", rationale="응")])
    findings = ha_guard.check_store(parsed, _PROFILE, None)
    assert "missing_rationale" in _codes(findings)
    assert not ha_guard.has_violation(findings)


def test_clean_output_has_no_findings():
    """정상 생성물은 findings 가 0건이어야 한다 — 규칙이 늘 뭔가를 잡으면 쓸모가 없다."""
    parsed = _store(online=[
        LLMChannelPlan(channel="인스타그램", content="시그니처 메뉴를 담은 릴스 주 2회",
                       rationale="리뷰에 메뉴 언급이 반복된다"),
        LLMChannelPlan(channel="네이버 블로그", content="방문 후기형 포스팅",
                       rationale="지도 검색 유입 동선을 강화한다"),
    ])
    assert ha_guard.check_store(parsed, _PROFILE, _CTX_DOWN) == []


# ── 배선 (가게 단위) ─────────────────────────────────────────────────────────

def test_violation_falls_back_to_stub(monkeypatch):
    """허위가 확정되면 LLM 응답을 버리고 스텁으로 내려간다 — 정책의 핵심."""
    from app.core.config import settings
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    bad = _store(offline=[LLMChannelPlan(
        channel="전단", content="런치 세트 12,000원", rationale="점심 수요")])
    monkeypatch.setattr(mkt, "_call_llm", lambda profile, tone, ctx: bad)

    body = client.post(f"{V1}/marketing/generate", json=_PROFILE).json()
    assert body["source"] == "rule-stub", "위반인데 생성물이 그대로 나갔다"
    codes = {f["code"] for f in body["ha_findings"]}
    assert "fabricated_price" in codes, "폐기 사유가 응답에 없다 — 왜 스텁인지 알 수 없다"
    # 생성물의 문구가 새어나가면 안 된다
    assert "12,000원" not in str(body["online"]) + str(body["offline"])


def test_warning_keeps_llm_output(monkeypatch):
    """경고 등급은 응답을 살리고 밝히기만 한다."""
    from app.core.config import settings
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    warn = _store(online=[LLMChannelPlan(
        channel="인스타그램", content="강남 최고의 이자카야", rationale="분위기가 좋다는 리뷰")])
    monkeypatch.setattr(mkt, "_call_llm", lambda profile, tone, ctx: warn)

    body = client.post(f"{V1}/marketing/generate", json=_PROFILE).json()
    assert body["source"] == "llm", "경고인데 응답을 버렸다"
    assert {f["code"] for f in body["ha_findings"]} == {"unsupported_superlative"}


def test_stub_without_llm_has_empty_findings(monkeypatch):
    """키가 없어 스텁이 나온 경우와 폐기된 경우는 findings 로 구분된다."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "")
    body = client.post(f"{V1}/marketing/generate", json=_PROFILE).json()
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
