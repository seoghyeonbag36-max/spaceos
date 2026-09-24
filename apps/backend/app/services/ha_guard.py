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
- 최상급: 입력 텍스트에 같은 표현이 있으면 면제한다(창업자가 낸 차별점에 "최고"가
  있으면 인용할 근거가 있는 것이다). `최대한` 은 `최대` 로 오인되므로 스캔 전에 걷어낸다.
- 비방: `경쟁력` 은 비방이 아니라 제외한다.
- 미검증 경험: **주장과 측정을 가른다.** "단골 고객에게"(주장)는 걸고 "재방문율을
  집계한다"(측정)는 안 건다. 후자는 팝업 검증의 핵심 지표라 이걸 죽이면 이 트랙의
  결론이 통째로 사라진다(services/program_brief).

## 알려진 한계

- 퍼센트 할인("10% 할인")은 금액 검사에 안 걸린다. 금액과 성격은 같지만 정상 표현과
  구분이 어려워 남겨 뒀다.
- `1만 5천원` 처럼 한자어 수 표기가 섞이면 금액 파싱이 놓친다.
- 사전 기반 검사(최상급·비방)는 우회가 쉽다. 이건 정직한 생성물을 확인하는 장치이지
  적대적 입력을 막는 장치가 아니다.
"""
from __future__ import annotations

import re

from app.schemas.marketing import HAFinding, LLMDistrictContents, LLMProgramPlan
from app.services import program_brief
from app.services.program_brief import MEASUREMENT_MARKS, UNPROVEN_EVIDENCE

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


def _check_unproven_evidence(generated: str) -> list[HAFinding]:
    """아직 없는 경험(단골·기존 고객·쌓인 후기)을 근거로 삼는가.

    Program 의 대상은 전부 **이 자리에서 이 아이템을 아직 해 보지 않은** 사람이다
    (예비창업자 · 팝업·가오픈·MVP 로 검증하려는 기창업자). 그래서 이 검사는 조건 없이
    **항상 켜진다** — 종전에는 '영업 중인 가게'가 대상에 섞여 있어 개업예정일이 있을
    때만 켰지만, 이제 갈라야 할 '영업 중'이 없다.

    ## 주장과 측정을 가른다

    금칙어가 **측정 문장**에 있으면 면제한다. 재방문율은 팝업 검증의 핵심 지표이고
    후기 수집은 가오픈의 목적이라, 그 문장까지 잡으면 이 트랙의 결론인 검증 지표가
    통째로 폐기된다. 거르는 것은 지표가 아니라 **이미 있다고 말하는 것**이다.
    """
    hits: list[str] = []
    for sent in _sentences(generated):
        if any(mark in sent for mark in MEASUREMENT_MARKS):
            continue    # 측정·판정 문장은 주장이 아니다
        hits.extend(w for w in UNPROVEN_EVIDENCE if w in sent)
    hit = sorted(set(hits))
    if not hit:
        return []
    return [HAFinding(
        severity="violation", code="unproven_experience_claim",
        message=("아직 이 자리에서 해 보지 않은 아이템에 단골·기존 고객·쌓인 후기를 "
                 "전제하는 제안을 한다 — 있지도 않은 경험을 근거로 삼는 것이라 그대로 "
                 "거짓이 된다. 앞으로 측정할 지표로 적는 것은 정상이다."),
        evidence=", ".join(hit[:5]))]


# 검증 지표의 목표선·판정선에 있어야 하는 것 — **셀 수 있는 값**이다.
# "많이 오면 성공" 같은 문장은 사후에 말을 맞추게 되므로 지표가 아니다.
_COUNTABLE_RE = re.compile(r"\d")
_MIN_DECISION_LEN = 8


def _check_signals(signals: list) -> list[HAFinding]:
    """검증 지표가 실제로 판정에 쓸 수 있는 모양인가 (2026-09-17 신설).

    팝업·가오픈·MVP 는 홍보가 아니라 **판정**이 목적이다. 지표가 아예 없거나, 목표선에
    숫자가 없거나, 가설을 기각할 조건이 비어 있으면 그 검증은 결과를 보고 사후에 말을
    맞추게 된다.

    등급은 **warning** 이다. 표기 방식이 다양해("절반 이하", "손익분기 미만") 숫자
    없는 정당한 판정선이 있을 수 있고, 여기서 응답을 버리면 나머지 채널안까지 함께
    사라진다 — 밝히고 사람이 보게 하는 쪽이 낫다(§0-3 의 등급 판단과 같다).
    """
    if not signals:
        return [HAFinding(
            severity="warning", code="missing_validation_signal",
            message=("검증 지표가 없다 — 무엇을 세면 '통했다'고 할지 정하지 않은 검증은 "
                     "판정이 아니라 지출이다."),
            evidence="signals=0")]

    out: list[HAFinding] = []
    vague = [s.name for s in signals
             if not _COUNTABLE_RE.search(f"{s.target or ''} {s.method or ''}")]
    if vague:
        out.append(HAFinding(
            severity="warning", code="unmeasurable_signal",
            message=(f"목표선에 셀 수 있는 값이 없는 지표 {len(vague)}건 — 숫자가 없으면 "
                     "결과를 보고 나서 성공이었다고 말하게 된다."),
            evidence=", ".join(vague[:5])))

    bare = [s.name for s in signals if len((s.decision or "").strip()) < _MIN_DECISION_LEN]
    if bare:
        out.append(HAFinding(
            severity="warning", code="missing_decision_rule",
            message=(f"가설을 기각할 조건이 비었거나 너무 짧은 지표 {len(bare)}건 — "
                     "기각 조건은 검증을 **시작하기 전에** 적어야 한다."),
            evidence=", ".join(bare[:5])))
    return out


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

    ## 못 돌린 것과 통과한 것을 가른다 (2026-09-16 fail-open 차단)

    종전에는 컨텍스트나 트렌드 라벨이 없으면 `[]` 를 돌려줬다. 그러면 응답에서
    **"검사했고 깨끗하다"와 "검사 자체를 못 했다"가 똑같이 보인다.** 이 검사는
    violation 등급이라 응답을 버리는 힘이 있는데, 입력 하나가 비면 그 힘이 조용히
    사라진다 — `pppp_status` 가 트렌드 라벨 게이트를 세우며 적어 둔 위험이 이것이다
    ("라벨이 없으면 트렌드 역행 검사가 조용히 통과한다").

    그래서 못 돌렸을 때는 `trend_unverified` 를 남긴다. 등급은 **warning** 이다 —
    검사 불가는 허위의 증거가 아니므로 응답을 버릴 근거가 못 되지만, 무엇이 검증
    안 됐는지는 드러나야 한다(§0-3 의 '통과시키되 findings 로 밝힌다'와 같은 처리).
    """
    if not context:
        return [HAFinding(
            severity="warning", code="trend_unverified",
            message=("상권 컨텍스트가 없어 트렌드 역행 검사를 돌리지 못했다 — "
                     "이 응답은 '트렌드를 뒤집지 않았다'가 검증된 것이 아니다."),
            evidence="context=None")]
    labels = set(_TREND_LABEL_RE.findall(context))
    if not labels:
        return [HAFinding(
            severity="warning", code="trend_unverified",
            message=("컨텍스트에 트렌드 라벨(상승/보합/하락)이 없어 역행 검사를 "
                     "돌리지 못했다 — 검색 트렌드 수집이 비었을 때 이 값이 뜬다."),
            evidence="라벨 0건")]
    if "상승" in labels:
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
                "자리·상권의 수치나 창업자가 낸 가설로 근거를 밝혀야 한다.",
        evidence=", ".join(bare[:5]))]


# ── 새 출력 계약(2026-08-23) 검증 ────────────────────────────────────────────
# 스키마가 필드의 **존재**를 강제해도 내용이 규칙을 지켰는지는 서버가 봐야 한다.
# `ha_check` 가 자기신고라 근거가 아닌 것과 같은 이유다(§0-3).

# 컨텍스트가 "인용할 행사가 없다"고 못 박는 문구. 이게 실려 있는데도 mode="cite" 가
# 나오면 지어낸 것이 확정된다 — 이름 대조 없이 판정되므로 오탐이 없다.
_NO_EVENT_MARKS = ("확인된 예정 행사가 없다", "안에 예정 행사가 없다",
                   "행사 참여·연계를 제안하지 말 것", "연계를 제안하지 말 것")
# 신규 제안의 근거로 인정하는 수치 표기. 빈 시간대 격차(%p)나 유동/매출 수치.
_GAP_FIGURE_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%p|%|시)")


def _check_cited_events(offline: list, context: str | None) -> list[HAFinding]:
    """컨텍스트가 '인용할 행사가 없다'고 했는데 기존 행사를 인용한 제안 — violation.

    2026-08-06 에는 신규 행사 제안을 **통째로 금지**해서 막았다. 그런데 대상이 공실
    창업 기업으로 바뀌면서 신규 제안이 이 출력의 목적이 됐다(§0-B 원칙 3). 금지를
    없애는 대신 **인용(cite)과 제안(propose)을 갈라** 인용만 사실 검증을 건다.
    """
    if not context or not any(m in context for m in _NO_EVENT_MARKS):
        return []
    cited = [p for p in offline if (getattr(p, "mode", None) or "") == "cite"]
    if not cited:
        return []
    return [HAFinding(
        severity="violation", code="fabricated_event",
        message="컨텍스트에 인용할 예정 행사가 없다고 적혀 있는데 기존 행사를 연계"
                f"(mode=cite)한 제안이 {len(cited)}건 있다 — 없는 행사를 사실로 주장한다. "
                "새로 열자는 제안이라면 mode=propose 로 적어야 한다.",
        evidence=", ".join(p.channel for p in cited[:5]))]


def _check_proposed_events(offline: list) -> list[HAFinding]:
    """신규 행사 제안(propose)에 빈 시간대 격차 수치가 없으면 경고.

    수치 없는 제안은 "상권 플리마켓 참여"처럼 어느 상권에나 해당하는 말이 된다 —
    2026-08-06 에 고치려던 바로 그 증상이다. 다만 표기 방식이 다양해 오탐이 섞이므로
    폐기하지 않고 밝히기만 한다.
    """
    bare = [p for p in offline
            if (getattr(p, "mode", None) or "") == "propose"
            and not _GAP_FIGURE_RE.search(p.rationale or "")]
    if not bare:
        return []
    return [HAFinding(
        severity="warning", code="unsupported_event_proposal",
        message=f"신규 행사 제안 {len(bare)}건의 근거에 빈 시간대 격차 수치가 없다 — "
                "수치가 없으면 어느 상권에나 해당하는 일반론이 된다.",
        evidence=", ".join(p.channel for p in bare[:5]))]


def _check_actors(offline: list) -> list[HAFinding]:
    """오프라인 제안에 협업 주체가 없으면 경고 — 공생(Symbiosis) 원칙의 실행 형태.

    신규 창업자가 혼자 축제를 열 수는 없다. 실측으로 상권 행사 785건 중 57%가
    공공·준공공 주최다. 주체가 비면 "당신이 알아서 하세요"가 된다.
    """
    # mode="own"(매장 자체 접점 — 입간판·시식)은 애초에 협업이 필요 없다. 여기까지
    # 주체를 요구하면 정당한 제안이 죽는다.
    solo = [p for p in offline
            if (getattr(p, "mode", None) or "") != "own"
            and not (getattr(p, "actors", None) or [])]
    if not solo:
        return []
    return [HAFinding(
        severity="warning", code="missing_actors",
        message=f"오프라인(상권 활성화) 제안 {len(solo)}건에 협업 주체가 비어 있다 — "
                "상권 활성화는 기업 단독으로 실행할 수 없다.",
        evidence=", ".join(p.channel for p in solo[:5]))]


def _check_budget_shares(online: list) -> list[HAFinding]:
    """온라인 예산 배분 비율의 합이 100% 에서 벗어나면 경고.

    비율로만 제안하는 것은 "얼마를 쓸지는 기업 몫"이라는 원칙의 구현이다(§0-B 원칙 2).
    합이 안 맞으면 배분표로 쓸 수 없다.
    """
    shares = [getattr(p, "budget_share", None) for p in online]
    vals = [v for v in shares if isinstance(v, int)]
    if not vals or len(vals) != len(shares):
        return []
    total = sum(vals)
    if 95 <= total <= 105:
        return []
    return [HAFinding(
        severity="warning", code="budget_share_mismatch",
        message=f"온라인 예산 배분 비율의 합이 {total}% 다 — 100% 가 되어야 배분표로 쓸 수 있다.",
        evidence=" + ".join(f"{p.channel} {p.budget_share}%" for p in online[:5]))]


def check_program(parsed: LLMProgramPlan, brief: dict,
                  context: str | None) -> list[HAFinding]:
    """검증 프로그램 생성물 검증. violation 이 하나라도 있으면 호출부가 응답을 버린다."""
    plans = list(parsed.online) + list(parsed.offline)
    # ⚠ 조각을 **줄바꿈으로** 잇는다. 공백으로 이으면 `_sentences` 가 전체를 한 문장으로
    # 보고, 문장 단위로 판정하는 검사들이 무력해진다 — 실측(2026-09-17): 어느 지표의
    # "…미만이면 기각한다"가 측정 표현으로 인정되면서 **다른 제안**의 "단골 고객에게"가
    # 함께 면제됐다. 같은 함정이 트렌드 검사에도 있었다(주장과 유입어가 서로 다른
    # 제안에 있어도 한 문장으로 읽혔다).
    parts = [p.content for p in plans] + [p.rationale for p in plans]
    # 검증 지표도 검사 대상에 넣는다 — 지표 문장에 지어낸 금액이나 미검증 경험이
    # 들어가면 채널안에 든 것과 똑같이 거짓이다.
    for s in parsed.signals:
        parts += [s.name, s.method, s.target, s.decision]
    parts.append(parsed.ha_check or "")
    generated = "\n".join(p for p in parts if p)

    # 금액의 근거는 **창업자가 준 예산 구간**이 정본이다. 종전에는 점주가 준 메뉴·리뷰가
    # 그 자리였는데, 대상이 바뀌면서 그 입력이 사라졌다(2026-09-17).
    # **상권 컨텍스트도 근거에 넣는다** — 행사가 컨텍스트에 합류(2026-08-06)하면서 행사
    # 요금·기간의 숫자가 거기 실린다. 빼면 실린 행사비를 인용한 것이 지어낸 금액으로
    # 잘못 걸린다. 대가로 컨텍스트의 금액을 가격처럼 쓰는 경우는 못 잡지만, 정상 인용을
    # 폐기하는 쪽이 더 나쁘다.
    allowed_text = " ".join([program_brief.claims_text(brief),
                             program_brief.allowed_prices_text(brief),
                             context or ""])
    source_text = f"{allowed_text} {brief.get('item', '')} {brief.get('category', '')}"

    return [
        *_check_unproven_evidence(generated),
        *_check_prices(generated, allowed_text),
        *_check_trend(generated, context),
        *_check_superlatives(generated, source_text),
        *_check_disparagement(generated),
        *_check_channel_balance(list(parsed.online)),
        *_check_rationales(plans),
        *_check_cited_events(list(parsed.offline), context),
        *_check_proposed_events(list(parsed.offline)),
        *_check_actors(list(parsed.offline)),
        *_check_budget_shares(list(parsed.online)),
        *_check_signals(list(parsed.signals)),
    ]


def check_district(parsed: LLMDistrictContents, context: str) -> list[HAFinding]:
    """상권 단위 온라인 카피 검증.

    상권 컨텍스트에는 가격 정보가 없다(키워드 빈도·업종 분포·트렌드뿐). 그래서 카피에
    나오는 금액은 근거가 컨텍스트에 있지 않는 한 지어낸 값이다.
    """
    # 줄바꿈으로 잇는 이유는 check_program 과 같다 — 카피 하나의 주장이 옆 카피의
    # 표현과 한 문장으로 읽히면 문장 단위 판정이 어긋난다.
    generated = "\n".join([*parsed.online_contents, parsed.ha_check or ""])
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
