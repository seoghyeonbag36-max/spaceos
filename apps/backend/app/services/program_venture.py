"""Program 입력 계약 ③층 — 창업 계획(Venture) (2026-08-23).

`docs/feature-program.md` §0-B 가 정의한 3층 입력의 마지막 층이다.

    ① 자리(Site)      services/program_site        ✅ 08-23
    ② 상권(Market)    services/marketing._district_context  ✅
    ③ 창업계획(Venture) **이 모듈**                  ✅ 08-23

## 앞의 두 층과 성격이 다르다

①·②는 우리가 가진 데이터에서 자동으로 나온다. ③은 **기업이 넣는다** — 아직 없는
가게의 강점과 의도는 어떤 데이터에도 없기 때문이다. 그래서 이 층은 수집 과제가
아니라 계약·검증 과제다.

## 이 층이 닫는 것 — '방문 후기형 포스팅'

§0-B 설계원칙 1 이 지적한 증상은 리뷰가 없는 입력(=공실)에 "방문 후기형 포스팅"을
제안하는 것이었다. 08-23 오전에 스텁을 고쳐 증상은 눌렀지만, 판정 근거가
`reviews 가 비었는가` 라는 **추정**이었다. 리뷰를 아직 못 모은 영업 중인 가게도
똑같이 '개업 전'으로 오인된다.

③층의 `open_date` 가 있으면 그것이 **확정**된다:

    개업 전  = open_date 가 오늘보다 뒤   → 방문·후기·재방문을 전제하는 제안은 거짓
    영업 중  = open_date 가 오늘 이하

그래서 이 모듈은 컨텍스트 문자열만 만들지 않고 `is_pre_open()` 을 함께 낸다.
ha_guard 가 그걸로 개업 전 생성물의 방문 전제를 **위반으로 잡는다**.

## 금액은 여기서만 절대액이다

출력의 `budget_share` 는 int 퍼센트라 절대액이 구조적으로 못 들어간다(§0-F).
예산의 절대액은 이 층에만 있고, 생성물이 그 범위를 인용하는 것은 정상이다 —
그래서 `allowed_prices_text()` 로 HA 의 `allowed_text` 에 합류시킨다. 넣지 않으면
기업이 준 예산을 인용한 문장이 '지어낸 금액'으로 잘못 폐기된다(행사 요금을
컨텍스트에 넣어야 했던 2026-08-06 과 같은 이유).

표준 라이브러리만 쓴다 — 배포 의존성이 fastapi/pydantic 뿐이다.
"""
from __future__ import annotations

import datetime as _dt

# 개업 전 생성물이 말하면 거짓이 되는 표현. "방문 후기"처럼 이미 일어난 경험을
# 전제하는 말들이다. 개업 **후**에는 전부 정상이므로 pre_open 일 때만 본다.
PRE_OPEN_FORBIDDEN = (
    "방문 후기", "방문후기", "재방문", "단골", "리뷰 이벤트", "후기 이벤트",
    "다녀온", "먹어본", "이용해 본", "이용해본", "기존 고객", "재구매",
)


def _parse_date(s: str | None) -> _dt.date | None:
    if not s:
        return None
    try:
        return _dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def is_pre_open(venture: dict | None, today: _dt.date | None = None) -> bool | None:
    """개업 전인가. ③층이 없으면 **None** — "모른다"와 "아니다"를 가른다.

    None 을 돌려주는 것이 중요하다. False 로 뭉뚱그리면 ③층을 안 준 요청이
    '영업 중'으로 단정돼, 개업 전 검사가 조용히 꺼진 채로 통과한다.
    """
    d = _parse_date((venture or {}).get("open_date"))
    if d is None:
        return None
    return d > (today or _dt.date.today())


def budget_band(venture: dict | None) -> tuple[int, int] | None:
    """월 마케팅 예산 구간(원). 뒤집혀 들어오면 바로잡아 돌려준다."""
    v = venture or {}
    lo, hi = v.get("budget_krw_min"), v.get("budget_krw_max")
    if not isinstance(lo, int) or not isinstance(hi, int) or lo <= 0 or hi <= 0:
        return None
    return (lo, hi) if lo <= hi else (hi, lo)


def allowed_prices_text(venture: dict | None) -> str:
    """HA `allowed_text` 에 실을 금액 문자열 — 기업이 준 예산은 인용해도 되는 금액이다."""
    band = budget_band(venture)
    return "" if band is None else f"{band[0]}원 {band[1]}원"


def venture_context(venture: dict | None, today: _dt.date | None = None) -> str | None:
    """③층을 LLM 컨텍스트 한 덩이로. ③층이 없으면 None."""
    v = venture or {}
    if not v:
        return None
    lines = ["[창업 계획 — 기업이 제출한 입력]"]
    if v.get("industry"):
        lines.append(f"- 업종: {v['industry']}")
    if v.get("target_customer"):
        lines.append(f"- 목표 고객: {v['target_customer']}")
    band = budget_band(v)
    if band:
        lines.append(f"- 월 마케팅 예산: {band[0]:,}~{band[1]:,}원"
                     " (제안은 비율로만 하고, 절대액은 이 범위에서 파생한다)")
    pre = is_pre_open(v, today)
    if v.get("open_date"):
        state = "개업 전" if pre else "영업 중"
        lines.append(f"- 개업 예정일: {v['open_date']} ({state})")
    if pre:
        lines.append("- ⚠ 아직 문을 열지 않았다. 방문·후기·재방문·단골을 전제하는 제안은"
                     " 사실이 아니다. 공간·준비 과정·개업 예고를 소재로 삼는다.")
    if v.get("strengths"):
        lines.append("- 내세울 강점(기업 주장, 검증된 사실 아님): "
                     + " · ".join(str(x) for x in v["strengths"][:8]))
    if v.get("tier"):
        lines.append(f"- Posting 3-Tier 선택: {v['tier']}")
    return "\n".join(lines) if len(lines) > 1 else None


def strengths_text(venture: dict | None) -> str:
    """강점을 allowed_text 조각으로 — 리뷰·메뉴와 같은 등급(점주/기업 제공)이다."""
    return " ".join(str(x) for x in (venture or {}).get("strengths") or [])
