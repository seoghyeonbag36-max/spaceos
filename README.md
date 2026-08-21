# SpaceOS — 상권 디지털 트윈 플랫폼

물리적 상권의 리뷰 데이터와 공실 히스토리를 결합해 "Place → Platform"으로 전환하는 디지털 트윈 SaaS. 모노레포로 구성되어 있으며 Claude Code 기반 개발을 전제로 셋업되어 있다.

## 구조

| 경로 | 내용 | 스택 |
|------|------|------|
| `apps/backend` | API 서버 | FastAPI · PostgreSQL/PostGIS · Redis · Celery |
| `apps/frontend` | 3D 디지털 트윈 UI | React · TypeScript · Vite · Three.js/@react-three/fiber · **네이버 지도**(`lib/naverMap.ts`) |
| `ml` | AI 모델 | PyTorch · LSTM(공실 예측) · GNN(업종 추천) · MLflow |
| `data` | ETL·크롤링 | Airflow · Playwright · Bronze/Silver/Gold |
| `infra` | 배포 | Docker · k8s · GitHub Actions |
| `docs` · `memory` | 문서·전략 메모리 | — | 

## 팀원 온보딩

저장소를 클론하고 API 키만 채우면 바로 개발 환경이 완성된다.

```bash
git clone https://github.com/seoghyeonbag36-max/spaceos.git && cd spaceos
cp data/.env.example data/.env
cp apps/backend/.env.example apps/backend/.env
cp apps/frontend/.env.example apps/frontend/.env
# → 공유 비밀번호 관리자(Bitwarden 컬렉션 "SpaceOS API Keys")에서 값 복사해 각 .env 채우기
```

이후 아래 [빠른 시작](#빠른-시작)으로 실행한다. 각 키가 어디에 쓰이는지는 [docs/api-keys-and-specs.md](docs/api-keys-and-specs.md) 참조.

### 키 공유 규칙 (🔒 비밀값은 GitHub에 올리지 않는다)

- **실제 키 값**은 GitHub이 아니라 **공유 비밀번호 관리자**(Bitwarden 무료 조직 컬렉션 `SpaceOS API Keys`)로만 공유한다. `.env`는 `.gitignore` 처리되어 커밋되지 않는다.
- **키가 바뀌면** → Bitwarden 항목만 갱신하고 팀원에게 알린다. `.env.example`은 슬롯(구조)만 담고 값은 비워 둔다.
- **새 키가 생기면** → `.env.example`에 **빈 슬롯을 추가해 커밋**하고(값 없음), 실제 값은 Bitwarden에 넣는다.
- 유일한 유료 키 `LLM_API_KEY`(Anthropic)는 **사용량 알림**을 설정한다.
- 협업은 **브랜치 + Pull Request**로 진행한다(`main` 직접 커밋 지양).

## 빠른 시작

```bash
# 1) Backend
cd apps/backend && pip install -r requirements.txt && uvicorn app.main:app --reload
#    → http://localhost:8000/docs

# 2) Frontend
cd apps/frontend && npm install && npm run dev
#    → http://localhost:5173  (Vite 프록시가 8000 으로 넘긴다)

# 3) 전체 로컬 스택 (DB + Redis + Backend)
docker compose -f infra/docker/docker-compose.yml up

# 4) 배포 — 프론트 정적 + FastAPI 서버리스 단일 Vercel 프로젝트
vercel --prod        # 상세: docs/deploy-vercel.md
```

### 지금 어디까지 와 있나

숫자를 이 파일에서 읽지 말 것 — 문서는 적은 날의 값이라 낡는다. 산출물을 세는 스크립트가
단일 기준이다.

```bash
python scripts/pppp_status.py     # 트랙별 진행률 + 게이트 ([자동] = 산출물 실측, [선언] = 사람이 적은 값)
```

거점은 **54곳**(전부 Tier1 = 건축물대장 실측)이며 `data/gold/*/coverage.json` 의 `tier` 가
그 근거다. 트랙별 상세는 [docs/README.md](docs/README.md) 에서 시작한다.

## Claude Code

- `CLAUDE.md` — 프로젝트 컨텍스트 + 코드베이스 가이드 (자동 로드)
- `.claude/settings.json` — 권한 설정
- `.claude/commands/` — 슬래시 커맨드
  - 트랙 전환: `/platform` `/page` `/posting` `/program` `/design`
  - 진행·검증: `/pppp-status` `/verify` `/quota`(건축HUB 일일 쿼터 소진)
  - 개발: `/backend-dev` `/frontend-dev` `/ml-train` `/district-map` `/director`
- `AGENTS.md` — Codex 병행 지침 (Claude Code 는 `feat/*`, Codex 는 `chore/*`·`fix/*`)

## Git

원격 저장소는 [github.com/seoghyeonbag36-max/spaceos](https://github.com/seoghyeonbag36-max/spaceos) (`main`)이다. 신규 팀원은 위 [팀원 온보딩](#팀원-온보딩)의 `git clone`으로 시작한다. 기여는 브랜치에서 작업 후 Pull Request로 병합한다.

⚠ `.git` 은 **이 디렉터리에만** 있다. 상위 폴더(`../`)에는 2026-08-02 에 치운 낡은 사본의
흔적이 있으니 거기서 파일을 만들지 않는다 — 경위는 [../README.md](../README.md).
