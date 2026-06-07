# SpaceOS Backend (FastAPI)

상권 디지털 트윈 API 서버. PostgreSQL/PostGIS + Redis + Celery.

## 실행

```bash
cd apps/backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

- API 문서: http://localhost:8000/docs
- 헬스체크: http://localhost:8000/health

## 테스트

```bash
pytest
```

## 구조

- `app/api/v1/` — 라우터 (buildings, districts, ai)
- `app/core/` — 설정 (config)
- `app/schemas/` — Pydantic 스키마
- `app/models/` — SQLAlchemy ORM (TODO)
- `app/services/` — 비즈니스 로직 (TODO)
