"""파일럿 피드백 수집 — KPI③ (PMF) 의 유일한 입력 창구.

인증 필수다. NPS 는 **누가 답했는지가 지표의 일부**라, 익명 응답을 받으면 공개 데모
트래픽의 만족도가 B2B 파일럿의 PMF 로 둔갑한다(`services/usage` 가 익명을 안 세는
것과 같은 판단). 그래서 여기만 `get_current_principal` 을 쓴다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import Principal, get_current_principal
from app.models.feedback import PilotFeedback
from app.schemas.feedback import FeedbackIn, FeedbackOut

router = APIRouter()


@router.post("", response_model=FeedbackOut, status_code=201)
def submit_feedback(
    body: FeedbackIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> FeedbackOut:
    """응답 1건 저장. 같은 조직이 다시 답하면 **덮어쓰지 않고 새로 쌓는다.**

    히스토리를 지우면 "쓰다 보니 생각이 바뀌었다"를 못 본다. 지표는
    `services/pmf` 가 조직당 최신 1건만 골라 계산한다.
    """
    row = PilotFeedback(
        org_id=principal.org.id,
        user_id=principal.user.id if principal.user else None,
        nps_score=body.nps_score,
        would_pay=body.would_pay,
        comment=body.comment or "",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return FeedbackOut(id=row.id, org_id=row.org_id, nps_score=row.nps_score,
                       would_pay=row.would_pay, created_at=row.created_at)
