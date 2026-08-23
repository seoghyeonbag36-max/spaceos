"""테스트 공통 설정.

## 기본 스위트는 외부 API 를 치지 않는다

크레딧 충전(2026-08-01) 전까지 `LLM_API_KEY` 는 사실상 죽은 키였고, LLM 경로는 항상
폴백으로 흘러 테스트가 네트워크를 타지 않았다. 키가 살아나자 `/marketing/{id}` 를
호출하는 테스트들이 **실호출로 바뀌었다** — 매번 12~17초가 걸리고 크레딧이 나가며,
실제로 `test_postings_and_marketing` 이 응답을 기다리다 프로세스째 멎었다.

개별 테스트가 각자 `monkeypatch.setattr(settings, "llm_api_key", "")` 하는 방식은
빠뜨리기 쉽다(실제로 test_districts.py 가 빠뜨려 있었다). 그래서 여기서 전역으로 끈다.

실호출 검증은 `test_llm_live.py` 가 `SPACEOS_LIVE_LLM=1` opt-in 으로만 수행한다 —
그 경우 이 픽스처는 키를 건드리지 않는다.
"""
from __future__ import annotations

import os

import pytest

_LIVE = os.getenv("SPACEOS_LIVE_LLM") == "1"


@pytest.fixture(autouse=True)
def _no_network_llm(monkeypatch):
    """LLM 키를 비워 기본 스위트가 외부 API 를 치지 못하게 한다.

    테스트가 본문에서 다시 `llm_api_key` 를 세팅하는 것은 그대로 동작한다
    (autouse 픽스처가 먼저 돌고, 본문의 monkeypatch 가 나중에 덮어쓴다).
    """
    if _LIVE:
        return
    from app.core.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "", raising=False)


# ── 출력 계약 헬퍼 (2026-08-23) ──────────────────────────────────────────────
# 온라인(퍼포먼스)과 오프라인(상권활성화)은 대칭이 아니라 필요한 속성이 다르다
# (schemas/marketing.py::ChannelPlan). 테스트들이 검증하는 것은 대개 ha_guard 의
# **규칙**이지 계약 자체가 아니므로, 계약이 요구하는 필드는 여기서 기본값으로 채워
# 본문이 규칙에만 집중하게 한다. 계약 자체는 test_program_output_split.py 가 본다.

def _perf(channel, content, rationale, target="20~30대 직장인",
          budget_share=100, kpi="저장 수"):
    from app.schemas.marketing import LLMPerformancePlan
    return LLMPerformancePlan(channel=channel, content=content, rationale=rationale,
                              target=target, budget_share=budget_share, kpi=kpi)


def _act(channel, content, rationale, timing="주말 오전",
         actors=None, mode="own"):
    from app.schemas.marketing import LLMActivationPlan
    return LLMActivationPlan(channel=channel, content=content, rationale=rationale,
                             # `or` 를 쓰면 actors=[] 를 기본값이 덮어써서 "주체 없음"을
                             # 검증할 수 없다. None 만 기본값으로 친다.
                             timing=timing,
                             actors=["상인회"] if actors is None else actors, mode=mode)
