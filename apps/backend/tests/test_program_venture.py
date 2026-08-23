"""Program 입력 계약 ③층 — 창업 계획(Venture) (2026-08-23).

## 이 스위트가 붙드는 것

§0-B 가 정의한 3층 입력의 마지막 층이다. ①자리·②상권과 달리 **기업이 넣는** 층이라
수집이 아니라 계약·검증 과제다. 붙드는 것은 셋:

1. **'개업 전'이 추정에서 확정으로 바뀐다.** 08-23 오전까지는 `reviews 가 비었는가` 로
   추정했고, 그러면 리뷰를 아직 못 모은 영업 중인 가게가 개업 전으로 오인된다.
2. **개업 전 방문 전제는 위반이다.** '방문 후기형 포스팅' 증상의 근본 해소 지점.
3. **③층을 안 준 요청은 아무것도 달라지지 않는다.** 모르는 것을 위반으로 만들면
   기존 요청이 전부 깨진다 — None 과 False 를 가르는 이유.
"""
from __future__ import annotations

import datetime as dt

from app.schemas.marketing import LLMPerformancePlan, LLMStoreMarketing
from app.services import ha_guard
from app.services import program_venture as V

_TODAY = dt.date(2026, 8, 23)

_VENTURE = {
    "industry": "베이커리",
    "target_customer": "30대 직장인 아침 수요",
    "budget_krw_min": 2_000_000,
    "budget_krw_max": 3_000_000,
    "open_date": "2026-12-01",
    "strengths": ["천연발효종 직접 배양", "매장 내 제빵"],
    "tier": "value",
}


# ── 개업 전 판정: 모른다 / 그렇다 / 아니다 세 갈래 ──────────────────────────

def test_pre_open_is_tri_state():
    """③층이 없으면 None 이다. False 로 뭉뚱그리면 검사가 조용히 꺼진다."""
    assert V.is_pre_open(None) is None
    assert V.is_pre_open({}) is None
    assert V.is_pre_open({"open_date": "not-a-date"}) is None
    assert V.is_pre_open({"open_date": "2026-12-01"}, _TODAY) is True
    assert V.is_pre_open({"open_date": "2026-01-05"}, _TODAY) is False


def test_open_date_today_counts_as_open():
    """개업 당일은 영업 중이다 — 경계에서 방문 제안이 막히면 개업일 판촉을 못 한다."""
    assert V.is_pre_open({"open_date": "2026-08-23"}, _TODAY) is False


def test_budget_band_is_normalised():
    assert V.budget_band(_VENTURE) == (2_000_000, 3_000_000)
    assert V.budget_band({"budget_krw_min": 500, "budget_krw_max": 100}) == (100, 500)
    assert V.budget_band({"budget_krw_min": 0, "budget_krw_max": 10}) is None
    assert V.budget_band(None) is None


# ── 컨텍스트는 사실 등급을 밝힌다 ───────────────────────────────────────────

def test_context_marks_strengths_as_claims_not_facts():
    """강점은 기업 주장이다. 우리가 관측한 수치와 같은 자리에 두면 근거가 오염된다."""
    ctx = V.venture_context(_VENTURE, _TODAY)
    assert "기업 주장" in ctx
    assert "천연발효종 직접 배양" in ctx


def test_context_warns_when_pre_open():
    ctx = V.venture_context(_VENTURE, _TODAY)
    assert "아직 문을 열지 않았다" in ctx
    open_ctx = V.venture_context({**_VENTURE, "open_date": "2026-01-05"}, _TODAY)
    assert "아직 문을 열지 않았다" not in open_ctx


def test_no_venture_means_no_context():
    assert V.venture_context(None) is None
    assert V.venture_context({}) is None


# ── 근본 해소: 개업 전 방문 전제는 위반이다 ────────────────────────────────

def _parsed(content: str) -> LLMStoreMarketing:
    return LLMStoreMarketing(
        tone_keywords=["담백"],
        online=[LLMPerformancePlan(channel="네이버 블로그", content=content,
                                   rationale="지역 검색 유입", target="지역 검색",
                                   budget_share=100, kpi="클릭")],
        offline=[],
        ha_check="확인함",
    )


def test_pre_open_visit_claim_is_a_violation():
    """'방문 후기형 포스팅' — §0-B 가 실측한 증상 그 자체가 이제 걸린다."""
    findings = ha_guard.check_store(
        _parsed("'○○' 방문 후기형 포스팅 + 지역 키워드 최적화"),
        {"name": "○○", "category": "베이커리", "venture": _VENTURE}, None)
    codes = [f.code for f in findings]
    assert "pre_open_visit_claim" in codes
    assert ha_guard.has_violation(findings)


def test_pre_open_check_is_off_without_venture():
    """③층을 안 준 기존 요청은 그대로 통과해야 한다 — 모르는 것은 위반이 아니다."""
    findings = ha_guard.check_store(
        _parsed("'○○' 방문 후기형 포스팅 + 지역 키워드 최적화"),
        {"name": "○○", "category": "베이커리"}, None)
    assert "pre_open_visit_claim" not in [f.code for f in findings]


def test_open_store_may_talk_about_visits():
    """영업 중이면 방문·재방문은 정상이다. 개업 전일 때만 켜지는 검사다."""
    findings = ha_guard.check_store(
        _parsed("단골 재방문 유도 포스팅"),
        {"name": "○○", "category": "베이커리",
         "venture": {**_VENTURE, "open_date": "2026-01-05"}}, None)
    assert "pre_open_visit_claim" not in [f.code for f in findings]


def test_budget_from_venture_is_not_a_fabricated_price():
    """기업이 준 예산을 인용한 문장이 '지어낸 금액'으로 폐기되면 안 된다."""
    findings = ha_guard.check_store(
        _parsed("월 2000000원 범위 안에서 채널을 배분한다"),
        {"name": "○○", "category": "베이커리",
         "venture": {**_VENTURE, "open_date": "2026-01-05"}}, None)
    assert "fabricated_price" not in [f.code for f in findings]


def test_strengths_are_usable_as_grounds():
    """③층 강점은 리뷰를 대신하는 근거의 원천이다 — 최상급 검사에 걸리지 않아야 한다."""
    assert "천연발효종" in V.strengths_text(_VENTURE)
    assert V.strengths_text(None) == ""


# ── 스텁도 ③층을 쓴다 ──────────────────────────────────────────────────────

def test_stub_uses_venture_for_target_and_rationale(monkeypatch):
    from app.core.config import settings
    from app.services import marketing as mkt
    monkeypatch.setattr(settings, "llm_api_key", None)
    out = mkt.generate_store_marketing(
        {"name": "○○", "category": "베이커리", "venture": _VENTURE})
    online = out["online"][0]
    assert online["target"] == _VENTURE["target_customer"]
    assert "기업이 제출한 강점" in online["rationale"]
    # 개업 전이 확정이므로 스텁 문구에도 방문 전제가 없어야 한다.
    joined = " ".join(f"{p['content']} {p['rationale']}" for p in out["online"])
    assert not any(w in joined for w in V.PRE_OPEN_FORBIDDEN)


def test_stub_pre_open_is_confirmed_not_guessed(monkeypatch):
    """리뷰가 있어도 개업 전이면 개업 전이다 — 추정이 확정을 이기면 안 된다."""
    from app.core.config import settings
    from app.services import marketing as mkt
    monkeypatch.setattr(settings, "llm_api_key", None)
    out = mkt.generate_store_marketing({
        "name": "○○", "category": "베이커리",
        "reviews": ["빵이 맛있어요"],          # 리뷰가 있으니 예전 규칙이면 '영업 중'
        "venture": _VENTURE,                    # 그러나 개업일은 미래다
    })
    joined = " ".join(f"{p['content']} {p['rationale']}" for p in out["online"])
    assert not any(w in joined for w in V.PRE_OPEN_FORBIDDEN)
