"""마케팅 솔루션(Program) 생성 서비스 — 가게 단위 → 상권 단위.

2026-07-18 개정 2단계 구조:
1) 가게 단위: 상가의 사진·정보·리뷰(StoreProfile)로 온/오프라인 광고 솔루션 자동 생성.
2) 상권 단위: Platform 수집 정보(상권분석 시계열·감성·리뷰 키워드) 기반 —
   현재는 services/districts.py 시드를 사용, gold/program_content_context 적재 후 교체.

윤리 기준: Humanistic Authority(균형·공생·공감) — 과장·허위·특정 자본 편중 금지.
"""
from __future__ import annotations

from collections import Counter

from app.core.config import settings
from app.services import districts as svc

# 규칙 기반 스텁의 카테고리별 강조 포인트 (LLM 연동 전 폴백)
_CATEGORY_ANGLE = {
    "카페": "시그니처 메뉴·공간 분위기",
    "의류": "스타일 큐레이션·신상 소식",
    "F&B": "대표 메뉴·재방문 혜택",
}
_DEFAULT_ANGLE = "가게의 강점·단골 혜택"


def _extract_tone_keywords(profile: dict) -> list[str]:
    """리뷰 텍스트에서 톤앤매너 키워드 추출 (빈도 기반 스텁).

    TODO: 실제 연동 — LLM(Claude vision)으로 리뷰+이미지에서 강점·톤 추출.
          image_urls 는 vision 입력으로 전달 (별도 Vision API 불필요, §8-D).
    """
    if profile.get("keywords"):
        return profile["keywords"][:5]
    words = [w for text in profile.get("reviews", []) for w in text.split() if len(w) >= 2]
    return [w for w, _ in Counter(words).most_common(5)]


def generate_store_marketing(profile: dict) -> dict:
    """가게 단위 온/오프라인 마케팅 광고 솔루션 생성.

    LLM 키(settings.llm_api_key) 설정 시 LLM 생성, 미설정 시 규칙 기반 스텁.
    반환: StoreMarketing 스키마 dict.
    """
    tone = _extract_tone_keywords(profile)
    angle = _CATEGORY_ANGLE.get(profile["category"], _DEFAULT_ANGLE)

    if settings.llm_api_key:
        # TODO: 실제 연동 — LangChain+Claude 로 리뷰·이미지 컨텍스트 주입 생성.
        #       프롬프트에 Humanistic Authority(균형·공생·공감) 가드레일 포함.
        pass

    tone_str = "·".join(tone) if tone else "리뷰 데이터 없음"
    online = [
        {"channel": "인스타그램", "kind": "online",
         "content": f"{profile['name']} — {angle}을 담은 릴스/피드 주 2회 게시",
         "rationale": f"리뷰 키워드({tone_str}) 기반 톤앤매너"},
        {"channel": "네이버 블로그", "kind": "online",
         "content": f"'{profile['name']}' 방문 후기형 포스팅 + 지역 키워드 최적화",
         "rationale": "네이버 지도 유입 동선(검색→플레이스) 강화"},
    ]
    offline = [
        {"channel": "지역 행사 참여", "kind": "offline",
         "content": "상권 플리마켓/팝업 부스 참여로 첫 방문 접점 확보",
         "rationale": "상권 공동 활성화 — 공생(Symbiosis) 원칙"},
        {"channel": "매장 앞 프로모션", "kind": "offline",
         "content": f"{angle} 중심의 입간판·시식(체험) 이벤트",
         "rationale": "보행 유동객 전환 — 과장 없는 실체 기반 소구"},
    ]
    return {
        "store_name": profile["name"],
        "category": profile["category"],
        "tone_keywords": tone,
        "online": online,
        "offline": offline,
        "ha_check": "균형·공생·공감 기준 자체 점검 통과 (스텁 — LLM 후처리 검증 TODO)",
        "source": "rule-stub",  # TODO: LLM 연동 시 "llm"
    }


def get_district_marketing(district_id: str) -> dict | None:
    """상권 단위 마케팅(행사 + 온라인 콘텐츠).

    TODO: 실제 연동 — Platform 수집 정보(gold/program_content_context:
          상권분석 시계열 + 감성 + 리뷰 키워드) 기반 생성으로 교체.
          현재는 시드 데이터(services/districts.py) 반환.
    """
    return svc.get_marketing(district_id)
