"""사용자 데이터용 DB 세션 (계정·조직·과금) — 분석 데이터(Gold)는 여전히 파일 직독이다.

docs/decision-infra-layer-2026-08-25.md §3-A 결정: DB 는 사용자 데이터 전용으로만
들인다. Gold 파이프라인·서빙 경로는 이 파일과 무관하게 그대로 둔다.

임포트 시점에는 커넥션을 열지 않는다(`create_engine` 은 지연 연결) — Postgres 가 없는
환경(로컬 파일 서빙만 하는 세션, CI 의 비-DB 테스트)에서도 앱이 정상 기동해야 한다.
실제 연결은 세션을 실제로 쓰는 요청에서만 일어난다.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI 의존성 — 요청 스코프 세션. 테스트에서 오버라이드 대상."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
