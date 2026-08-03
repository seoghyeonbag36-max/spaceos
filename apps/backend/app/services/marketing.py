"""마케팅 솔루션(Program) 생성 서비스 — 가게 단위 → 상권 단위.

2026-07-18 개정 2단계 구조:
1) 가게 단위: 상가의 사진·정보·리뷰(StoreProfile)로 온/오프라인 광고 솔루션 자동 생성.
   LLM 키(settings.llm_api_key) 설정 시 Claude 실호출(vision 포함), 실패·미설정 시
   규칙 기반 스텁 폴백 (source 필드로 구분).
2) 상권 단위: Platform 수집 정보(상권분석 시계열·감성·리뷰 키워드) 기반 —
   gold/program_content_context 를 가게 단위 생성의 컨텍스트로 결합하고,
   GET /{district_id} 의 온라인 콘텐츠도 같은 Gold 로 생성한다(2026-08-01).
   행사(events)는 서울열린데이터광장 문화행사 실데이터 — services/events.py 가 서빙한다.

윤리 기준: Humanistic Authority(균형·공생·공감) — 과장·허위·특정 자본 편중 금지.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.data.seoul_pages import DISTRICTS_BY_ID
from app.schemas.marketing import LLMDistrictContents, LLMStoreMarketing
from app.services import districts as svc
from app.services import events

# 규칙 기반 스텁의 카테고리별 강조 포인트 (LLM 폴백)
_CATEGORY_ANGLE = {
    "카페": "시그니처 메뉴·공간 분위기",
    "의류": "스타일 큐레이션·신상 소식",
    "F&B": "대표 메뉴·재방문 혜택",
}
_DEFAULT_ANGLE = "가게의 강점·단골 혜택"

# 상권 컨텍스트 결합용 district_id → gold 슬러그 매핑.
# 2026-08-01: 거점 id 와 gold 슬러그가 같은 54거점이 build_program13_context 로 모두
# 생성돼(garosugil 만 전용 Bronze), 표 대신 **동명 슬러그 + 파일 존재 확인**으로 푼다.
# 여기에는 id 가 슬러그와 다른 예외(별칭)만 남긴다. 새 거점을 추가하려면
# `python -m data.pipelines.build_gold --platform13` 로 Gold 만 만들면 자동 반영된다.
_DISTRICT_ALIAS: dict[str, str] = {
    "gangnam-garosugil": "garosugil",
}

# district_id 는 요청 본문에서 오므로 경로로 쓰기 전에 형태를 제한한다(경로 이탈 방지).
_SLUG_RE = re.compile(r"^[a-z0-9-]{1,40}$")

_GOLD_DIR = Path(__file__).resolve().parents[4] / "data" / "gold"

_SYSTEM_PROMPT = """너는 SpaceOS의 Program(가게 단위 마케팅 자동화) 생성기다.
입력된 가게 프로필(이름·카테고리·주소·리뷰 텍스트·사진·메뉴)과 상권 컨텍스트를 근거로,
소상공인이 바로 실행할 수 있는 온라인/오프라인 마케팅 솔루션을 제안한다.

원칙 (Humanistic Authority — 균형·공생·공감):
- 리뷰·사진·메뉴에 실제로 나타난 강점만 소구한다. 과장·허위·검증 불가한 최상급 표현 금지.
- 메뉴는 **적힌 품목·가격 그대로만** 쓴다. 없는 메뉴를 만들거나 가격을 지어내지 않는다.
  가격대를 논할 때는 적힌 가격에서만 끌어낸다.
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

    거점 id 형식이 아니거나 Gold 미적재면 None (컨텍스트 없이 생성).
    """
    slug = _DISTRICT_ALIAS.get(district_id or "", district_id or "")
    if not _SLUG_RE.match(slug):
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
        summaries = [s for _, g in trend.groupby("kind") if (s := _trend_summary(g))]
        if summaries:
            parts.append("검색 트렌드(최근 6개월, 방향은 계산된 값이다): " + "; ".join(summaries))
    return "\n".join(parts) or None


# 트렌드 방향 판정 임계 — 최근 3개월 평균이 직전 3개월 평균 대비 이만큼 벗어나야 방향을 붙인다.
# 5%는 검색량의 월별 잡음(계절·요일 구성)을 방향으로 오독하지 않을 정도로 잡은 값이다.
_TREND_FLAT_BAND = 0.05


def _trend_summary(group: "pd.DataFrame") -> str | None:
    """검색 트렌드 한 그룹을 **방향이 붙은 한 문장**으로 요약.

    왜 숫자를 그대로 넘기지 않는가 — 2026-08-01 실사고. 이 함수 이전에는 최근 3개월의
    원시 수치만 프롬프트에 실었고(`신사동 2026-05=67.7; …`), LLM 이 하락 시계열을 보고
    "신사동을 찾는 발걸음이 다시 늘고 있는 요즘"이라고 썼다. 같은 실행에서 가게 단위는
    방향을 맞혔으므로 모델이 아니라 **해석을 LLM 에 맡긴 설계**가 원인이다.
    방향은 여기서 계산해 확정하고, LLM 에는 판정 결과를 문장으로 준다.

    판정: 최근 3개월 평균 vs 직전 3개월 평균의 상대 변화. ±5%(_TREND_FLAT_BAND) 안이면 보합.
    6개 점이 안 되면 방향을 만들지 않고 None — 근거 없는 방향을 주느니 트렌드를 빼는 게 낫다.
    (Gold 단계에서 미완성 달은 이미 잘려 있다 — data/pipelines/build_gold._complete_trend_points)
    """
    name = str(group["kind"].iloc[0]).split(":", 1)[1]
    vals = group.sort_values("key")["value"].astype(float).tolist()[-6:]
    if len(vals) < 6:
        return None
    prior = sum(vals[:3]) / 3
    recent = sum(vals[3:]) / 3
    if prior <= 0:
        return None
    change = (recent - prior) / prior
    label = "보합" if abs(change) < _TREND_FLAT_BAND else ("상승" if change > 0 else "하락")
    return f"{name} {label}({prior:.1f}→{recent:.1f}, {change * 100:+.1f}%)"


def _call_llm(profile: dict, tone: list[str], district_ctx: str | None) -> LLMStoreMarketing:
    """Claude 실호출 — 리뷰 텍스트 + 사진 URL(vision) → 구조화 마케팅 솔루션."""
    import anthropic

    reviews = "\n".join(f"- {t}" for t in profile.get("reviews", [])) or "(리뷰 없음)"
    menu = "\n".join(f"- {m}" for m in profile.get("menu", [])) or "(메뉴 정보 없음)"
    text = (
        f"가게: {profile['name']} (카테고리: {profile['category']})\n"
        f"주소: {profile.get('address') or '(미상)'}\n"
        f"리뷰/블로그 텍스트:\n{reviews}\n"
        f"메뉴(적힌 그대로 — 없는 품목·가격을 추가하지 말 것):\n{menu}\n"
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
    # 메뉴가 있으면 첫 품목을 그대로 인용한다 — 스텁이라도 입력을 흘리지는 않는다.
    # 가공하지 않고 적힌 문자열을 그대로 쓴다(가격을 지어내지 않기 위해).
    lead_menu = (profile.get("menu") or [None])[0]
    offline = [
        {"channel": "지역 행사 참여", "kind": "offline",
         "content": "상권 플리마켓/팝업 부스 참여로 첫 방문 접점 확보",
         "rationale": "상권 공동 활성화 — 공생(Symbiosis) 원칙"},
        {"channel": "매장 앞 프로모션", "kind": "offline",
         "content": (f"'{lead_menu}' 중심의 입간판·시식(체험) 이벤트" if lead_menu
                     else f"{angle} 중심의 입간판·시식(체험) 이벤트"),
         "rationale": ("메뉴에 적힌 품목을 그대로 소구 — 보행 유동객 전환" if lead_menu
                       else "보행 유동객 전환 — 과장 없는 실체 기반 소구")},
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


_DISTRICT_SYSTEM_PROMPT = """너는 SpaceOS의 Program(상권 단위 마케팅) 온라인 콘텐츠 생성기다.
입력된 상권 컨텍스트(블로그 언급 키워드 빈도·업종 분포·검색 트렌드)만을 근거로,
그 상권의 온라인 콘텐츠 소재를 한 줄 카피 형태로 제안한다.

형식: "{소재 문장} #{해시태그} #{해시태그}" — 한 줄에 해시태그 2개.

원칙 (Humanistic Authority — 균형·공생·공감):
- 컨텍스트에 실제로 나타난 키워드·업종만 소구한다. 데이터에 없는 점포명·행사·수치를 지어내지 않는다.
- **데이터가 말하지 않는 방향을 주장하지 않는다.** 검색 트렌드에는 이미 판정된 방향
  (상승/보합/하락)이 붙어 있다. 그 방향과 어긋나게 쓰지 말 것 — '하락'인데 "다시 늘고 있는",
  '보합'인데 "급증하는" 식의 서술은 금지다. 하락·보합이면 유입 증가를 전제하지 말고
  이미 있는 강점(키워드·업종)에 소구하거나, 트렌드를 언급하지 않는다.
- 특정 점포나 자본에 편중하지 않고 상권 전체의 활성화를 향한다.
- 과장·허위·검증 불가한 최상급 표현을 쓰지 않는다.
- ha_check 에 위 기준으로 자체 점검한 결과를 1~2문장으로 쓴다.

출력: online_contents 2~4건. 한국어로 작성한다."""


def _call_district_llm(name: str, sub: str, ctx: str) -> LLMDistrictContents:
    """Claude 실호출 — 상권 컨텍스트(Gold) → 온라인 콘텐츠 한 줄 카피."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.llm_api_key)
    response = client.messages.parse(
        model=settings.llm_model,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=_DISTRICT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content":
                   f"상권: {name} ({sub})\n\n[상권 컨텍스트 — Platform 수집 데이터]\n{ctx}"}],
        output_format=LLMDistrictContents,
    )
    parsed = response.parsed_output
    if parsed is None:
        raise ValueError(f"LLM 구조화 출력 파싱 실패 (stop_reason={response.stop_reason})")
    return parsed


# 상권 콘텐츠 LLM 결과 캐시: district_id → (컨텍스트 파일 mtime, online_contents)
#
# 캐시가 없으면 이 엔드포인트는 **호출마다** LLM 을 친다 — 실측 12~14초 + 매번 크레딧이
# 나간다(2026-08-01). 거점 심층 뷰가 이 응답을 기다리므로 화면이 그만큼 멈춘다.
# 입력은 Gold 컨텍스트 파일 하나뿐이라 mtime 이 그대로면 결과도 그대로다. TTL 이 아니라
# mtime 으로 무효화하는 이유: 파이프라인을 다시 돌리면 즉시 반영돼야 하고, 안 돌렸다면
# 하루가 지나도 다시 칠 이유가 없다. 프로세스 재시작 시 비므로 코드·시드 변경도 반영된다.
_district_llm_cache: dict[str, tuple[float, list[str]]] = {}


def clear_district_cache() -> None:
    """상권 콘텐츠 LLM 캐시 비우기.

    평소에는 컨텍스트 파일 mtime 이 바뀌면 알아서 무효화되므로 부를 일이 없다.
    같은 프로세스 안에서 캐시를 강제로 버려야 할 때 쓴다(테스트 격리, 프롬프트 수정 후 재생성).
    """
    _district_llm_cache.clear()


def _context_mtime(district_id: str) -> float:
    """상권 컨텍스트 파일의 mtime. 없으면 0.0 (캐시 키로만 쓴다)."""
    slug = _DISTRICT_ALIAS.get(district_id, district_id)
    if not _SLUG_RE.match(slug):
        return 0.0
    for name in ("program_content_context.parquet", "program_content_context.csv"):
        path = _GOLD_DIR / slug / name
        if path.exists():
            return path.stat().st_mtime
    return 0.0


def get_district_marketing(district_id: str) -> dict | None:
    """상권 단위 마케팅(행사 + 온라인 콘텐츠) — Program 2단계.

    online_contents: Gold(program_content_context)의 블로그 키워드·업종 분포를 근거로
      LLM 생성. 키 미설정·Gold 미적재·호출 실패 시 시드 카피로 폴백(source 로 구분).
      생성 결과는 컨텍스트 파일 mtime 기준으로 캐시한다(위 주석 참조).
    events: 서울열린데이터광장 문화행사 실데이터(services/events.py). LLM 은 절대
      관여하지 않는다 — 좌표·일정이 붙은 실물이라 지어내면 없는 행사를 지도에 찍게 된다.
      Gold 미적재면 시드로 폴백하되 events_source 로 출처를 밝힌다.
    """
    base = svc.get_marketing(district_id)
    if base is None:
        return None

    # 행사: 서울열린데이터광장 문화행사 실데이터. Gold 미적재면 시드로 폴백하되
    # 출처를 밝힌다. 적재됐는데 그 거점에 예정 행사가 없으면 **빈 목록 그대로** —
    # 시드로 채우면 지어낸 행사를 지도에 다시 찍는 셈이다.
    real_events = events.for_district(district_id)
    if real_events is None:
        base = {**base, "events_source": "seed"}
    else:
        base = {**base, "events": real_events, "events_source": "seoul-open-data"}

    ctx = _district_context(district_id)
    if settings.llm_api_key and ctx:
        mtime = _context_mtime(district_id)
        hit = _district_llm_cache.get(district_id)
        if hit and hit[0] == mtime:
            return {**base, "online_contents": hit[1], "source": "llm"}

        d = DISTRICTS_BY_ID.get(district_id, {})
        try:
            parsed = _call_district_llm(d.get("name", district_id), d.get("sub", ""), ctx)
            if parsed.online_contents:
                _district_llm_cache[district_id] = (mtime, parsed.online_contents)
                return {**base, "online_contents": parsed.online_contents, "source": "llm"}
        except Exception as exc:
            print(f"[marketing] 상권 콘텐츠 LLM 생성 실패 → 시드 폴백: {exc}")
    return {**base, "source": "seed"}
