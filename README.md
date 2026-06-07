# SpaceOS — 상권 디지털 트윈 플랫폼

물리적 상권의 리뷰 데이터와 공실 히스토리를 결합해 "Place → Platform"으로 전환하는 디지털 트윈 SaaS. 모노레포로 구성되어 있으며 Claude Code 기반 개발을 전제로 셋업되어 있다.

## 구조

| 경로 | 내용 | 스택 |
|------|------|------|
| `apps/backend` | API 서버 | FastAPI · PostgreSQL/PostGIS · Redis · Celery |
| `apps/frontend` | 3D 디지털 트윈 UI | React · TypeScript · Vite · Three.js · Mapbox GL |
| `ml` | AI 모델 | PyTorch · LSTM(공실 예측) · GNN(업종 추천) · MLflow |
| `data` | ETL·크롤링 | Airflow · Playwright · Bronze/Silver/Gold |
| `infra` | 배포 | Docker · k8s · GitHub Actions |
| `docs` · `memory` | 문서·전략 메모리 | — | 

## 빠른 시작

```bash
# 1) git 초기화 (Windows 터미널에서 — 아래 "Git" 참고)
git init && git add -A && git commit -m "init: SpaceOS 모노레포 골격"

# 2) Backend
cd apps/backend && pip install -r requirements.txt && uvicorn app.main:app --reload
#    → http://localhost:8000/docs

# 3) Frontend
cd apps/frontend && npm install && npm run dev
#    → http://localhost:5173

# 4) 전체 로컬 스택 (DB + Redis + Backend)
docker compose -f infra/docker/docker-compose.yml up
```

## Claude Code

- `CLAUDE.md` — 프로젝트 컨텍스트 + 코드베이스 가이드 (자동 로드)
- `.claude/settings.json` — 권한 설정
- `.claude/commands/` — 슬래시 커맨드: `/backend-dev`, `/frontend-dev`, `/ml-train`

## Git

이 폴더는 아직 git 저장소가 아니다. 본인 Windows 터미널(PowerShell)에서 아래를 실행해 초기화한다 (`.gitignore`는 이미 준비됨):

```powershell
cd C:\Users\USER\Documents\Claude\Projects\SpaceOS
git init
git add -A
git commit -m "init: SpaceOS 모노레포 골격"
```
