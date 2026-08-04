"""상권 행사가 생성 컨텍스트에 실리는지 (services/marketing._events_context).

## 왜 이 검사가 필요한가

행사 785건이 Gold 에 있는데 컨텍스트에 들어가지 않아, 오프라인 제안이 "상권
플리마켓/팝업 부스 참여" 같은 **어느 상권에나 해당하는 말**로 나왔다. 실데이터를
수집해 놓고 쓰지 않으면 수집하지 않은 것과 같다.

## 세 경우를 가르는 것이 요점이다

    None(Gold 미적재)   아무 말도 하지 않는다 — 모르는 것을 "없다"고 하면 안 된다
    [](예정 행사 없음)   **명시적으로 없다고 말하고 제안을 금지한다** — 침묵하면 LLM 이
                        일반론으로 행사를 지어낸다(고치려던 바로 그 증상)
    목록 있음            가까운 순 상위 N건 + **거리**

거리가 특히 중요하다. 이 API 는 공공·문화시설 행사 중심이라 가두 상권 커버리지가
낮아서, 가로수길 2건은 둘 다 800m 밖이다. 거리를 빼면 남의 동네 행사가 "우리 골목
행사"로 둔갑한다.
"""
from __future__ import annotations

import pytest

from app.services import marketing as mkt


def test_missing_gold_says_nothing():
    """Gold 미적재(None)면 침묵한다 — '행사 없음'은 모르는 것을 안다고 주장하는 것이다."""
    assert mkt._events_context(None) is None


def test_empty_events_forbid_fabrication(monkeypatch):
    """예정 행사가 0건이면 없다고 **말하고** 제안을 금지한다.

    빈 목록에 침묵하면 LLM 이 "플리마켓 참여"를 지어낸다 — 이 함수를 만든 이유다.
    """
    from app.services import events
    monkeypatch.setattr(events, "for_district", lambda d: [])

    ctx = mkt._events_context("hongdae-yeonnam")
    assert ctx and "없다" in ctx
    assert "제안하지 말 것" in ctx, "없다고만 하면 LLM 이 일반론으로 채운다"


def test_none_from_service_is_silent(monkeypatch):
    """서비스가 None(미적재)을 주면 컨텍스트에 행사 줄 자체가 없다."""
    from app.services import events
    monkeypatch.setattr(events, "for_district", lambda d: None)
    assert mkt._events_context("garosugil") is None


def test_events_carry_distance(monkeypatch):
    """거리를 반드시 싣는다 — 800m 밖 행사를 상권 안 행사로 쓰지 못하게."""
    from app.services import events
    monkeypatch.setattr(events, "for_district", lambda d: [
        {"n": "재즈 공연", "when": "2026-08-06~2026-08-20",
         "place": "재즈클럽그루브", "distance_m": 957},
    ])

    ctx = mkt._events_context("garosugil")
    assert "957m" in ctx
    assert "재즈 공연" in ctx and "재즈클럽그루브" in ctx


def test_nearest_events_first_and_capped(monkeypatch):
    """가까운 순 상위 N건만 — 도심 거점(ikseon 78건)이 컨텍스트를 잠식하면 안 된다."""
    from app.services import events
    rows = [{"n": f"행사{i}", "when": "2026-08-01~2026-08-31",
             "place": "장소", "distance_m": (20 - i) * 50} for i in range(20)]
    monkeypatch.setattr(events, "for_district", lambda d: rows)

    ctx = mkt._events_context("ikseon")
    assert ctx.count(";") == mkt._MAX_CONTEXT_EVENTS - 1, "행사 수 상한이 안 걸렸다"
    assert "행사19" in ctx, "가장 가까운 행사가 빠졌다"
    assert "행사0" not in ctx, "가장 먼 행사가 실렸다"


def test_missing_distance_does_not_crash(monkeypatch):
    """거리가 없는 행사(시드 잔재)도 죽지 않고 장소만 싣는다."""
    from app.services import events
    monkeypatch.setattr(events, "for_district", lambda d: [
        {"n": "행사", "when": "2026-08-01~2026-08-31", "place": "장소", "distance_m": None},
    ])
    ctx = mkt._events_context("garosugil")
    assert ctx and "장소" in ctx and "거점에서" not in ctx


def test_events_reach_district_context():
    """실제 Gold 에서도 행사 줄이 상권 컨텍스트에 합류한다 (통합)."""
    ctx = mkt._district_context("garosugil")
    if ctx is None:
        pytest.skip("gold/garosugil 미적재")
    assert "상권 행사" in ctx, "행사가 컨텍스트에 없다 — 오프라인 제안이 공허해진다"


def test_cache_key_covers_events_file():
    """캐시 키가 행사 Gold 의 mtime 을 포함한다.

    행사가 컨텍스트에 합류하면서 입력이 두 파일이 됐다. program_content_context 만
    보면 행사 파이프라인만 다시 돌린 경우 무효화가 안 돼 낡은 카피가 남는다.
    """
    from app.services import events

    if not events.is_available():
        pytest.skip("gold/platform_events.json 미적재")
    assert events.source_mtime() > 0
    # 행사 mtime 이 키에 섞여 있으므로, 컨텍스트 파일이 없는 거점이라도 0 이 아니다
    assert mkt._context_mtime("garosugil") >= events.source_mtime()


def test_event_fee_is_not_fabricated_price():
    """컨텍스트에 실린 금액을 인용한 것은 지어낸 가격이 아니다 (HA 검증기 연계).

    행사가 컨텍스트에 들어오면서 요금·기간의 숫자가 거기 실린다. 이걸 근거에서 빼면
    정상 인용이 violation 으로 폐기된다.
    """
    from app.schemas.marketing import LLMChannelPlan, LLMStoreMarketing
    from app.services import ha_guard

    ctx = "상권 행사(공공 문화행사 실데이터, 가까운 순): 재즈 공연(참가비 5,000원, 거점에서 957m)"
    parsed = LLMStoreMarketing(
        tone_keywords=["재즈"],
        online=[LLMChannelPlan(channel="인스타그램", content="공연 연계 게시",
                               rationale="인근 행사와 시간대를 맞춘다")],
        offline=[LLMChannelPlan(channel="입간판", content="참가비 5,000원 공연 안내 병기",
                                rationale="행사 관람객 동선을 잡는다")],
        ha_check="점검 통과")

    findings = ha_guard.check_store(parsed, {"name": "가게", "menu": [], "reviews": []}, ctx)
    assert "fabricated_price" not in {f.code for f in findings}
