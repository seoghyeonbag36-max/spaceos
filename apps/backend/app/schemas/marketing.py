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
    keywords: list[str] = []          # 사전 추출 키워드 (선택)


class ChannelPlan(BaseModel):
    channel: str                      # 예: 인스타그램, 네이버 블로그, 전단
    kind: str                         # online | offline
    content: str                      # 제안 문구/실행안
    rationale: str                    # 근거 (리뷰 키워드·상권 특성)


class StoreMarketing(BaseModel):
    store_name: str
    category: str
    tone_keywords: list[str]          # 리뷰·이미지에서 추출한 톤앤매너 키워드
    online: list[ChannelPlan]
    offline: list[ChannelPlan]
    ha_check: str                     # Humanistic Authority(균형·공생·공감) 검증 메모
    source: str                       # "llm" | "rule-stub"
