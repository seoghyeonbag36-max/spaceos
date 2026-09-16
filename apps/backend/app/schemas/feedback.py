"""파일럿 피드백 스키마 — KPI③ 입력 계약."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FeedbackIn(BaseModel):
    # 0~10 NPS 표준 척도. 범위를 스키마에서 막아야 계산기가 방어 코드를 안 들고 다닌다.
    nps_score: int = Field(ge=0, le=10,
                           description="0~10. 9~10 추천자 · 7~8 중립 · 0~6 비추천자")
    # 계약이 아니라 **의향**이다. 이름에 그대로 남긴다.
    would_pay: Literal["yes", "maybe", "no"]
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackOut(BaseModel):
    id: str
    org_id: str
    nps_score: int
    would_pay: str
    created_at: datetime
