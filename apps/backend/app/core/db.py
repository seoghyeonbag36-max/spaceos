"""사용자 데이터용 DB 세션 (계정·조직·과금) — 분석 데이터(Gold)는 여전히 파일 직독이다.

docs/decision-infra-layer-2026-08-25.md §3-A 결정: DB 는 사용자 데이터 전용으로만
들인다. Gold 파이프라인·서빙 경로는 이 파일과 무관하게 그대로 둔다.

임포트 시점에는 **엔진도 만들지 않는다.** Postgres 가 없는 환경(로컬 파일 서빙만 하는
세션, CI 의 비-DB 테스트, DB 를 아직 안 붙인 배포)에서도 앱이 정상 기동해야 한다.

⚠ 2026-08-27 — 이 파일은 원래 모듈 최상위에서 `create_engine()` 을 부르면서 "지연
연결이라 괜찮다"고 적어 뒀다. **절반만 맞았다.** 커넥션은 안 열지만 `create_engine` 은
그 자리에서 **DBAPI 드라이버 모듈을 import** 한다(`postgresql://` → `import psycopg2`).
그래서 psycopg2 가 없는 배포에서는 앱이 통째로 뜨지 않았다 — 분석 API 까지 전부.
`test_usage_tracking.py` 가 "연결 불가능한 DB 를 물려도 익명 요청이 200" 을 고정하고
있었지만, 그 테스트 환경에는 psycopg2 가 설치돼 있어서 이 구멍을 볼 수 없었다.
지금은 엔진 생성 자체를 첫 사용 시점으로 미뤄 문서가 주장하던 성질을 실제로 만든다.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

_engine: Engine | None = None


def get_engine() -> Engine:
    """엔진을 처음 필요할 때 만든다(프로세스당 1회).

    DBAPI 드라이버 import 가 여기서 일어난다 — 그래서 이 함수를 부르지 않는 요청은
    드라이버가 설치돼 있지 않아도 된다.
    """
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    return _engine


class _LazyBindSession(Session):
    """실제로 질의할 때까지 엔진을 만들지 않는 세션.

    `get_bind` 는 SQLAlchemy 가 커넥션이 필요한 순간에만 부르는 공개 훅이다. 세션을
    **만드는** 것만으로는 안 불린다 — 익명 요청이 `get_db` 를 거쳐도 엔진·드라이버가
    필요 없어지는 지점이 여기다(security.get_optional_principal 이 주장하는 성질).
    """

    def get_bind(self, *args, **kwargs) -> Engine:      # type: ignore[override]
        return get_engine()


SessionLocal = sessionmaker(class_=_LazyBindSession, autoflush=False,
                            autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI 의존성 — 요청 스코프 세션. 테스트에서 오버라이드 대상."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
