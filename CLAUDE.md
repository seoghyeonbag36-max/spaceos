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
| **Posting** | Promotion → Posting | 입점 솔루션 (고급화/가성비/기능중심 비용-효용 분석) |
| **Program** | Promotion → Program | 온/오프라인 마케팅 자동화 (LLM 콘텐츠 + 행사 추천) |

## Active Projects
| 이름 | 내용 |
|------|------|
| **PPPP 6개월 로드맵** | 2026-05-20 완성. MVP + M1~M6 로드맵 + 바이브 코딩 방법론 |
| **MVP 거점** | 고양시 라페스타·웨스턴돔(1순위) OR 홍대·연남동 — M1 1주차 확정 예정 |
| **B2B 파일럿** | 6개월차 5~10건 목표 (프랜차이즈 본사·자산운용사·지자체) |

→ 상세: memory/projects/

## Tech Stack (확정)
- **FE**: React + TypeScript + Three.js/@react-three/fiber + Mapbox GL + Tailwind
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
| **거점 상권** | MVP 검증할 1개 상권. 1순위 라페스타, 2순위 홍대·연남동 |
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
- `SpaceOS_Goyang_Roadmap_v1.docx` — 고양시 로드맵 v1 (이전)

---

## Development (Claude Code) — 코드베이스 가이드

이 저장소는 모노레포로 구성되어 있다. 코드 작업 시 아래 구조와 규칙을 따른다.

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

# Frontend
cd apps/frontend && npm install && npm run dev
cd apps/frontend && npm run build         # 타입체크 + 빌드

# 전체 로컬 스택 (DB + Redis + Backend)
docker compose -f infra/docker/docker-compose.yml up

# ML 골격 확인
cd ml && python models/lstm/vacancy_lstm.py
```

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
