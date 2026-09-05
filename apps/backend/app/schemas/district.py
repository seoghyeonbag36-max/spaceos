"""거점(commercial district) 응답 스키마."""
from __future__ import annotations

from pydantic import BaseModel

from app.schemas.marketing import HAFinding


class DistrictSummary(BaseModel):
    id: str
    name: str
    gu: str
    # 도시 — 54거점이 전부 서울이던 동안은 암묵이었다(파일명이 곧 도시였다).
    # 고양·파주가 같은 목록에 섞이면 프론트가 구분할 방법이 필요하다.
    # `city` 는 슬러그(seoul/goyang/paju), `city_name` 은 화면 표기(서울/고양/파주).
    city: str = "seoul"
    city_name: str = "서울"
    type: str
    center: list[float]
    note: str
    rec_top: str
    # 감성구역 시드가 없는 실측 거점은 **null** 이다. 0 이 아니다 —
    # 0 은 "쟀더니 0", null 은 "재지 않았다". 화면은 이 둘을 다르게 그려야 한다.
    sentiment: float | None = None
    reviews: int | None = None
    risk_zones: int | None = None
    # 시드 없이 Gold 만으로 서는 거점(고양·파주). 화면이 빈 축을 밝히는 근거.
    measured_only: bool = False
    # 예외 표시 — 비어 있지 않으면 이 거점의 수치를 다른 거점과 **직접 비교하면 안 된다**.
    # 거점을 목록에서 빼는 대신 왜 다른지 밝힌 채로 싣기 위한 자리다(계획상가 밀집 등).
    caveat: str = ""
    # 공실 대표값 — **None 이 두 가지 뜻을 갖지 않게** 한다.
    #   vacancy_withheld=False + None  → 재지 않았다(Gold 미보유 등)
    #   vacancy_withheld=True  + None  → 쟀지만 거점을 대표하지 못해 **내렸다**
    # 후자는 계획상가 밀집 거점이다(app/data/hub_caveats). 화면이 둘을 다르게 그려야
    # 한다 — "실측 없음" 과 "대표값 미제공" 은 사용자에게 다른 말이다.
    vacancy_rate: float | None
    vacancy_withheld: bool = False
    # 대표 집계의 분모가 이 거점 상업 재고에서 차지하는 비율(%) — 호실 기준.
    # `precision_pct`(지번 기준)와 다른 것을 잰다: services/gold_vacancy 참조.
    # 이 값이 낮을수록 대표 공실률을 믿을 이유가 준다.
    inventory_coverage_pct: float | None = None
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
    """거점 안의 **행정동 단위 실측 구역**(2026-09-05 부터).

    종전에는 손으로 적은 감성 구역이었다. 지금은 `gold/{거점}/district_zones.json`
    에서 오고, 값의 성격이 둘로 갈린다:

    - **실측**: `stores`·`buildings`·`capacity`·`active`·`vacancy_rate`.
      공실률은 거점 대표값과 **같은 규칙**으로 세므로 합계가 맞는다.
    - **미측정**: `s`(감성)·`d`(증감)·`r`(리뷰수)·`f`(키워드)는 **null/빈 배열**이다.
      0 으로 채우면 "쟀더니 0"으로 읽힌다 — 좌표를 가진 점포 리뷰 채널이 없어서
      못 잰 것이다(docs/feature-platform.md §0-K).
    """
    id: str
    n: str                      # 행정동명 — 실측
    grp: str                    # 법정동명 — 실측
    lat: float
    lng: float
    # ── 실측 ────────────────────────────────────────────────────────────
    stores: int | None = None       # 그 행정동의 점포 수(소상공인 상가정보)
    buildings: int | None = None    # 대표 집계에 든 건물 수(지번 중복 제거 후)
    capacity: int | None = None     # 상업 호실 수 — 공실률 분모
    active: int | None = None       # 영업 호실 수 — 공실률 분자의 여집합
    vacancy_rate: float | None = None
    # ── 미측정 (감성) ───────────────────────────────────────────────────
    # None 이 정상이다. 화면이 "감성 실측 없음"으로 그린다.
    s: float | None = None
    d: float | None = None
    r: int | None = None
    f: list[list[str]] = []


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
    # 거점 평균 — DistrictSummary.vacancy_rate 와 같은 값이고 같은 이유로 None 이 된다.
    # 셀(`cells`)은 내리지 않는다: 셀 값은 그 셀 건물들의 실측이고, 내린 것은 그것들을
    # 거점 하나의 수로 뭉친 **대표값**이다.
    avg_vacancy: float | None
    vacancy_withheld: bool = False
    inventory_coverage_pct: float | None = None
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
    foot: str
    # 필드별 입력 출처 — services/posting_inputs 참조:
    #   "rone"(R-ONE 임대료) · "flpop"/"flpop+trdar"(상권 유동) ·
    #   "gold-ledger"(건축물대장 상업면적÷capacity) · "seed"(손으로 적은 프록시) ·
    #   "absent"(값이 없어 0 을 전제로 계산했다 — prem 이 그렇다)
    inputs_source: dict[str, str] | None = None
    # 아래 셋은 **시드에만 있던 서술 필드**다. 실 인벤토리(건축물대장 실측)에는 없어서
    # 2026-08-24 배선 때 선택 필드가 됐다. 지어내지 않고 비운 채 내보낸다 —
    # `rec` 은 이미 계산으로 대체됐고(services/districts.recommend_tier),
    # `persona`·`note` 는 근거 없이 적은 문구라 실측 자리에 얹으면 실측처럼 읽힌다.
    rec: str | None = None
    persona: str | None = None
    note: str | None = None
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
