---
description: Backend(FastAPI) 기능 개발 — 라우터/스키마/서비스 추가
---

SpaceOS 백엔드에 새 기능을 추가한다. 대상: $ARGUMENTS

규칙:
1. 라우터는 `apps/backend/app/api/v1/`에 도메인별로 추가하고 `router.py`에 등록.
2. 요청/응답은 `apps/backend/app/schemas/`에 Pydantic 모델로 정의.
3. DB 접근은 `app/models/`(SQLAlchemy) + `app/services/`로 분리. PostGIS 공간쿼리 활용.
4. 더미 데이터에는 `TODO`로 실제 연동 지점 명시.
5. 작업 후 `cd apps/backend && pytest`로 검증하고 테스트를 추가.
