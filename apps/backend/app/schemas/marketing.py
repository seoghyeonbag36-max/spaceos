"""가게 단위 마케팅 솔루션(Program) 스키마.

StoreProfile 은 수집 채널(네이버 지역검색·카카오 로컬·블로그 API·점주 제공)에
무관하게 정규화된 입력 계약이다. 플레이스 리뷰·사진은 공식 API가 없으므로
크롤링 산출물은 PoC 내부 검증 한정 — 상용은 점주 제공 데이터(동의) 원칙.
(docs/feature-program.md §0 검증 결과)
"""
from __future__ import annotations

from pydantic import BaseModel


class StoreProfile(BaseModel):
    name: str
    category: str                     # 예: 카페, 의류
    district_id: str | None = None    # 상권 컨텍스트 결합용 (선택)
    address: str | None = None
    reviews: list[str] = []           # 리뷰·블로그 텍스트 (공식 API 또는 점주 제공)
    image_urls: list[str] = []        # 상가 사진 (점주 제공 원칙) — vision 분석 입력
    menu: list[str] = []              # 메뉴 한 줄씩 ("대표메뉴 18,000원") — 지도 메뉴탭/점주 제공
    keywords: list[str] = []          # 사전 추출 키워드 (선택)


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


class ChannelPlan(BaseModel):
    channel: str                      # 예: 인스타그램, 네이버 블로그, 전단
    kind: str                         # online | offline
    content: str                      # 제안 문구/실행안
    rationale: str                    # 근거 (리뷰 키워드·상권 특성)


class LLMChannelPlan(BaseModel):
    """LLM 구조화 출력용 채널 플랜 (kind 는 서버가 부여)."""
    channel: str
    content: str
    rationale: str


class LLMStoreMarketing(BaseModel):
    """LLM 구조화 출력 계약 — generate_store_marketing 의 llm 경로 응답 스키마."""
    tone_keywords: list[str]
    online: list[LLMChannelPlan]
    offline: list[LLMChannelPlan]
    ha_check: str                     # 균형·공생·공감 자체 점검 결과 서술


# 상권 단위 응답 모델(GET /marketing/{id})은 여기가 아니라 `schemas/district.py::Marketing`
# 이다. 예전에 이 파일에도 같은 뜻의 `DistrictMarketing` 이 있었지만 라우터가 쓰지 않는
# 죽은 사본이었고, 2026-08-04 실제로 이걸 고치고 응답이 안 바뀌어 한 번 헛짚었다. 지웠다.


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
