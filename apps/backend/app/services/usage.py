"""분석 API 사용량 기록 — KPI② (PMF) 를 재는 원천 데이터.

## 왜 필요한가

`docs/README.md` §진행률 이 적어 둔 대로 **KPI② PMF 를 재는 게이트가 0개**다. PPPP
진행률 22게이트는 전부 분석 파이프라인(KPI①)만 센다. 파일럿을 5~10건 받기로 해 놓고
"그 파일럿이 실제로 무엇을 얼마나 썼나"를 셀 자리가 없으면, 유료 전환 의향 30%·NPS 30
같은 목표는 **관측 없이 선언만 남는다** — 이 저장소가 반복해 잡아 온 실패 양식이다.

## 설계 — 익명은 안 센다, 못 세는 게 아니라 세지 않는 것이다

- **익명 요청은 기록하지 않는다.** 공개 데모 트래픽은 파일럿 사용량이 아니고, 익명까지
  세면 DB 를 안 쓰던 분석 API 가 매 요청 DB 를 때린다. `get_optional_principal` 이
  자격증명 없을 때 DB 를 건드리지 않는 것과 짝이다.
- **기록 실패가 요청을 깨뜨리지 않는다.** 사용량 로깅 때문에 분석 API 가 500 을 내면
  주객이 전도된다. 다만 조용히 삼키지 않는다 — `record_access` 는 성공 여부를
  돌려주고, `/admin/usage` 가 "기록이 실제로 쌓이고 있나"를 드러낸다.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import Principal
from app.models.auth import AuditLog

logger = logging.getLogger(__name__)

# AuditLog.action 접두사 — 계정 이벤트(signup/login)와 한 표에 살지만 구분은 된다.
ACCESS_PREFIX = "access:"


def record_access(db: Session, principal: Principal | None, path: str) -> bool:
    """접근 1건 기록. 익명이면 아무것도 안 하고 False.

    반환값은 "기록됐나"이지 "요청이 성공했나"가 아니다.
    """
    if principal is None:
        return False
    try:
        db.add(AuditLog(
            org_id=principal.org.id,
            user_id=principal.user.id if principal.user else None,
            action=f"{ACCESS_PREFIX}{principal.via}",
            detail=path[:500],
        ))
        db.commit()
        return True
    except SQLAlchemyError:
        db.rollback()
        # 로깅 실패로 분석 응답을 깨뜨리지 않는다. 대신 흔적은 남긴다 —
        # /admin/usage 의 카운트가 0 인 채로 있으면 여기가 계속 실패하는 것이다.
        logger.warning("사용량 기록 실패 (path=%s)", path, exc_info=True)
        return False


def usage_summary(db: Session, days: int = 30) -> dict:
    """조직별 접근 요약 — 파일럿 활성도를 보는 최소 지표.

    `active_orgs` 가 곧 "살아 있는 파일럿 수"의 하한이다(KPI② 목표 5~10건).
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(AuditLog.org_id, func.count(AuditLog.id))
        .where(AuditLog.action.like(f"{ACCESS_PREFIX}%"))
        .where(AuditLog.created_at >= since)
        .group_by(AuditLog.org_id)
    ).all()
    by_org = {org_id: int(n) for org_id, n in rows if org_id}
    return {
        "window_days": days,
        "active_orgs": len(by_org),
        "total_accesses": sum(by_org.values()),
        "by_org": by_org,
    }
