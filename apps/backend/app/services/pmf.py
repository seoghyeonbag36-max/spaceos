"""PMF 지표 계산 — KPI③ 의 `NPS 30+` · `유료 전환 의향 30%+`.

## NPS 를 표준대로 센다

추천지수 = 추천자 비율(9~10) − 비추천자 비율(0~6). 중립(7~8)은 분모에만 들어간다.
−100~+100 범위다. 평균 점수로 바꾸지 않는다 — 벤치마크와 비교가 끊긴다.

## 조직당 최신 1건

같은 조직이 여러 번 답하면 기록은 다 남기되 **최신 것만 센다.** 응답 수가 아니라
조직 수가 표본이다 — 한 조직이 열 번 답해서 지표가 흔들리면 그건 PMF 신호가 아니다.

## 표본이 적으면 판정하지 않는다

파일럿 목표가 5~10건이라 n 은 애초에 작다. n=3 에서 나온 NPS 는 한 명이 바뀌면
±33 이 움직인다. `MIN_RESPONSES` 미만이면 `verdict: "표본부족"` 으로 물러난다 —
KPI 규칙 2(불확실성 없이 '달성'이라 적지 않는다)를 계산기 안에 박아 둔 것이다.
지연 계측기(`services/latency`)와 같은 처리다.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feedback import PilotFeedback

# NPS 목표(KPI③). 바꾸려면 CLAUDE.md §KPI Priorities 와 함께 바꾼다.
NPS_TARGET = 30.0
# 유료 전환 의향 목표(%).
PAY_TARGET_PCT = 30.0
# 이 수 미만이면 판정하지 않는다. 파일럿 목표 하한(5)에 맞췄다 — 그보다 적으면
# 애초에 KPI③ 을 논할 표본이 아니다.
MIN_RESPONSES = 5

PROMOTER_MIN = 9      # 9~10 추천자
DETRACTOR_MAX = 6     # 0~6 비추천자


def _latest_per_org(db: Session) -> list[PilotFeedback]:
    """조직별 최신 응답. 표본 단위가 응답이 아니라 **조직**이다."""
    rows = db.execute(
        select(PilotFeedback).order_by(PilotFeedback.created_at.desc())
    ).scalars().all()
    seen: set[str] = set()
    latest: list[PilotFeedback] = []
    for row in rows:
        if row.org_id in seen:
            continue
        seen.add(row.org_id)
        latest.append(row)
    return latest


def pmf_summary(db: Session) -> dict:
    """NPS + 유료 전환 의향. 읽기만 한다."""
    latest = _latest_per_org(db)
    n = len(latest)
    if n == 0:
        return {
            "n_orgs": 0, "nps": None, "would_pay_pct": None,
            "nps_target": NPS_TARGET, "pay_target_pct": PAY_TARGET_PCT,
            "min_responses": MIN_RESPONSES,
            "verdict": "표본부족",
            "note": ("응답 0건. 계측 배선은 섰지만 **배선 100% 는 파일럿 0건과 "
                     "양립한다** — 이 값은 실적이지 배선이 아니다."),
        }

    promoters = sum(1 for r in latest if r.nps_score >= PROMOTER_MIN)
    detractors = sum(1 for r in latest if r.nps_score <= DETRACTOR_MAX)
    nps = (promoters - detractors) / n * 100.0
    pay_yes = sum(1 for r in latest if r.would_pay == "yes")
    pay_pct = pay_yes / n * 100.0

    enough = n >= MIN_RESPONSES
    if not enough:
        verdict = "표본부족"
    elif nps >= NPS_TARGET and pay_pct >= PAY_TARGET_PCT:
        verdict = "충족"
    else:
        verdict = "미달"

    return {
        "n_orgs": n,
        "nps": round(nps, 1),
        "promoters": promoters,
        "passives": n - promoters - detractors,
        "detractors": detractors,
        "would_pay_pct": round(pay_pct, 1),
        "would_pay_yes": pay_yes,
        "nps_target": NPS_TARGET,
        "pay_target_pct": PAY_TARGET_PCT,
        "min_responses": MIN_RESPONSES,
        "verdict": verdict,
        # n 이 작을 때 한 응답이 지표를 얼마나 흔드는지 숫자로 보여 준다.
        # "NPS 40 달성" 이 조직 5곳에서 나온 값이면 한 곳이 바뀌어 20 이 될 수 있다.
        "one_response_swing_nps": round(200.0 / n, 1),
        "note": ("조직당 최신 1건만 센다. 표본 단위는 응답이 아니라 조직이다. "
                 f"n={n} 에서는 한 조직이 추천자↔비추천자로 바뀌면 NPS 가 "
                 f"{round(200.0 / n, 1)}포인트 움직인다."),
    }
