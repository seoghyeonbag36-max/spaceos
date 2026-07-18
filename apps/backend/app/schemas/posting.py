"""입점 시뮬레이션(Posting) 요청/결과 스키마.

외부 AI 창업 코파일럿(services/posting.py 어댑터)과 내부 3-Tier 폴백이
모두 이 스키마로 정규화되어 FE·리포트가 공급자에 독립적으로 동작한다.
"""
from __future__ import annotations

from pydantic import BaseModel

from app.schemas.district import TierScenario


class SimulateRequest(BaseModel):
    district_id: str
    unit_id: str | None = None       # 거점 내 공실 유닛 (없으면 대표 유닛)
    industry_type: str | None = None  # GNN 업종 추천(Platform) 결과를 전달 가능
    strategy: str | None = None       # premium | value | factory (없으면 3전략 비교)


class SimulateResult(BaseModel):
    district_id: str
    unit_id: str
    industry_type: str | None
    scenarios: dict[str, TierScenario]
    source: str  # "copilot" | "fallback-3tier"
