"""분석 API 공통 의존성 — 신원 확인(선택)과 사용량 기록을 한 자리에 둔다.

라우터마다 붙이지 않고 `router.py` 의 `include_router(dependencies=[...])` 한 곳에서
거는 이유: 엔드포인트별로 달면 **새로 추가된 엔드포인트가 조용히 빠진다.** 이 저장소가
반복해 잡아 온 양식(게이트는 100% 인데 산출물이 제품에 안 닿는다)과 같은 모양이라,
빠질 수 없는 자리에 건다.
"""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import Principal, get_optional_principal
from app.services import usage


def track_access(
    request: Request,
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> Principal | None:
    """호출자를 밝히고(있으면) 사용량을 남긴다. 익명이면 둘 다 건너뛴다.

    반환값을 쓰는 엔드포인트는 아직 없다 — 지금은 기록이 목적이다. 다만 의존성으로
    두면 나중에 조직별 스코핑(예: 파일럿에게 자기 거점만 보이기)을 붙일 때
    시그니처를 안 바꾸고 `Depends(track_access)` 를 받아 쓰면 된다.
    """
    usage.record_access(db, principal, request.url.path)
    return principal
