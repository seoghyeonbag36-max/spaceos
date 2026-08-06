"""Humanistic Authority 후처리 검증 — 생성물이 프롬프트 지시를 실제로 지켰는지 서버가 확인한다.

## 왜 필요한가 (docs/feature-program.md §3-4 미이행분)

`ha_check` 는 **LLM 이 스스로 "점검 통과"라고 적은 문장**이다. 그게 사실인지 확인하는 코드는
없었다. 자기신고는 근거가 아니다 — 이 저장소가 실측처럼 보이는 추정치를 가장 나쁜 산출물로
보는 것과 같은 이유다(AGENTS.md §0).

## 두 등급으로 나누는 이유

- **violation(허위)** — 입력과 대조하면 참·거짓이 갈린다. 지어낸 금액, 서버가 이미 계산해
  확정한 트렌드 방향을 뒤집는 서술. 소상공인이 그대로 전단에 인쇄하면 실제 손해가 나므로
  **응답을 버리고 폴백으로 떨어뜨린다.**
- **warning(과장·편중 의심)** — 사전 매칭이라 오탐이 섞인다. 2026-08-01 동명이지 정제에서
  배운 것이 그대로 적용된다: 자동 규칙을 세게 걸면 진짜 상호명까지 죽는다(체험단 필터를
  포기한 이유). 그래서 **통과시키되 findings 로 밝혀 사람이 보게 한다.**

## 오탐을 어디서 끊었나 (규칙마다 근거가 있다)

- 금액: `1만원` 은 잡고 `1만 5천원` 같은 혼합 표기는 못 잡는다 — 아래 한계 참조.
- 트렌드: **주장과 목표를 가른다.** "손님이 늘고 있다"(주장)는 걸고 "손님을 늘리는
  전단"(목표)은 안 건다. 후자는 정당한 오프라인 제안이라 이걸 죽이면 기능이 망가진다.
- 최상급: 입력 텍스트에 같은 표현이 있으면 면제한다(리뷰에 "최고예요"가 있으면 인용할
  근거가 있는 것이다). `최대한` 은 `최대` 로 오인되므로 스캔 전에 걷어낸다.
- 비방: `경쟁력` 은 비방이 아니라 제외한다.

## 알려진 한계

- 퍼센트 할인("10% 할인")은 금액 검사에 안 걸린다. 금액과 성격은 같지만 정상 표현과
  구분이 어려워 남겨 뒀다.
- `1만 5천원` 처럼 한자어 수 표기가 섞이면 금액 파싱이 놓친다.
- 사전 기반 검사(최상급·비방)는 우회가 쉽다. 이건 정직한 생성물을 확인하는 장치이지
  적대적 입력을 막는 장치가 아니다.
"""
from __future__ import annotations

import re

from app.schemas.marketing import HAFinding, LLMDistrictContents, LLMStoreMarketing

# ── 금액 ─────────────────────────────────────────────────────────────────────
# "6,000원" / "6000 원" / "1만원". 앞의 숫자만 잡고 콤마는 지운다.
_PRICE_RE = re.compile(r"(\d[\d,]*)\s*원")
_MAN_PRICE_RE = re.compile(r"(\d[\d,]*)\s*만\s*원")

# ── 트렌드 방향 ───────────────────────────────────────────────────────────────
# marketing._trend_summary 가 만드는 형식: "신사동 하락(67.4→65.0, -3.6%)"
_TREND_LABEL_RE = re.compile(r"(상승|보합|하락)\(")

# 유입을 가리키는 말. 아래 '증가 주장'과 **같은 문장에** 있을 때만 위반으로 본다.
_INFLOW_WORDS = ("발걸음", "유입", "방문객", "방문자", "손님", "인파", "검색량",
                 "관심", "고객", "찾는", "찾아오", "붐빔")

# **주장**만 넣는다. "늘리는"(목표)은 일부러 뺐다 — "손님을 늘리는 전단"은 정당한 제안이다.
_INCREASE_CLAIMS = ("늘고 있", "늘어나", "늘어난", "늘었", "증가하고 있", "증가세",
                    "상승세", "많아지", "높아지고 있", "커지고 있", "회복세")

# 단독으로도 유입 증가를 주장하는 말 — 유입어와 짝지을 필요가 없다.
_STANDALONE_SURGE = ("붐비", "몰리", "북적", "문전성시")

# ── 최상급 ───────────────────────────────────────────────────────────────────
_SUPERLATIVES = ("최고", "최상", "최대", "최초", "유일", "1위", "1등", "완벽",
                 "압도적", "최강", "국내 최", "세계 최", "가장 맛있", "제일 맛있")
# "최대한"은 "최대"로 오인된다. 스캔 전에 지운다.
_SUPERLATIVE_NOISE = ("최대한",)

# ── 비방·출혈경쟁 ────────────────────────────────────────────────────────────
# "경쟁력"은 비방이 아니라서 뺐다.
_DISPARAGE = ("경쟁점", "경쟁업체", "경쟁 업체", "타 매장", "타매장", "다른 가게보다",
              "주변 가게보다", "이웃 가게보다", "주변보다 저렴", "최저가", "보다 우수")

# ── 채널 계열 (편중 판정용) ──────────────────────────────────────────────────
_CHANNEL_FAMILY = {
    "인스타": "instagram", "릴스": "instagram",
    "네이버": "naver", "블로그": "naver", "플레이스": "naver", "스마트플레이스": "naver",
    "카카오": "kakao", "톡채널": "kakao",
    "유튜브": "youtube", "쇼츠": "youtube",
    "배달의민족": "delivery", "배민": "delivery", "쿠팡": "delivery", "요기요": "delivery",
}

_SENTENCE_RE = re.compile(r"[.!?\n]+")

# rationale 이 이보다 짧으면 근거를 적었다고 보기 어렵다.
_MIN_RATIONALE_LEN = 10


def _prices(text: str) -> set[int]:
    """텍스트에서 원화 금액을 집합으로. "1만원" → 10000."""
    out: set[int] = set()
    for m in _MAN_PRICE_RE.finditer(text or ""):
        try:
            out.add(int(m.group(1).replace(",", "")) * 10_000)
        except ValueError:
            continue
    for m in _PRICE_RE.finditer(text or ""):
        # "1만원"은 숫자와 원 사이에 "만"이 끼어 여기서는 안 잡힌다(위에서 이미 처리했다).
        raw = m.group(1).replace(",", "")
        try:
            out.add(int(raw))
        except ValueError:
            continue
    return out


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(text or "") if s.strip()]


def _check_prices(generated: str, allowed_text: str) -> list[HAFinding]:
    """생성물의 금액이 전부 입력에 있던 것인지. 없으면 지어낸 것이다."""
    allowed = _prices(allowed_text)
    invented = sorted(_prices(generated) - allowed)
    if not invented:
        return []
    shown = ", ".join(f"{v:,}원" for v in invented[:5])
    return [HAFinding(
        severity="violation", code="fabricated_price",
        message=(f"입력에 없는 금액 {len(invented)}건을 생성물이 말한다 — 가격은 입력에 적힌 "
                 "것만 쓸 수 있다. 지어낸 가격은 그대로 전단에 인쇄된다."),
        evidence=shown)]


def _check_trend(generated: str, context: str | None) -> list[HAFinding]:
    """서버가 확정한 트렌드 방향(하락·보합)을 생성물이 뒤집는지.

    2026-08-01 실사고가 이 검사의 이유다 — 입력이 하락인데 생성 카피가
    "신사동을 찾는 발걸음이 다시 늘고 있는 요즘"이라고 썼다.
    상승이 하나라도 섞여 있으면 증가 서술이 정당할 수 있으므로 걸지 않는다.
    """
    if not context:
        return []
    labels = set(_TREND_LABEL_RE.findall(context))
    if not labels or "상승" in labels:
        return []

    for sent in _sentences(generated):
        surge = next((w for w in _STANDALONE_SURGE if w in sent), None)
        claim = next((w for w in _INCREASE_CLAIMS if w in sent), None)
        inflow = any(w in sent for w in _INFLOW_WORDS)
        if surge or (claim and inflow):
            return [HAFinding(
                severity="violation", code="trend_contradiction",
                message=(f"검색 트렌드가 {'·'.join(sorted(labels))}인데 생성물이 유입 증가를 "
                         "주장한다 — 방향은 서버가 계산해 확정한 값이다."),
                evidence=sent[:120])]
    return []


def _check_superlatives(generated: str, source_text: str) -> list[HAFinding]:
    """근거 없는 최상급. 입력에 같은 표현이 있으면 인용할 근거가 있으므로 면제한다."""
    haystack = generated
    for noise in _SUPERLATIVE_NOISE:
        haystack = haystack.replace(noise, "")
    hits = [w for w in _SUPERLATIVES if w in haystack and w not in (source_text or "")]
    if not hits:
        return []
    return [HAFinding(
        severity="warning", code="unsupported_superlative",
        message=("입력에 근거가 없는 최상급 표현이다 — 검증 불가한 최상급은 쓰지 않는다. "
                 "(사전 매칭이라 오탐일 수 있으니 눈으로 확인하라)"),
        evidence=", ".join(hits[:5]))]


def _check_disparagement(generated: str) -> list[HAFinding]:
    """이웃 가게 비방·출혈 경쟁 조장 — 공생(Symbiosis) 원칙 위반."""
    hits = [w for w in _DISPARAGE if w in (generated or "")]
    if not hits:
        return []
    return [HAFinding(
        severity="warning", code="competitor_disparagement",
        message=("이웃 가게와의 비교·출혈 경쟁을 암시한다 — 상권 공동 활성화(공생)를 해친다. "
                 "(사전 매칭이라 오탐일 수 있으니 눈으로 확인하라)"),
        evidence=", ".join(hits[:5]))]


def _family(channel: str) -> str:
    for token, fam in _CHANNEL_FAMILY.items():
        if token in (channel or ""):
            return fam
    return (channel or "").strip()


def _check_channel_balance(online: list) -> list[HAFinding]:
    """온라인 제안이 한 플랫폼 계열에만 쏠렸는지 — 균형(Balance) 원칙.

    1건뿐이면 편중을 논할 수 없으므로 2건 이상일 때만 본다.
    """
    if len(online) < 2:
        return []
    fams = {_family(p.channel) for p in online}
    if len(fams) > 1:
        return []
    return [HAFinding(
        severity="warning", code="channel_concentration",
        message=(f"온라인 제안 {len(online)}건이 모두 같은 플랫폼 계열이다 — "
                 "특정 플랫폼·자본에 편중되지 않게 채널을 섞어야 한다."),
        evidence=", ".join(p.channel for p in online))]


def _check_rationales(plans: list) -> list[HAFinding]:
    """근거가 비었거나 형식뿐인 제안 — 각 제안에는 근거를 명시해야 한다."""
    bare = [p.channel for p in plans if len((p.rationale or "").strip()) < _MIN_RATIONALE_LEN]
    if not bare:
        return []
    return [HAFinding(
        severity="warning", code="missing_rationale",
        message=f"근거(rationale)가 비었거나 너무 짧은 제안 {len(bare)}건 — 각 제안은 "
                "리뷰 키워드나 상권 데이터로 근거를 밝혀야 한다.",
        evidence=", ".join(bare[:5]))]


def check_store(parsed: LLMStoreMarketing, profile: dict,
                context: str | None) -> list[HAFinding]:
    """가게 단위 생성물 검증. violation 이 하나라도 있으면 호출부가 응답을 버린다."""
    plans = list(parsed.online) + list(parsed.offline)
    generated = " ".join(f"{p.content} {p.rationale}" for p in plans)
    generated = f"{generated} {parsed.ha_check or ''}"
    # 금액의 근거는 메뉴가 정본이고, 리뷰에 적힌 가격도 점주 입력에서 온 것이라 인정한다.
    # **상권 컨텍스트도 근거에 넣는다** — 행사가 컨텍스트에 합류(2026-08-06)하면서 행사
    # 요금·기간의 숫자가 거기 실린다. 빼면 실린 행사비를 인용한 것이 지어낸 금액으로
    # 잘못 걸린다. 대가로 컨텍스트의 금액을 가게 가격처럼 쓰는 경우는 못 잡지만,
    # 정상 인용을 폐기하는 쪽이 더 나쁘다.
    allowed_text = " ".join([*(profile.get("menu") or []), *(profile.get("reviews") or []),
                             context or ""])
    source_text = f"{allowed_text} {profile.get('name', '')}"

    return [
        *_check_prices(generated, allowed_text),
        *_check_trend(generated, context),
        *_check_superlatives(generated, source_text),
        *_check_disparagement(generated),
        *_check_channel_balance(list(parsed.online)),
        *_check_rationales(plans),
    ]


def check_district(parsed: LLMDistrictContents, context: str) -> list[HAFinding]:
    """상권 단위 온라인 카피 검증.

    상권 컨텍스트에는 가격 정보가 없다(키워드 빈도·업종 분포·트렌드뿐). 그래서 카피에
    나오는 금액은 근거가 컨텍스트에 있지 않는 한 지어낸 값이다.
    """
    generated = " ".join(parsed.online_contents) + f" {parsed.ha_check or ''}"
    return [
        *_check_prices(generated, context or ""),
        *_check_trend(generated, context),
        *_check_superlatives(generated, context or ""),
        *_check_disparagement(generated),
    ]


def has_violation(findings: list[HAFinding]) -> bool:
    """폐기해야 하는 등급이 섞여 있는가."""
    return any(f.severity == "violation" for f in findings)


def summarize(findings: list[HAFinding]) -> str:
    """로그 한 줄용 요약."""
    return "; ".join(f"[{f.severity}] {f.code}={f.evidence or '-'}" for f in findings)
