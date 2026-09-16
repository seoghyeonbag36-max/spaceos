"""파일럿 피드백 — KPI③ (PMF) 의 `NPS 30+` · `유료 전환 의향 30%+` 를 재는 원천.

## 왜 필요한가

2026-09-16 에 세어 보니 이 두 목표를 재는 코드가 **저장소 전체에 0줄**이었다.
`usage.record_access` 가 세는 것은 `active_orgs`(파일럿이 살아 있나) 하나뿐이고,
"그래서 그들이 돈을 낼 생각인가 / 남에게 권할 생각인가"는 물어본 적도 담을 곳도
없었다. KPI 규칙 4(계측기 없는 목표는 KPI 가 아니다)의 마지막 구멍이다.

## 익명은 받지 않는다

NPS 는 **누가 답했는지가 지표의 일부**다. 공개 데모 트래픽의 만족도는 B2B 파일럿의
PMF 가 아니고, 익명을 받으면 한 사람이 열 번 답해도 막을 수 없다. `usage` 가 익명
요청을 세지 않는 것과 같은 판단이다 — 못 세는 게 아니라 **세지 않는 것**이다.

조직당 최신 1건만 지표에 쓴다(아래 `pmf_summary`). 같은 조직이 여러 번 답하면
기록은 다 남기되 최신 것만 센다 — 히스토리를 지우면 변화를 못 본다.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.auth import _now, _uuid


class PilotFeedback(Base):
    """파일럿 응답 1건. 조직·사용자에 묶인다."""

    __tablename__ = "pilot_feedback"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # 0~10. NPS 표준 척도 그대로 둔다 — 5점 척도로 바꾸면 업계 벤치마크와 비교가 끊긴다.
    nps_score: Mapped[int] = mapped_column(Integer)
    # "yes" | "maybe" | "no". 유료 전환 **의향**이지 계약이 아니다 — 이름에 남겨 둔다.
    would_pay: Mapped[str] = mapped_column(String(10))
    comment: Mapped[str] = mapped_column(String(2000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
