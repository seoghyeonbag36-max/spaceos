"""입점 솔루션(Posting) 서비스 — 외부 AI 창업 코파일럿 어댑터.

2026-07-18 개정: 외부에서 만든 AI 창업 코파일럿 프로그램을 연동해 적용한다.
- settings.posting_copilot_url 설정 시 외부 코파일럿 호출 → SimulateResult 로 정규화
- 미설정·호출 실패 시 내부 3-Tier(고급화/가성비/기능중심) 계산으로 폴백

2026-08-01: 코파일럿 명세가 아직 없어 실제로는 항상 폴백이 돈다. 그래서 **폴백의
입력**을 실데이터로 올렸다 — 유닛의 rent 는 R-ONE 임대료, foot 은 서울 상권분석
유동인구에서 온다(services/posting_inputs). area·prem 은 실데이터 소스가 없어
시드 프록시를 유지하며, 응답의 `inputs_source` 가 필드별 출처를 밝힌다.

외부 코파일럿의 연동 형태(REST/패키지)에 대한 가정은 이 모듈 밖으로 내보내지 않는다.
"""
from __future__ import annotations

from app.core.config import settings
from app.services import districts as svc
from app.services import posting_inputs


def _call_copilot(unit: dict, industry_type: str | None) -> dict | None:
    """외부 AI 창업 코파일럿 호출 → 시나리오 dict 반환.

    TODO: 실제 연동 — 코파일럿 입출력 명세 확정 후 구현.
      예상 형태: POST {settings.posting_copilot_url}/simulate
                 headers={"Authorization": settings.posting_copilot_key}
                 body={면적, 임대료, 권리금, 업종, 유동인구 등급}
      응답 필드를 TierScenario(invest_mn/month_cost/month_rev/roi_months)로 매핑하고
      단위(만원/월)를 검증할 것. 매핑 불가 필드는 폴백으로 처리.
    """
    if not settings.posting_copilot_url:
        return None
    return None  # TODO: 실제 연동 전까지 항상 폴백


def simulate(district_id: str, unit_id: str | None = None,
             industry_type: str | None = None, strategy: str | None = None) -> dict | None:
    """공실 유닛의 입점 시뮬레이션. 코파일럿 우선, 실패 시 3-Tier 폴백.

    strategy(premium/value/factory) 지정 시 해당 전략만, 미지정 시 3전략 비교 반환.
    반환: SimulateResult 스키마 dict. 거점/유닛을 찾지 못하면 None.
    """
    units = svc.resolved_units(district_id)
    if not units:
        return None
    unit = next((u for u in units if u["id"] == unit_id), units[0])

    scenarios = _call_copilot(unit, industry_type)
    source = "copilot"
    if scenarios is None:
        scenarios = svc.tier_scenarios(unit)
        source = "fallback-3tier"
    # 전략 필터 **전에** 판정한다 — 한 전략만 뽑고 나서 보면 "그 전략이 안 된다"와
    # "이 자리가 안 된다"가 뒤섞인다.
    note = svc.unviable_note(scenarios)
    if strategy in scenarios:
        scenarios = {strategy: scenarios[strategy]}
    return {
        "district_id": district_id,
        "unit_id": unit["id"],
        "industry_type": industry_type,
        "scenarios": scenarios,
        "source": source,
        # 시나리오를 만든 입력의 필드별 출처 — 프록시를 실측으로 오독하면 안 된다
        "inputs_source": unit.get("inputs_source"),
        "inputs_quarter": posting_inputs.quarter(),
        "unviable_note": note,
    }
