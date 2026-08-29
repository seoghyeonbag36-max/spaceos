"""가게 단위 마케팅 솔루션(Program) 스키마.

StoreProfile 은 수집 채널(네이버 지역검색·카카오 로컬·블로그 API·점주 제공)에
무관하게 정규화된 입력 계약이다. 플레이스 리뷰·사진은 공식 API가 없으므로
크롤링 산출물은 PoC 내부 검증 한정 — 상용은 점주 제공 데이터(동의) 원칙.
(docs/feature-program.md §0 검증 결과)
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator


class VenturePlan(BaseModel):
    """입력 계약 ③층 — 창업 계획(Venture). **기업이 직접 넣는 유일한 층이다.**

    ①자리·②상권은 우리가 가진 데이터에서 자동으로 나오지만, 아직 없는 가게의 강점과
    의도는 데이터에서 나올 수 없다(docs/feature-program.md §0-B). 그래서 이 층이
    **리뷰를 대신하는 근거의 원천**이고 HA 의 `allowed_text` 에 합류한다.

    ⚠ `strengths` 는 검증된 사실이 아니라 **기업의 주장**이다. 점주가 제공한 리뷰·메뉴와
    같은 등급으로 다루되(그래서 allowed_text 에 들어간다), 우리가 확인한 수치와
    같은 자리에 두지 않는다.
    """
    industry: str                          # 업종 — StoreProfile.category 보다 구체적일 수 있다
    target_customer: str                   # 목표 고객 (예: "30대 직장인 점심 수요")
    # 예산은 **구간**으로 받는다. 출력의 budget_share 는 int 퍼센트라 절대액이 구조적으로
    # 못 들어가고(§0-F), 실제 금액은 이 구간에서 파생한다 — "얼마를 쓸지는 기업 몫".
    budget_krw_min: int = Field(gt=0)      # 월 마케팅 예산 하한(원)
    budget_krw_max: int = Field(gt=0)      # 월 마케팅 예산 상한(원)
    open_date: str                         # 개업 예정일 YYYY-MM-DD
    strengths: list[str] = []              # 내세울 강점 — 기업 주장
    # Posting 3-Tier 시나리오와의 연결(premium/value/factory). 주면 그 전략의
    # 회수 가정과 어긋나는 제안을 사람이 대조할 수 있다.
    tier: str | None = None


class StoreProfile(BaseModel):
    name: str
    category: str                     # 예: 카페, 의류
    district_id: str | None = None    # 상권 컨텍스트 결합용 (선택)
    # 입력 계약 ①층(자리) — `gold/{거점}/vacant_units.json` 의 유닛 id.
    # 주면 그 공실의 면적·층·직전 업종·건물 공실률이 생성 근거에 합류한다
    # (services/program_site · docs/feature-program.md §0-B).
    # ⚠ 이 모델은 본래 **영업 중인 가게** 전제로 만들어졌다. 공실 대상 입력은
    # ③층(venture)까지 채워야 완성된다 — 그때 비로소 "아직 개업 전"이 추정이 아니라
    # **확정**이 되어 '방문 후기형 포스팅' 문제가 닫힌다(services/program_venture).
    unit_id: str | None = None
    # 입력 계약 ③층(창업계획). 공실 대상이면 이걸 채운다.
    venture: VenturePlan | None = None
    address: str | None = None
    reviews: list[str] = []           # 리뷰·블로그 텍스트 (공식 API 또는 점주 제공)
    image_urls: list[str] = []        # 상가 사진 (점주 제공 원칙) — vision 분석 입력
    menu: list[str] = []              # 메뉴 한 줄씩 ("대표메뉴 18,000원") — 지도 메뉴탭/점주 제공
    keywords: list[str] = []          # 사전 추출 키워드 (선택)


class CommercialStoreProfile(StoreProfile):
    """상용 온보딩용 점주 제공 입력.

    공개 데모의 ``StoreProfile`` 과 분리한다. 이 모델에 든 리뷰·사진·메뉴·키워드는
    **전부 점주 또는 그 권한을 받은 조직이 제공한 값**으로 취급하며, 공개 검색
    스니펫을 섞지 않는다. 상한은 API 오용으로 원문이 무제한 메모리에 올라오는 것을
    막는 운영 한계이지 데이터 값을 채우는 기본값이 아니다.
    """

    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=300)
    reviews: list[str] = Field(default_factory=list, max_length=100)
    image_urls: list[str] = Field(default_factory=list, max_length=4)
    menu: list[str] = Field(default_factory=list, max_length=100)
    keywords: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("reviews", "menu", "keywords")
    @classmethod
    def _bounded_text(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("빈 문자열은 입력 항목으로 셀 수 없습니다")
        if any(len(value) > 1000 for value in values):
            raise ValueError("입력 항목 한 건은 1000자를 넘을 수 없습니다")
        return values

    @field_validator("image_urls")
    @classmethod
    def _public_http_images(cls, values: list[str]) -> list[str]:
        if any(not value.startswith(("https://", "http://")) for value in values):
            raise ValueError("사진은 공개 접근 가능한 http/https URL이어야 합니다")
        return values


class ProgramCommercialConsent(BaseModel):
    """점주 제공 원문을 처리하기 위한 명시적 상용 계약.

    bool 기본값을 두지 않고 ``Literal[True]`` 로 받는다. 체크박스를 렌더링만 하고
    요청에서 빼먹거나, 프론트가 임의로 동의한 것으로 채우면 422로 실패한다.
    """

    contract_version: Literal["spaceos.program-onboarding/1"]
    data_origin: Literal["merchant-provided"]
    processing_purpose: Literal["program-marketing-generation"]
    consent_to_process: Literal[True]
    rights_confirmed: Literal[True]
    allow_external_model_processing: Literal[True]
    raw_input_retention: Literal["request-only"]


class ProgramCommercialOnboardingRequest(BaseModel):
    profile: CommercialStoreProfile
    consent: ProgramCommercialConsent

    @model_validator(mode="after")
    def _requires_merchant_content(self) -> Self:
        p = self.profile
        if not any((p.reviews, p.image_urls, p.menu, p.keywords, p.venture)):
            raise ValueError(
                "상용 온보딩에는 리뷰·사진·메뉴·키워드·창업계획 중 하나가 필요합니다")
        return self


class StorePlace(BaseModel):
    """카카오 로컬 키워드 검색 후보 1건 — 반자동 채우기의 '어느 가게냐'를 확정하는 단위.

    상호만으로는 가게가 특정되지 않는다(같은 이름이 전국에 있다 — 2026-08-01 블로그
    코퍼스 오염의 원인이 정확히 이것이었다). 그래서 후보를 **사람이 고르게** 하고,
    고른 결과의 주소로 리뷰 질의를 좁힌다.
    """
    name: str
    category: str                     # 카카오 category_name 의 말단(예: 카페, 일식>이자카야)
    address: str | None = None        # 지번
    road_address: str | None = None
    phone: str | None = None
    lat: float | None = None
    lng: float | None = None
    place_url: str | None = None      # 카카오맵 상세 — 사람이 눈으로 확인하라고 준다
    distance_m: int | None = None     # 거점 중심 기준 (district_id 를 준 경우만)


class StorePlaceLookup(BaseModel):
    """GET /marketing/places 응답. `source` 가 "unavailable" 이면 키 미설정·조회 실패다."""
    query: str
    places: list[StorePlace]
    source: str                       # "kakao-local" | "unavailable"
    note: str | None = None


class StoreReviewLookup(BaseModel):
    """GET /marketing/reviews 응답.

    ⚠ 이건 **네이버 블로그 검색 스니펫**이지 플레이스 방문자 리뷰가 아니다(공식 API 없음).
    화면에도 그렇게 표기한다 — 방문자 리뷰라고 부르면 없는 근거를 주장하는 것이다.
    """
    query: str
    reviews: list[str]
    source: str                       # "naver-blog" | "unavailable"
    note: str | None = None


class HAFinding(BaseModel):
    """Humanistic Authority 후처리 검증 결과 1건 (services/ha_guard.py).

    `ha_check` 가 **LLM 의 자기신고**인 것과 달리 이건 서버가 입력과 대조해 낸 판정이다.

    - `severity == "violation"`: 입력 대조로 거짓이 확정된 것(지어낸 금액, 확정된 트렌드
      방향 역행). 이 findings 가 붙어 있고 `source` 가 `"llm"` 이 아니면 **LLM 응답이
      폐기되고 폴백으로 내려간 것**이다 — 키 미설정·호출 실패와 구분되는 상태다.
    - `severity == "warning"`: 사전 매칭이라 오탐이 섞인다. 응답은 살리고 밝히기만 한다.
    """
    severity: str                     # "violation" | "warning"
    code: str                         # fabricated_price | trend_contradiction | ...
    message: str                      # 사람이 읽을 판정 문장
    evidence: str | None = None       # 걸린 실제 문자열 (사람이 오탐인지 보게 한다)


class VacantSite(BaseModel):
    """입력 계약 ①층(자리) 1건 — `gold/{거점}/vacant_units.json` 의 공실 유닛.

    아직 아무도 장사하지 않는 자리라 리뷰·평점·매출 실적이 존재하지 않는다. 여기 있는
    것은 전부 건축물대장과 건물 마스터에서 온 **사실**이다(services/program_site).
    """
    id: str
    n: str | None = None              # 소재 표기(지번 + 건물 용도/명칭)
    lat: float | None = None
    lng: float | None = None
    area: int | None = None           # 평 — 건물 상업면적 ÷ 호실 수(호실당 평균)
    floor: str | None = None          # 상가정보 flrNo 매칭 전이라 1F 가정
    was: str | None = None            # 직전 업종
    capacity: int | None = None       # 건물 호실 수
    active: int | None = None         # 그중 영업 중
    vacancy_rate: float | None = None  # 건물 공실률(%)
    bld_floors: int | None = None
    com_area_m2: float | None = None


class VacantSiteList(BaseModel):
    """GET /marketing/sites 응답. `site_source == "unavailable"` 이면 Gold 미적재다.

    `site_note` 를 반드시 함께 노출한다 — 면적이 호실당 평균이고 층이 1F 가정이라는
    한계가 빠지면 그 위에 얹힌 제안이 실측처럼 읽힌다.
    """
    district_id: str
    sites: list[VacantSite]
    site_source: str
    site_note: str | None = None
    site_built_at: str | None = None


class ChannelPlan(BaseModel):
    """제안 1건. **온라인과 오프라인은 대칭이 아니다 — 주체가 다르다**(§0-B).

    온라인은 창업 기업이 **단독 실행**하는 퍼포먼스 마케팅이고, 오프라인은 기업 혼자
    할 수 없는 **상권 활성화**다(행사 785건 중 57%가 공공·준공공 주최). 그래서 필요한
    속성이 갈린다. 하나의 모델에 담되 `kind` 로 어느 쪽 필드가 유효한지 가른다 —
    프론트가 online/offline 두 목록을 같은 모양으로 받던 것을 깨지 않기 위해서다.

    ⚠ 2026-08-23 이전에는 아래 네 필드(channel·kind·content·rationale)뿐이라
    타겟·예산배분·협업주체를 담을 자리가 없었다. 그래서 오프라인 제안이 "누가
    함께하는지" 없이 나왔고, 그건 신규 창업자가 혼자 축제를 열라는 말이 된다.
    """
    channel: str                      # 온라인=채널명 / 오프라인=행사 형식(플리마켓·공동 프로모션)
    kind: str                         # online | offline
    content: str                      # 제안 문구/실행안
    rationale: str                    # 근거 (수치·상권 데이터. 리뷰가 아니어도 된다)

    # ── 온라인(퍼포먼스) 전용 ─────────────────────────────────────────
    target: str | None = None         # 목표 고객 세그먼트 (TRDAR 연령·성별·시간대에서)
    # 예산 **배분 비율(%)**. 절대액을 담지 않는 것이 핵심이다 — "얼마를 쓸지는 기업 몫"
    # 이라는 §0-B 원칙 2 를, 값을 int 퍼센트로 못 박아 **구조적으로** 강제한다.
    # 문자열이면 LLM 이 "월 30만원" 을 넣을 수 있지만 int 에는 넣을 수 없다.
    budget_share: int | None = None
    kpi: str | None = None            # 목표 지표 (도달·저장·방문 전환 등)

    # ── 오프라인(상권활성화) 전용 ─────────────────────────────────────
    timing: str | None = None         # 시기 — 빈 시간대(TRDAR 격차)·계절
    actors: list[str] = []            # 협업 주체 (상인회·구청·건물주·인근 점포)
    # 오프라인 제안의 성격. 셋을 가르는 이유는 규칙이 서로 다르기 때문이다.
    #   cite    = 컨텍스트에 실린 **기존 행사** 연계 → 사실 주장이라 인용만 허용
    #   propose = **신규 공동 행사** 제안 → 계획이라 허용하되 빈 시간대 수치 인용을 강제
    #   own     = 매장 자체 접점(입간판·시식·외관) → 행사가 아니다. 협업 주체도 필수가 아니다
    # own 이 없으면 입간판 같은 평범한 제안이 '수치 없는 행사 제안'으로 잘못 걸린다
    # (2026-08-23 오탐 대조 테스트가 잡았다).
    mode: str | None = None


class LLMPerformancePlan(BaseModel):
    """LLM 구조화 출력 — 온라인(퍼포먼스). 창업 기업 단독 실행."""
    channel: str
    content: str
    rationale: str
    target: str
    budget_share: int                 # % — 온라인 제안들의 합이 100 이 되게 한다
    kpi: str


class LLMActivationPlan(BaseModel):
    """LLM 구조화 출력 — 오프라인(상권활성화). 기업 + 상권 주체 협업.

    `channel` 은 채널이 아니라 **형식**이다(플리마켓·공동 프로모션·야외 팝업).
    `mode` 가 이 출력의 안전장치다 — 기존 행사 인용과 신규 제안을 가르지 않으면
    지어낸 행사가 사실처럼 나간다(2026-08-06 에 금지 조항으로 막아 둔 것).
    """
    channel: str
    content: str
    rationale: str
    timing: str
    actors: list[str]
    mode: str                         # "cite" | "propose" | "own" — ChannelPlan 주석 참조


class LLMStoreMarketing(BaseModel):
    """LLM 구조화 출력 계약 — generate_store_marketing 의 llm 경로 응답 스키마."""
    tone_keywords: list[str]
    online: list[LLMPerformancePlan]
    offline: list[LLMActivationPlan]
    ha_check: str                     # 균형·공생·공감 자체 점검 결과 서술


# 상권 단위 응답 모델(GET /marketing/{id})은 여기가 아니라 `schemas/district.py::Marketing`
# 이다. 예전에 이 파일에도 같은 뜻의 `DistrictMarketing` 이 있었지만 라우터가 쓰지 않는
# 죽은 사본이었고, 2026-08-06 실제로 이걸 고치고 응답이 안 바뀌어 한 번 헛짚었다. 지웠다.


class LLMDistrictContents(BaseModel):
    """LLM 구조화 출력 계약 — 상권 단위 온라인 콘텐츠(Program 2단계).

    online_contents 는 프론트가 그대로 노출하는 한 줄 카피(해시태그 포함) 목록이다.
    """
    online_contents: list[str]
    ha_check: str


class StoreMarketing(BaseModel):
    store_name: str
    category: str
    tone_keywords: list[str]          # 리뷰·이미지에서 추출한 톤앤매너 키워드
    online: list[ChannelPlan]
    offline: list[ChannelPlan]
    ha_check: str                     # LLM 자기신고 — 이것만으로는 검증이 아니다
    source: str                       # "llm" | "rule-stub"
    ha_findings: list[HAFinding] = []  # 서버 후처리 검증 결과 (ha_check 와 다르다)


class ProgramCommercialOnboardingResponse(BaseModel):
    """조직별 동의 영수증 + 생성 결과. 점주 제공 원문은 응답에도 되돌려주지 않는다."""

    onboarding_id: str
    org_id: str
    accepted_at: datetime
    contract_version: Literal["spaceos.program-onboarding/1"]
    input_source: Literal["merchant-provided"]
    raw_input_persisted: Literal[False]
    marketing: StoreMarketing
