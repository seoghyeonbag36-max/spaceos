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
    # 권리금(만원) — **기업이 넣는다**. 공개 통계가 없어(bronze 전수 확인) 수집으로는
    # 못 채우고, 실제로도 임대인·기존 임차인과의 협상값이라 그 기업만 안다.
    # Program 입력 계약 ③층(창업계획)과 같은 성격이다: 수집 과제가 아니라 계약 과제.
    # 안 주면 0 을 전제로 계산하고 `inputs_source["prem"]="absent"` 로 밝힌다.
    # 실측 감도(270유닛 전수): 추천 5.2% 뒤집힘 · roi 중앙 1.6개월(p90 15.5) ·
    # 회수가부 판정은 0건 변화. → docs/feature-posting.md §0-K
    prem: int | None = None


class SimulateResult(BaseModel):
    district_id: str
    unit_id: str
    industry_type: str | None
    scenarios: dict[str, TierScenario]
    source: str  # "copilot" | "fallback-3tier"
    # 폴백으로 떨어진 **이유**. 코파일럿 미설정이면 None(폴백이 정상 동작이다),
    # 설정돼 있는데 실패했으면 계약 위반·연결 실패 사유가 들어간다.
    # 이 둘을 구분하지 않으면 코파일럿이 죽어 있어도 화면이 똑같아 아무도 모른다.
    source_note: str | None = None
    # 시나리오를 만든 입력의 **필드별** 출처: area/rent/prem/foot →
    #   "rone"(R-ONE 임대료) | "flpop"(서울 상권분석 유동인구) | "seed"(손으로 적은 프록시)
    # source 가 코파일럿이냐 폴백이냐와 별개로, 입력이 실측인지 프록시인지를 밝힌다.
    inputs_source: dict[str, str] | None = None
    inputs_quarter: str | None = None   # 실데이터 기준 분기 (예: "20261")
    # 세 전략 모두 회수 불가일 때만 채워진다 — "추천이 없다"와 "이 자리는 회수가
    # 안 된다"를 구분한다. 예전에는 둘 다 빈 값으로 조용히 같아 보였다.
    unviable_note: str | None = None
