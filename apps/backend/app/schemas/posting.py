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
    # 시나리오를 만든 입력의 **필드별** 출처: area/rent/prem/foot →
    #   "rone"(R-ONE 임대료) | "flpop"(서울 상권분석 유동인구) | "seed"(손으로 적은 프록시)
    # source 가 코파일럿이냐 폴백이냐와 별개로, 입력이 실측인지 프록시인지를 밝힌다.
    inputs_source: dict[str, str] | None = None
    inputs_quarter: str | None = None   # 실데이터 기준 분기 (예: "20261")
    # 세 전략 모두 회수 불가일 때만 채워진다 — "추천이 없다"와 "이 자리는 회수가
    # 안 된다"를 구분한다. 예전에는 둘 다 빈 값으로 조용히 같아 보였다.
    unviable_note: str | None = None
