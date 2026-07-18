"""마케팅 솔루션(Program) 생성 서비스 — 가게 단위 → 상권 단위.

2026-07-18 개정 2단계 구조:
1) 가게 단위: 상가의 사진·정보·리뷰(StoreProfile)로 온/오프라인 광고 솔루션 자동 생성.
   LLM 키(settings.llm_api_key) 설정 시 Claude 실호출(vision 포함), 실패·미설정 시
   규칙 기반 스텁 폴백 (source 필드로 구분).
2) 상권 단위: Platform 수집 정보(상권분석 시계열·감성·리뷰 키워드) 기반 —
   가게 단위 생성에는 gold/program_content_context 를 컨텍스트로 결합하고,
   GET /{district_id} 는 services/districts.py 시드를 사용(Gold 교체 TODO).

윤리 기준: Humanistic Authority(균형·공생·공감) — 과장·허위·특정 자본 편중 금지.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.schemas.marketing import LLMStoreMarketing
from app.services import districts as svc

# 규칙 기반 스텁의 카테고리별 강조 포인트 (LLM 폴백)
_CATEGORY_ANGLE = {
    "카페": "시그니처 메뉴·공간 분위기",
    "의류": "스타일 큐레이션·신상 소식",
    "F&B": "대표 메뉴·재방문 혜택",
}
_DEFAULT_ANGLE = "가게의 강점·단골 혜택"

# 상권 컨텍스트 결합용 district_id → gold 슬러그 매핑.
# 새 거점을 추가하려면: ① data/config/<slug>.py 수집 설정 작성 → ② 수집기 실행
# → ③ build_gold 로 gold/<slug>/program_content_context 생성 → ④ 여기에 매핑 추가.
# (예: 서울 Page 시드 지역 확장 시 이 표만 늘리면 가게 단위 생성에 자동 반영)
_DISTRICT_GOLD_SLUG: dict[str, str] = {
    "garosugil": "garosugil",
    "gangnam-garosugil": "garosugil",
}

_GOLD_DIR = Path(__file__).resolve().parents[4] / "data" / "gold"

_SYSTEM_PROMPT = """너는 SpaceOS의 Program(가게 단위 마케팅 자동화) 생성기다.
입력된 가게 프로필(이름·카테고리·주소·리뷰 텍스트·사진)과 상권 컨텍스트를 근거로,
소상공인이 바로 실행할 수 있는 온라인/오프라인 마케팅 솔루션을 제안한다.

원칙 (Humanistic Authority — 균형·공생·공감):
- 리뷰·사진에 실제로 나타난 강점만 소구한다. 과장·허위·검증 불가한 최상급 표현 금지.
- 상권 공동 활성화(공생)를 해치는 제안(이웃 가게 비방·출혈 경쟁 조장) 금지.
- 특정 플랫폼·자본에 편중되지 않게 채널을 균형 있게 섞는다.
- 각 제안에는 반드시 근거(rationale)를 리뷰 키워드나 상권 데이터로 명시한다.
- ha_check 필드에 위 기준으로 자체 점검한 결과를 1~2문장으로 기술한다.

출력: 온라인 2~3건, 오프라인 2~3건. 한국어로 작성한다."""


def _extract_tone_keywords(profile: dict) -> list[str]:
    """리뷰 텍스트에서 톤앤매너 키워드 추출 (빈도 기반 — LLM 폴백/프롬프트 보조)."""
    if profile.get("keywords"):
        return profile["keywords"][:5]
    words = [w for text in profile.get("reviews", []) for w in text.split() if len(w) >= 2]
    return [w for w, _ in Counter(words).most_common(5)]


def _district_context(district_id: str | None) -> str | None:
    """Platform Gold(program_content_context)에서 상권 컨텍스트 요약 텍스트 생성.

    매핑(_DISTRICT_GOLD_SLUG)에 없는 거점이거나 Gold 미적재면 None (컨텍스트 없이 생성).
    """
    slug = _DISTRICT_GOLD_SLUG.get(district_id or "")
    if slug is None:
        return None
    try:
        import pandas as pd
        path = _GOLD_DIR / slug / "program_content_context.parquet"
        if not path.exists():
            path = _GOLD_DIR / slug / "program_content_context.csv"
            if not path.exists():
                return None
            df = pd.read_csv(path)
        else:
            df = pd.read_parquet(path)
    except Exception:
        return None

    parts: list[str] = []
    kw = df[df["kind"] == "blog_keyword"].nlargest(5, "value")
    if len(kw):
        parts.append("블로그 언급 키워드: " + ", ".join(
            f"{r.key}({int(r.value)}건)" for r in kw.itertuples()))
    cat = df[df["kind"] == "category"].nlargest(5, "value")
    if len(cat):
        parts.append("상권 업종 분포: " + ", ".join(
            f"{r.key} {int(r.value)}곳" for r in cat.itertuples()))
    trend = df[df["kind"].astype(str).str.startswith("trend:")]
    if len(trend):
        last = trend.sort_values("key").groupby("kind").tail(3)
        parts.append("검색 트렌드(최근): " + "; ".join(
            f"{r.kind.split(':', 1)[1]} {r.key}={round(r.value, 1)}" for r in last.itertuples()))
    return "\n".join(parts) or None


def _call_llm(profile: dict, tone: list[str], district_ctx: str | None) -> LLMStoreMarketing:
    """Claude 실호출 — 리뷰 텍스트 + 사진 URL(vision) → 구조화 마케팅 솔루션."""
    import anthropic

    reviews = "\n".join(f"- {t}" for t in profile.get("reviews", [])) or "(리뷰 없음)"
    text = (
        f"가게: {profile['name']} (카테고리: {profile['category']})\n"
        f"주소: {profile.get('address') or '(미상)'}\n"
        f"리뷰/블로그 텍스트:\n{reviews}\n"
        f"사전 추출 키워드: {', '.join(tone) if tone else '(없음)'}"
    )
    if district_ctx:
        text += f"\n\n[상권 컨텍스트 — Platform 수집 데이터]\n{district_ctx}"

    content: list[dict] = [
        {"type": "image", "source": {"type": "url", "url": u}}
        for u in profile.get("image_urls", [])[:4]
        if str(u).startswith(("http://", "https://"))
    ]
    content.append({"type": "text", "text": text})

    client = anthropic.Anthropic(api_key=settings.llm_api_key)
    response = client.messages.parse(
        model=settings.llm_model,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
        output_format=LLMStoreMarketing,
    )
    parsed = response.parsed_output
    if parsed is None:
        raise ValueError(f"LLM 구조화 출력 파싱 실패 (stop_reason={response.stop_reason})")
    return parsed


def generate_store_marketing(profile: dict) -> dict:
    """가게 단위 온/오프라인 마케팅 광고 솔루션 생성.

    LLM 키(settings.llm_api_key) 설정 시 LLM 생성, 미설정·실패 시 규칙 기반 스텁.
    반환: StoreMarketing 스키마 dict.
    """
    tone = _extract_tone_keywords(profile)

    if settings.llm_api_key:
        try:
            parsed = _call_llm(profile, tone, _district_context(profile.get("district_id")))
            return {
                "store_name": profile["name"],
                "category": profile["category"],
                "tone_keywords": parsed.tone_keywords[:5] or tone,
                "online": [{**p.model_dump(), "kind": "online"} for p in parsed.online],
                "offline": [{**p.model_dump(), "kind": "offline"} for p in parsed.offline],
                "ha_check": parsed.ha_check,
                "source": "llm",
            }
        except Exception as exc:
            print(f"[marketing] LLM 생성 실패 → 규칙 기반 폴백: {exc}")

    return _rule_stub(profile, tone)


def _rule_stub(profile: dict, tone: list[str]) -> dict:
    """규칙 기반 스텁 (LLM 미설정/실패 폴백)."""
    angle = _CATEGORY_ANGLE.get(profile["category"], _DEFAULT_ANGLE)
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
        "ha_check": "균형·공생·공감 기준 자체 점검 통과 (규칙 기반 스텁)",
        "source": "rule-stub",
    }


def get_district_marketing(district_id: str) -> dict | None:
    """상권 단위 마케팅(행사 + 온라인 콘텐츠).

    TODO: 실제 연동 — Platform 수집 정보(gold/program_content_context:
          상권분석 시계열 + 감성 + 리뷰 키워드) 기반 생성으로 교체.
          현재는 시드 데이터(services/districts.py) 반환.
    """
    return svc.get_marketing(district_id)
