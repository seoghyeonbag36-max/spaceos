# Memory — SpaceOS Project

## Me
**sh.pac** (seoghyeonbag36@gmail.com) — SpaceOS 창업자 겸 디지털 트윈 AI/IT 개발자. 지역 상권의 리뷰 데이터와 공실 히스토리를 결합해 물리적 상권을 디지털 트윈 SaaS로 플랫폼화하는 프로젝트를 진행 중.

## Project Identity
**SpaceOS** — 물리적 상권의 디지털 트윈 플랫폼. "Place의 Platform화" 가설 검증. 18~24개월 내 네이버/카카오/직방 대상 M&A Exit 목표.

## PPPP Framework (핵심 4기능)
| 기능 | 전환 | 의미 |
|------|------|------|
| **Platform** | Place → Platform | 상권 AI 추천 엔진 (각 상권을 하나의 플랫폼화) |
| **Page** | Product/Price → Page | 공실 히트맵 + 3D 디지털 트윈 (어떤 업장이 어디에) |
| **Posting** | Promotion → Posting | 입점 솔루션 — **외부 AI 창업 코파일럿 연동**(어댑터) + 3-Tier 비용-효용 폴백 |
| **Program** | Promotion → Program | 마케팅 자동화 — **대상은 Platform(상권) 내 빈 Page(공실 건물)에 Posting(창업)할 기업**이다. 그 기업에게 온/오프라인으로 어떻게 마케팅·홍보할지 알려준다 (2026-08-16 대상 재정의) |

## Active Projects
| 이름 | 내용 |
|------|------|
| **PPPP 6개월 로드맵** | 2026-05-20 완성. MVP + M1~M6 로드맵 + 바이브 코딩 방법론 |
| **거점** | **서울 54거점 전부 Tier1**(건축물대장 실측, 08-17 완주). PoC 출발점은 신사동 가로수길 — 거점 수는 `data/gold/*/coverage.json` 의 `tier` 를 세는 것이 단일 기준이다 |
| **B2B 파일럿** | 6개월차 5~10건 목표 (프랜차이즈 본사·자산운용사·지자체) |

→ 상세: memory/projects/

## Tech Stack (확정)
- **FE**: React + TypeScript + Three.js/@react-three/fiber + **네이버 지도**(`lib/naverMap.ts`) + Tailwind
  - `mapbox-gl` 은 **제거됐다**(2026-08-25 커밋 1979bb4 · package.json·lock 모두 정리 완료). 베이스맵은 네이버뿐이니 다시 끌어오지 말 것
- **BE**: FastAPI + PostgreSQL/PostGIS + Redis + Celery
- **ML**: PyTorch + PyTorch Geometric (GNN) + LSTM + MLflow + LangChain
- **Data**: Airflow + Selenium/Playwright + Bronze/Silver/Gold 3계층
- **Infra**: AWS (S3/EC2/RDS/EKS) + Docker + GitHub Actions
- **바이브 코딩**: Cursor (Composer/Agent) + Claude Code (CLI) + Copilot 보조

→ 상세: memory/context/tech-stack.md

## Key Terms
| 용어 | 의미 |
|------|------|
| **PPPP** | Platform·Page·Posting·Program (디지털 4P 프레임워크) |
| **바이브 코딩** | 자연어 PRD → AI 코드 생성 → 검증 사이클 (Cursor + Claude Code) |
| **거점 상권** | MVP 검증할 1개 상권. 1순위 신사동 가로수길, 2순위 홍대·연남동 |
| **Bronze/Silver/Gold** | 데이터 레이크 3계층 (원본/정제/분석용) |
| **GNN** | Graph Neural Network — 업종 간 시너지/잠식 분석 |
| **LSTM** | 시계열 매출·공실 예측 모델 |
| **DaaS** | Data as a Service — 월 500만원 B2B 구독 모델 |
| **Humanistic Authority** | 균형·공생·공감 3대 지표 (브랜드 차별화) |

→ 전체 용어집: memory/glossary.md

## KPI Priorities (사용자 선택)
1. **기술 완성도** — MVP 데모 가능, AI 정확도 70%+, 3D 트윈 로딩 3초 이내
2. **고객 검증(PMF)** — B2B 파일럿 5~10건, 유료 전환 의향 30%+, NPS 30+

## Preferences
- 결과물: **Word(.docx)** 선호 (표·그래프 포함, 핵심 요약 + 상세 분석)
- 한글 문서 작성 시: **폰트 임베딩 필수** (Noto Sans KR subset → odttf로 obfuscate)
- 데이터 기반 작성, 추측 최소화, 논리적 구조 유지
- 바이브 코딩 도구는 **Cursor + Claude Code** 조합 우선
- 응답 언어: 한국어

## Critical Technical Notes
- **한글 docx 작성**: "맑은 고딕"/"Noto Sans KR" 폰트명만 지정하면 Cowork 프리뷰에서 박스(□)로 깨짐. 반드시 OOXML 폰트 임베딩 필요. → memory/context/docx-korean-fonts.md
- **docx-js 단락 테두리 순서**: top/left/bottom/right 4면 모두 지정하면 OOXML 스키마 위반. top+bottom만 사용 권장.
- **거점 선정 기준**: 데이터 가용성(공공데이터·SNS) + B2B 잠재 고객 접근성

## Recent Deliverables
- `SpaceOS_PPPP_6Month_Vibe_Roadmap.docx` (2026-05-20) — 본 로드맵
- `SpaceOS_6Month_Technical_Roadmap.docx` — 기술 로드맵 (이전)

---

## Development (Claude Code) — 코드베이스 가이드

이 저장소는 모노레포로 구성되어 있다. 코드 작업 시 아래 구조와 규칙을 따른다.

### 작업 루트 = 이 디렉터리 (2026-08-02 고정)
`.git` 은 여기(`spaceos/`)에만 있다. **상위 폴더(`../`)에서는 아무것도 만들지 않는다.**
예전에 상위에 `apps/` · `data/` · `ml/` · `src/` 가 git 밖의 낡은 사본으로 남아 있어
거기서 연 도구가 헛일을 할 수 있었다 → `../archive/root-skeleton-2026-08-02/` 로 치웠다.
경위는 `../README.md`, 재발 방지 가드는 `../CLAUDE.md` · `../AGENTS.md`.

### 두 에이전트 병행 (Claude Code + Codex)
- **Claude Code**(여기): 설계·근거 판단·다파일 리팩터. 브랜치 `feat/*`
- **Codex**: 명세가 확정된 실행. 브랜치 `chore/*` · `fix/*`. 지침은 [AGENTS.md](AGENTS.md)
- Codex 로 내보낼 때는 **대상 파일 / 입력 소스와 출처 표기 / 통과 조건(테스트 이름) / 금지 사항**
  4개를 채워서 보낸다. 하나라도 못 채우면 그 작업은 Claude Code 몫이다
- Codex 산출물은 머지 전 `/verify` — 특히 **값이 새로 채워진 곳**

### 디렉토리 구조
```
apps/backend     FastAPI API 서버 (Python 3.11)
apps/frontend    React + TypeScript + Vite (3D 디지털 트윈 UI)
ml               PyTorch LSTM(공실 예측) / GNN(업종 추천) + MLflow
data             Airflow DAG + 크롤러 + Bronze/Silver/Gold 레이어
infra            docker-compose / Dockerfile / k8s / GitHub Actions
docs             설계 문서
memory           프로젝트 메모리 (전략·용어집 — 기존 유지)
```

### 자주 쓰는 명령어
```bash
# Backend
cd apps/backend && pip install -r requirements.txt && uvicorn app.main:app --reload
cd apps/backend && pytest                 # 테스트

# 계정층 DB 마이그레이션(Alembic, 2026-08-26 도입) — 분석 Gold 파이프라인과는 무관한 별도 DB
cd apps/backend && alembic upgrade head    # DATABASE_URL 은 .env(app.core.config.settings) 기준

# Frontend
cd apps/frontend && npm install && npm run dev
cd apps/frontend && npm run build         # 타입체크 + 빌드

# 전체 로컬 스택 (DB + Redis + Backend)
docker compose -f infra/docker/docker-compose.yml up

# 배포 — main 에 푸시하면 GitHub Actions 가 Cloud Run 으로 낸다(테스트→빌드→배포→검증).
# 수동 배포·좌표·무료 한도의 경계는 docs/deploy-cloud-run.md 참조.
#   프로덕션: https://spaceos-twin.web.app  (Firebase Hosting → Cloud Run)
# ⚠ Vercel 은 2026-08-28 프로덕션에서 내려왔다(무료 플랜이 상업적 사용 금지).
#   `vercel --prod` 를 쓰지 말 것 — docs/deploy-vercel.md 는 이력으로만 남겼다.
git push origin main

# ML 골격 확인
cd ml && python models/lstm/vacancy_lstm.py

# GNN 재학습 (체크포인트 재개 내장) — 스레드 1개 · UTF-8 필수
OMP_NUM_THREADS=1 PYTHONIOENCODING=utf-8 python -u -m ml.training.train_gnn --epochs 600 --patience 80

# 진행률·게이트 — 문서가 아니라 산출물을 센다
python scripts/pppp_status.py

# 건축HUB 수집 전 프리플라이트 (쿼터·전원·시도이력)
python scripts/quota_preflight.py
```

⚠ **로그를 파일로 리다이렉트할 때 `PYTHONIOENCODING=utf-8`** — Windows 기본 cp949 에는
`—`(em dash) 가 없어 학습·수집 스크립트가 UnicodeEncodeError 로 죽는다(08-19 실측).

### 코드 작성 규칙
- **언어**: 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- **Backend**: FastAPI 라우터는 `app/api/v1/`에 도메인별로 분리. 스키마는 `app/schemas/`, DB 모델은 `app/models/`, 비즈니스 로직은 `app/services/`. 타입 힌트 필수.
- **Frontend**: 함수형 컴포넌트 + 훅. API 호출은 `src/lib/api.ts`로 일원화. `@/` 경로 별칭 사용.
- **ML**: 모델은 `ml/models/`, 학습은 `ml/training/`, 서빙 래퍼는 `ml/inference/`. 실험은 MLflow로 추적.
- **Data**: 모든 파이프라인은 Bronze→Silver→Gold 3계층 흐름을 지킨다. 크롤러는 `data/crawlers/`.
- **API 설계**: 엔드포인트는 `/api/v1/...` 규약 (buildings, commercial-districts, ai, heatmap, marketing).
- 데이터 기반·추측 최소화 원칙은 코드에도 적용 — 더미 데이터에는 반드시 `TODO` 주석으로 실제 연동 지점을 명시.

### 성능 목표 (참고)
AI 공실 예측 정확도 70%+(Phase1), 3D 맵 로딩 <3초, API p95 <200ms.
