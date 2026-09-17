"""Program 입력 계약 ③층 — 검증 브리프(Brief) (2026-09-17).

    ① 자리(Site)     services/program_site                 — 우리 데이터
    ② 상권(Market)   services/marketing._district_context  — 우리 데이터
    ③ 검증 브리프    **이 모듈**                            — 창업자가 넣는다

## 앞의 두 층과 성격이 다르다

①·②는 우리가 가진 데이터에서 자동으로 나온다. ③은 **창업자가 넣는다** — 아직 해 보지
않은 아이템의 가설과 조건은 어떤 데이터에도 없기 때문이다. 그래서 이 층은 수집 과제가
아니라 계약·검증 과제다.

## 이 모듈이 닫는 것 — '있지도 않은 경험을 근거로 삼는 제안'

대상이 예비창업자·검증하려는 기창업자라 **이 자리에서의 장사 이력이 없다.** 그런데
생성물은 학습된 관성으로 "단골 고객에게", "방문 후기를 모아" 같은 말을 쓴다. 그 말이
전제하는 경험이 존재하지 않으므로 그대로 거짓이다.

종전(`program_venture`)에는 이 검사가 **개업예정일이 있을 때만** 켜졌다. 영업 중인
가게도 대상이라 그 둘을 갈라야 했기 때문이다. 이제 대상이 전부 미검증이므로 검사는
**항상 켜진다** — 갈라야 할 '영업 중'이 없다.

## 주장과 측정을 가른다 — 이게 이 모듈의 어려운 절반

검사를 넓게 걸면 정당한 산출물이 죽는다. 팝업의 핵심 지표가 **재방문율**이고, 가오픈의
목적 중 하나가 **후기 수집**이다. "재방문율을 센다"(측정)를 "단골 고객에게"(주장)와
같이 잡으면 이 트랙의 결론인 검증 지표가 통째로 폐기된다. 그래서 두 층으로 막는다:

1. 금칙어를 **경험을 전제하는 표현**으로만 좁힌다("단골 고객" ○ / "재방문" ✕)
2. 그 표현이 **측정 문장**에 있으면 면제한다("재방문 고객 비율을 집계한다")

2026-08-01 동명이지 정제에서 체험단 필터를 포기한 판단이 그대로 적용된다 — 자동 규칙을
세게 걸면 진짜 산출물까지 죽는다.

## 금액은 여기서만 절대액이다

출력의 `budget_share` 는 int 퍼센트라 절대액이 구조적으로 못 들어간다(§0-F). 예산의
절대액은 이 층에만 있고, 생성물이 그 범위를 인용하는 것은 정상이다 — 그래서
`allowed_prices_text()` 로 HA 의 `allowed_text` 에 합류시킨다. 넣지 않으면 창업자가 준
예산을 인용한 문장이 '지어낸 금액'으로 잘못 폐기된다.

표준 라이브러리만 쓴다 — 배포 의존성이 fastapi/pydantic 뿐이다.
"""
from __future__ import annotations

import datetime as _dt

from app.schemas.marketing import MODE_LABEL, STAGE_LABEL

# 아직 없는 경험을 **전제**하는 표현. 전부 "이미 우리 가게를 겪은 사람"이 있어야 성립한다.
#
# ⚠ 여기에 "재방문"·"후기"를 맨몸으로 넣지 않는다. 재방문율은 팝업의 핵심 지표이고
# 후기 수집은 가오픈의 목적이라, 그 둘을 잡으면 검증 지표가 통째로 죽는다. 잡아야 하는
# 것은 지표가 아니라 **이미 있다고 말하는 것**이다.
UNPROVEN_EVIDENCE = (
    "단골 고객", "단골고객", "단골 손님", "단골손님", "기존 고객", "기존고객",
    "재방문 고객", "재구매 고객", "우리 단골", "방문 후기에", "방문후기에",
    "다녀온 분", "먹어본 분", "이용해 본 분", "이용해본 분",
    "검증된 맛", "입증된 맛", "이미 입소문", "소문난 맛집",
)

# 위 표현이 **측정 문장**에 있으면 면제한다 — "재방문 고객 비율을 집계한다"는 주장이
# 아니라 지표다. 이 목록이 오탐을 끊는 자리다.
MEASUREMENT_MARKS = (
    "율", "비율", "지표", "측정", "집계", "센다", "세어", "카운트", "수집",
    "설문", "기록한다", "확인한다", "판정", "기준선", "목표선", "미만이면", "이상이면",
)


def _parse_date(s: str | None) -> _dt.date | None:
    if not s:
        return None
    try:
        return _dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def run_window(brief: dict | None) -> tuple[_dt.date, _dt.date] | None:
    """검증 기간 (시작일, 종료일). 시작일이나 기간이 없으면 None.

    종료일을 계산해 두는 이유는 오프라인 제안의 `timing` 이 기간 밖을 가리키는지
    사람이 대조할 수 있어야 하기 때문이다 — 3일짜리 팝업에 "둘째 달부터"는 말이 안 된다.
    """
    start = _parse_date((brief or {}).get("start_date"))
    days = (brief or {}).get("run_days")
    if start is None or not isinstance(days, int) or days <= 0:
        return None
    return start, start + _dt.timedelta(days=days - 1)


def budget_band(brief: dict | None) -> tuple[int, int] | None:
    """검증 기간 마케팅 예산 구간(원). 뒤집혀 들어오면 바로잡아 돌려준다."""
    b = brief or {}
    lo, hi = b.get("budget_krw_min"), b.get("budget_krw_max")
    if not isinstance(lo, int) or not isinstance(hi, int) or lo <= 0 or hi <= 0:
        return None
    return (lo, hi) if lo <= hi else (hi, lo)


def allowed_prices_text(brief: dict | None) -> str:
    """HA `allowed_text` 에 실을 금액 문자열 — 창업자가 준 예산은 인용해도 되는 금액이다."""
    band = budget_band(brief)
    return "" if band is None else f"{band[0]}원 {band[1]}원"


def claims_text(brief: dict | None) -> str:
    """창업자가 적은 주장(가설·차별점)을 allowed_text 조각으로.

    검증되지 않았지만 **창업자가 낸 것**이라 인용은 정상이다. 점주가 준 메뉴·리뷰를
    같은 등급으로 다루던 것과 같은 자리다.
    """
    b = brief or {}
    parts = [str(x) for x in (b.get("differentiators") or [])]
    for key in ("hypothesis", "target_customer", "item"):
        if b.get(key):
            parts.append(str(b[key]))
    return " ".join(parts)


def brief_context(brief: dict | None) -> str | None:
    """③층을 LLM 컨텍스트 한 덩이로. 브리프가 비면 None.

    ①자리·②상권과 **따로** 싣는다. 사실의 등급이 다르기 때문이다 — 앞의 둘은 우리가
    관측한 수치이고 이 층은 창업자의 계획과 주장이다. 한 덩어리로 합치면 생성물이
    근거의 출처를 섞어 인용한다.
    """
    b = brief or {}
    if not b:
        return None

    mode = MODE_LABEL.get(str(b.get("mode")), str(b.get("mode") or ""))
    stage = STAGE_LABEL.get(str(b.get("stage")), str(b.get("stage") or ""))

    lines = ["[검증 브리프 — 창업자가 제출한 입력. 계획과 주장이지 관측된 사실이 아니다]"]
    if b.get("item"):
        lines.append(f"- 아이템: {b['item']}")
    if b.get("category"):
        lines.append(f"- 업종: {b['category']}")
    if mode:
        lines.append(f"- 검증 방식: {mode}")
    if stage:
        lines.append(f"- 단계: {stage}")
    if b.get("hypothesis"):
        lines.append(f"- 검증 가설(이것이 맞는지 확인하려고 돈다): {b['hypothesis']}")
    if b.get("target_customer"):
        lines.append(f"- 목표 고객: {b['target_customer']}")

    window = run_window(b)
    if window:
        start, end = window
        lines.append(f"- 검증 기간: {start.isoformat()} ~ {end.isoformat()}"
                     f" ({b['run_days']}일). 제안의 시기는 이 안에 들어와야 한다.")
    elif b.get("start_date"):
        lines.append(f"- 검증 시작 예정일: {b['start_date']}")
    elif b.get("run_days"):
        lines.append(f"- 검증 기간: {b['run_days']}일 (시작일 미정)")

    band = budget_band(b)
    if band:
        lines.append(f"- 검증 기간 마케팅 예산: {band[0]:,}~{band[1]:,}원"
                     " (제안은 비율로만 하고, 절대액은 이 범위에서 파생한다)")
    if b.get("differentiators"):
        lines.append("- 내세울 차별점(창업자 주장, 검증된 사실 아님 — 이것이 통하는지가 검증 대상이다): "
                     + " · ".join(str(x) for x in b["differentiators"][:8]))
    if b.get("tier"):
        lines.append(f"- Posting 3-Tier 선택: {b['tier']}")

    lines.append("- ⚠ 이 자리에서 이 아이템으로 장사한 적이 **없다**. 단골·기존 고객·"
                 "방문 후기처럼 이미 쌓인 경험을 전제하는 제안은 사실이 아니다. "
                 "재방문율·후기 수집은 앞으로 **측정할 지표**로는 정상이다.")
    return "\n".join(lines)
