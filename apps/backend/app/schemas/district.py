"""거점(commercial district) 응답 스키마."""
from __future__ import annotations

from pydantic import BaseModel

from app.schemas.marketing import HAFinding


class DistrictSummary(BaseModel):
    id: str
    name: str
    gu: str
    type: str
    center: list[float]
    note: str
    rec_top: str
    sentiment: float
    reviews: int
    risk_zones: int
    vacancy_rate: float
    vacant_units: int
    cell_count: int
    store_count: int
    tier_mix: dict[str, int]
    # 공실 수치의 출처 — "gold"(Gold 실측 건물 집계) | "synthetic"(합성 그리드 폴백).
    # 합성값을 실측처럼 읽으면 안 되므로 항상 함께 내려보낸다.
    vacancy_source: str = "synthetic"
    # Gold 경로에서만 채워진다 — 집계에 쓰인 건물 수, 전체 대비 비율(%).
    building_count: int | None = None
    precision_pct: float | None = None
    # 앵커 대조 — 거점별 R-ONE 중대형상가 공실률과 그 격차(%p).
    # 모집단·단위가 달라(우리는 호실·전수, R-ONE 은 면적·표본) 격차 0 이 정상이 아니다.
    # 절대값이 아니라 거점 간 비교·추세 감시에 쓴다.
    anchor_pct: float | None = None
    anchor_gap_pp: float | None = None
    # Platform·LSTM 다음 분기 예측 (forecast json 부재 시 None)
    predicted_rate: float | None = None
    predicted_delta: float | None = None
    predicted_direction: str | None = None


class Zone(BaseModel):
    id: str
    n: str
    grp: str
    lat: float
    lng: float
    s: float
    d: float
    r: int
    f: list[list[str]]


class Cell(BaseModel):
    i: int
    j: int
    lat: float
    lng: float
    c_lat: float
    c_lng: float
    v: float
    stores: int
    vac_n: int
    dlat: float
    dlng: float
    # Gold 경로에서만 — 셀의 총 호실 수(공실률 분모)와 집계된 건물 수.
    capacity: int | None = None
    buildings: int | None = None


class VacancyHeatmap(BaseModel):
    district_id: str
    resolution_m: int
    cells: list[Cell]
    sum_stores: int
    sum_vac: int
    avg_vacancy: float
    # "gold"(실측 건물 집계) | "synthetic"(합성 그리드 폴백) — DistrictSummary 와 동일 의미
    vacancy_source: str = "synthetic"
    # Gold 경로에서만 — 총 호실 수, 집계·전체 **지번** 수, 정밀 표본 비율(%),
    # 집합건물로 제외된 건물 수. buildings < buildings_total 인 이유는 제외 규칙 3종
    # (floor_approx · expos_units · polygon_only) — services/gold_vacancy 모듈 주석 참조.
    #
    # ⚠ buildings·buildings_total 의 단위는 폴리곤이 아니라 **지번(대지)** 이다.
    # 한 지번에 여러 동이 올라가면 각 폴리곤이 지번 전체의 active·capacity 를 물려받아
    # 그대로 세면 그 지번이 폴리곤 수만큼 가중된다(가락시장: 지번 1개 = 폴리곤 225개).
    # 지도에 그리는 폴리곤 총수는 polygons_total 로 따로 본다.
    capacity: int | None = None
    buildings: int | None = None
    buildings_total: int | None = None
    polygons_total: int | None = None
    precision_pct: float | None = None
    excluded_mall: int | None = None
    # 앵커 대조 — 거점별 R-ONE 중대형상가 공실률과 격차(%p). DistrictSummary 와 동일 의미.
    anchor_pct: float | None = None
    anchor_gap_pp: float | None = None
    # Platform·LSTM 다음 분기 예측 (거점 단위, forecast json 부재 시 None)
    predicted_rate: float | None = None
    predicted_delta: float | None = None
    predicted_direction: str | None = None


class TierScenario(BaseModel):
    tier: str
    name: str
    sub: str
    invest_mn: int
    month_cost: int
    month_rev: int
    month_net: int
    roi_months: float
    recommended: bool
    # 순익이 0 이하면 False — 회수 자체가 성립하지 않는다. roi_months 의 99.0 은
    # "매우 김"이 아니라 "불가"의 표식이었는데 구분이 안 됐다.
    viable: bool = True
    # 이 회수기간이 **어떤 비용 항목까지** 넣고 계산됐는지. services/districts.COST_BASIS.
    basis: str | None = None


class Posting(BaseModel):
    id: str
    n: str
    grp: str
    lat: float
    lng: float
    area: int
    rent: int
    prem: int
    floor: str
    was: str
    rec: str
    foot: str
    # 필드별 입력 출처: "rone" | "flpop" | "seed" — services/posting_inputs 참조.
    # rent·foot 은 실데이터, area·prem 은 소스가 없어 시드 프록시로 남아 있다.
    inputs_source: dict[str, str] | None = None
    persona: str
    note: str
    scenarios: dict[str, TierScenario]


class MarketingEvent(BaseModel):
    """상권 행사. 실데이터(서울 문화행사)와 시드가 같은 스키마로 흐른다.

    실데이터로 넘어오면서 시드의 `k2`(효과 지표 "유입 +52%")·`roles`·`ha` 는
    선택 필드가 됐다 — 셋 다 근거 없이 적은 값이라 실데이터에는 없다.
    실데이터 전용 필드(place/org/fee/…)도 시드에는 없으므로 선택이다.
    """
    id: str
    n: str
    lat: float
    lng: float
    ic: str
    when: str
    # ── 시드에만 있는 필드(근거 없는 값이라 실데이터로 승계하지 않음) ──
    k2: str | None = None
    desc: str | None = None
    roles: list[str] | None = None
    ha: str | None = None
    # ── 실데이터에만 있는 필드 ──
    category: str | None = None
    place: str | None = None
    org: str | None = None
    fee: str | None = None
    target: str | None = None
    link: str | None = None
    distance_m: int | None = None


class Marketing(BaseModel):
    district_id: str
    events: list[MarketingEvent]
    online_contents: list[str]
    # 행사 출처: "seoul-open-data"(실데이터) | "seed"(Gold 미적재 폴백).
    # 실데이터인데 목록이 비어 있으면 그 거점에 예정 공공 문화행사가 없다는 뜻이다.
    events_source: str = "seed"
    # 온라인 콘텐츠의 출처 — "llm"(Gold 컨텍스트 기반 생성) | "seed"(시드 폴백).
    # 기본값을 둬 기존 소비자(프론트·테스트)와 호환된다.
    source: str = "seed"
    # HA 후처리 검증 결과(services/ha_guard.py). violation 이 있는데 source 가 "seed" 면
    # **LLM 이 생성은 했으나 검증에 걸려 폐기된 것**이다 — 키 미설정·Gold 미적재와 다르다.
    ha_findings: list[HAFinding] = []
