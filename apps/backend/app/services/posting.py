"""입점 솔루션(Posting) 서비스 — 외부 AI 창업 코파일럿 어댑터.

2026-07-18 개정: 외부에서 만든 AI 창업 코파일럿 프로그램을 연동해 적용한다.
- settings.posting_copilot_url 설정 시 외부 코파일럿 호출 → SimulateResult 로 정규화
- 미설정·호출 실패 시 내부 3-Tier(고급화/가성비/기능중심) 계산으로 폴백

2026-08-01: 코파일럿 명세가 아직 없어 실제로는 항상 폴백이 돈다. 그래서 **폴백의
입력**을 실데이터로 올렸다 — 유닛의 rent 는 R-ONE 임대료, foot 은 서울 상권분석
유동인구에서 온다(services/posting_inputs). area·prem 은 실데이터 소스가 없어
시드 프록시를 유지하며, 응답의 `inputs_source` 가 필드별 출처를 밝힌다.

2026-08-23: **명세를 기다리는 것을 그만두고 우리가 발행했다.** 공급자가 미정이라
기다리는 한 이 자리는 영원히 비어 있었다(07-18 이후 0%). 계약 `spaceos.posting/1` 은
services/posting_copilot 에 있고, 어댑터는 그에 맞춰 오늘 구현·검증됐다. 공급자가
정해지면 `POSTING_COPILOT_URL` 만 채우면 된다.

외부 코파일럿의 연동 형태(REST/패키지)에 대한 가정은 이 모듈 밖으로 내보내지 않는다.
"""
from __future__ import annotations

from app.core.config import settings
from app.services import districts as svc
from app.services import posting_copilot
from app.services import posting_inputs


def _call_copilot(district_id: str, unit: dict,
                  industry_type: str | None) -> tuple[dict | None, str | None]:
    """외부 AI 창업 코파일럿 호출 → (시나리오, 실패사유).

    반환은 셋 중 하나다. **"안 붙였다"와 "붙였는데 실패했다"를 섞지 않는다** —
    예전에는 둘 다 그냥 폴백이라 화면에서 구분되지 않았고, 코파일럿이 죽어 있어도
    아무도 몰랐다(unviable_note 가 고쳤던 것과 같은 실패 양식이다).

      (None, None)      코파일럿 미설정 — 폴백이 정상 동작이다
      (None, "사유")     설정돼 있는데 실패 — 폴백이되 사유를 화면까지 올린다
      ({...}, None)     정상

    계약은 services/posting_copilot (spaceos.posting/1). 예외를 넓게 받는 이유는
    외부 공급자의 실패로 우리 API 가 5xx 를 내면 안 되기 때문이다 — 어떤 실패든
    폴백으로 같은 스키마를 돌려주는 것이 이 어댑터의 계약이다.
    """
    if not settings.posting_copilot_url:
        return None, None
    try:
        payload = posting_copilot.fetch(district_id, unit, industry_type)
        return posting_copilot.normalize(payload, svc.TIER), None
    except posting_copilot.ContractError as exc:
        return None, str(exc)
    except Exception as exc:  # noqa: BLE001 — 외부 장애가 우리 5xx 가 되면 안 된다
        return None, f"코파일럿 호출 중 예외: {type(exc).__name__}: {exc}"


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

    scenarios, fail = _call_copilot(district_id, unit, industry_type)
    source = "copilot"
    source_note = None
    if scenarios is None:
        scenarios = svc.tier_scenarios(unit)
        source = "fallback-3tier"
        source_note = fail
    else:
        # 추천은 **우리가** 계산한다 — 기준(회수 최단)이 제품 정의라 공급자가 못 바꾼다.
        # 반올림 전 `_raw` 로 고르고 표시만 반올림하는 것도 폴백과 동일하게 맞춘다.
        best = svc.recommend_tier(scenarios)
        for k, s in scenarios.items():
            s["recommended"] = k == best
            s.pop("_raw", None)
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
        # 폴백으로 떨어진 **이유**. 미설정이면 None, 호출 실패면 사유가 들어간다.
        "source_note": source_note,
        # 시나리오를 만든 입력의 필드별 출처 — 프록시를 실측으로 오독하면 안 된다
        "inputs_source": unit.get("inputs_source"),
        "inputs_quarter": posting_inputs.quarter(),
        "unviable_note": note,
    }
