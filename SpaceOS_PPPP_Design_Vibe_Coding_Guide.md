# SpaceOS — 디지털 PPPP & 디자인 바이브 코딩 가이드

> **목적** — Platform · Page · Posting · Program(PPPP)과 디자인 과정을 *바이브 코딩(Vibe Coding)* 으로 구현하기 위한 단일 기준 문서.
> **핵심 가설** — "물리적 Place의 가치가 Digital Platform으로 전이된다."
> **작업 방식** — 자연어 PRD → Claude(Code)로 코드 생성 → 검증 사이클. 도구는 **Cursor + Claude Code** 조합.
> **원칙** — 데이터 기반 · 추측 최소화 · 논리적 구조 유지 · 기술 용어 영문 병기.

---

## 📑 목차

1. **용어 사전** — PPPP & 디자인 과정의 각 의미와 설명
2. **초기 공통 Claude Code 셋업** — 모든 과정의 공통 출발점
3. **데이터 수집·저장 폴더 구조** — 바이브 코딩 단계별 Bronze/Silver/Gold
4. **프롬프트 + 바이브 코딩 코드** — 단계별 Claude 활용 프롬프트와 복붙용 코드

---

# 1. 용어 사전 — PPPP & 디자인

## 1.0 큰 그림 — PPPP + 디자인 파이프라인

SpaceOS는 전통 마케팅 4P(Place·Product/Price·Promotion)를 **디지털 4P(PPPP)** 로 전환하고, 그 결과물을 하나의 앱으로 묶는 **디자인 과정**을 더해 5개 트랙으로 구성된다.

```
[데이터 수집] → P1 Platform → P2 Page → P3 Posting → P4 Program → [Design: 하나의 앱으로 통합]
   Bronze         GNN 추천      공실 3D맵     입점 솔루션    마케팅 자동화      UX/UI · React FE
```

| 트랙 | 전환(기존 4P → 디지털) | SpaceOS 구현 기능 | 핵심 기술 |
|------|------------------------|-------------------|-----------|
| **Platform** | Place → Platform | 상권 AI 추천 엔진 (각 상권을 하나의 플랫폼으로) | GNN, PostGIS |
| **Page** | Product/Price → Page | 공실 히트맵 + 3D 디지털 트윈 맵 | Three.js, Mapbox |
| **Posting** | Promotion → Posting | 입점 솔루션 (고급화/가성비/기능중심 비용-효용 분석) | LSTM, Scikit-learn |
| **Program** | Promotion → Program | 온·오프라인 마케팅 자동화 (LLM 콘텐츠 + 행사 추천) | LangChain, LLM |
| **Design** | — (통합 레이어) | 디자인 시스템 + 화면 설계 + React 구현·배포 | React, Tailwind, Figma |

## 1.1 Platform (플랫폼화)

- **의미** — 물리적 *장소(Place)* 를 데이터와 거버넌스가 작동하는 **디지털 트윈 운영 체계**로 전환한다. 각 상권 자체를 하나의 "플랫폼"으로 본다.
- **SpaceOS 구현** — 리뷰·유동인구·개폐업 데이터를 그래프로 모델링해, 특정 입지에 **최적 업종을 추천**하는 AI 엔진.
- **핵심 기술** — **GNN(Graph Neural Network)**: 업종 간 *시너지(synergy)* 와 *잠식(cannibalization)* 효과를 학습. PostgreSQL/**PostGIS** 공간 쿼리.
- **산출물** — `/api/v1/ai/recommend` 업종 추천 API, 상권 점수(Commercial District Score).

## 1.2 Page (페이지화)

- **의미** — 개별 상가·업종의 *가치(Product/Price)* 를 신뢰도 높은 **디지털 인터페이스**로 표현한다. "어떤 업장이 어디에" 있는지를 한눈에.
- **SpaceOS 구현** — **공실 히트맵(Vacancy Heatmap)** + **3D 디지털 트윈 맵**. 건물의 과거 10년 업종 변천사(공실 히스토리)를 시각화.
- **핵심 기술** — **Three.js / @react-three/fiber**(3D 렌더링), **Mapbox GL JS**(2D 지도 위 3D 배치), 100m×100m 공실 그리드.
- **산출물** — `/api/v1/heatmap`, `/api/v1/buildings/{id}/history`, 3D 트윈 뷰어.

## 1.3 Posting (포스팅화)

- **의미** — *홍보(Promotion)* 를 **알고리즘 기반 자동화된 반복 정보 발행**으로 전환. 입점 의사결정에 필요한 정보를 구조화해 "게시".
- **SpaceOS 구현** — **입점 솔루션**: 후보 업종을 **고급화 / 가성비 / 기능중심** 3축으로 **비용-효용(cost-benefit)** 분석해 제시.
- **핵심 기술** — **LSTM**(예상 매출·공실 위험도 시계열 예측), **Scikit-learn**(피처 엔지니어링), ROI(투자 회수 기간) 산출.
- **산출물** — 입점 시뮬레이션 리포트(PDF), `/api/v1/ai/simulate` 매출 시뮬레이터.

## 1.4 Program (프로그램화)

- **의미** — *홍보(Promotion)* 를 상인-건물주-소비자 간 **지속 가능한 관계·참여 구조**로 전환. 일회성 광고가 아닌 "프로그램".
- **SpaceOS 구현** — **마케팅 자동화**: 분석 결과 연계 **LLM 콘텐츠 자동 생성** + **지역 행사/팝업 기획** 추천.
- **핵심 기술** — **LangChain** + LLM, 상권 감성 키워드(Sentiment) 기반 톤앤매너 매칭.
- **산출물** — 자동 생성 SNS 포스팅·축제 기획안, `/api/v1/marketing/generate`.

## 1.5 Design (디자인 과정)

PPPP 4개 트랙의 산출물(추천·히트맵·시뮬레이션·콘텐츠)을 **하나의 사용 가능한 앱**으로 묶는 UX/UI 전 과정.

- **디자인 시스템(Design System)** — 색·타이포·간격·컴포넌트를 **디자인 토큰(Design Token)** 으로 정의해 일관성 확보.
- **화면 설계** — 정보구조(IA) → 와이어프레임 → 유저 플로우 → 고해상도 프로토타입.
- **FE 구현·배포** — React + TypeScript + Tailwind로 토큰을 코드화, 3D 트윈/대시보드 화면 구현 후 배포.
- **차별화 지표 — Humanistic Authority** — 디자인·콘텐츠가 지켜야 할 3대 윤리 기준: **균형(Balance)** · **공생(Symbiosis)** · **공감(Empathy)**.

## 1.6 공통 핵심 용어

| 용어 | 의미 |
|------|------|
| **디지털 트윈(Digital Twin)** | 물리적 상권을 데이터로 1:1 복제한 가상 모델. SpaceOS의 핵심 결과물. |
| **공실 히스토리(Vacancy History)** | 특정 건물의 과거 업종 변천사 + AI 요약 폐업 사유. |
| **GNN** | Graph Neural Network — 업종 간 시너지/잠식 분석 모델. |
| **LSTM** | Long Short-Term Memory — 시계열 매출·공실 예측 모델. |
| **Bronze / Silver / Gold** | 데이터 레이크 3계층 (원본 / 정제 / 분석용). |
| **바이브 코딩(Vibe Coding)** | 자연어 PRD → AI 코드 생성 → 검증 사이클. Cursor + Claude Code. |
| **거점 상권** | MVP 검증 대상 1개 상권 (1순위 라페스타, 2순위 홍대·연남동). |
| **Sentiment Score** | 리뷰·SNS 텍스트의 감성 점수 (−1 ~ +1). |
| **DaaS** | Data as a Service — 월 구독형 상권 분석 데이터 제공 모델. |
| **PostGIS** | PostgreSQL 공간 확장 — 좌표·폴리곤 공간 쿼리. |

## 1.7 디자인 전용 용어

| 용어 | 의미 |
|------|------|
| **디자인 시스템(Design System)** | 재사용 가능한 UI 표준 묶음 (토큰 + 컴포넌트 + 가이드). |
| **디자인 토큰(Design Token)** | 색·폰트·간격 등 디자인 결정의 최소 단위 변수 (`--color-primary`). |
| **Atomic Design** | Atom → Molecule → Organism → Template → Page 단계적 컴포넌트 설계법. |
| **IA(Information Architecture)** | 정보구조 — 화면·메뉴·데이터의 위계 설계. |
| **유저 플로우(User Flow)** | 사용자가 목표 달성까지 거치는 화면 전환 경로. |
| **와이어프레임 / 프로토타입** | 저충실도 레이아웃 / 고충실도 상호작용 시안. |
| **반응형(Responsive)** | 화면 크기에 따라 레이아웃이 적응하는 설계. |
| **접근성(a11y)** | 색 대비·키보드·스크린리더 등 모두가 쓸 수 있는 설계. |

---

# 2. 초기 공통 Claude Code 셋업

> PPPP·디자인 **모든 트랙이 공유하는 출발점**. 새 트랙을 시작할 때마다 이 셋업을 먼저 확인한다.

## 2.1 사전 준비 / 설치

> 📌 **전역 설치(`-g`)** — 어느 폴더에서나 `claude` 명령을 쓰도록 시스템 전체에 설치. **Cursor** — AI 코드 생성에 특화된 에디터(VS Code 기반).

```bash
# 필수 런타임
node -v   # 18+ 필요
python --version   # 3.11 권장
git --version
docker --version

# Claude Code 설치 (전역)
npm install -g @anthropic-ai/claude-code

# 첫 실행 → 로그인(인증)
claude        # 브라우저로 Anthropic 계정 인증

# 에디터: Cursor 설치 후 Claude Code를 보조 CLI로 병행
#  - Cursor: Composer/Agent로 빠른 생성
#  - Claude Code: 멀티파일·터미널·MCP 작업
```

## 2.2 모노레포 부트스트랩

> 📌 **모노레포(Monorepo)** — BE·FE·ML·Data를 한 git 저장소에서 함께 관리하는 방식(폴더로 구분). **부트스트랩(Bootstrap)** — 프로젝트 초기 뼈대(폴더·설정)를 한 번에 세팅하는 작업.

```bash
# 1) 레포 생성/클론
git clone <repo-url> spaceos && cd spaceos

# 2) 표준 디렉토리 골격
mkdir -p apps/backend apps/frontend ml data infra docs memory \
         .claude/commands .claude/agents

# 3) 결과 구조
spaceos/
├── apps/
│   ├── backend/      # FastAPI (Python 3.11)
│   └── frontend/     # React + TypeScript + Vite
├── ml/               # PyTorch LSTM(공실) / GNN(업종) + MLflow
├── data/             # Airflow DAG + 크롤러 + Bronze/Silver/Gold
├── infra/            # docker-compose / Dockerfile / k8s / GitHub Actions
├── docs/             # 설계 문서
├── memory/           # 프로젝트 메모리(전략·용어집)
├── .claude/          # Claude Code 설정
│   ├── commands/     # 커스텀 슬래시 명령
│   ├── agents/       # 서브에이전트
│   └── settings.json # 권한·도구 설정
├── CLAUDE.md         # 프로젝트 메모리(항상 로드됨)
└── .mcp.json         # 프로젝트 스코프 MCP 서버
```

## 2.3 `CLAUDE.md` — 프로젝트 메모리 스켈레톤

> 📌 **CLAUDE.md** — Claude Code가 **매 세션 자동으로 읽는 '프로젝트 규칙 메모'**. 스택·컨벤션·금지사항을 적어두면 AI가 그대로 코드를 생성한다. 바이브 코딩 품질을 좌우하는 핵심 파일.

```markdown
# SpaceOS — 코드베이스 가이드

## 핵심 가설
"물리적 Place의 가치가 Digital Platform으로 전이된다."

## 디렉토리
apps/backend  FastAPI  |  apps/frontend  React+Vite
ml  LSTM/GNN+MLflow    |  data  Airflow+크롤러+Bronze/Silver/Gold

## 기술 스택 (확정)
FE: React+TS+Three.js/@react-three/fiber+Mapbox GL+Tailwind
BE: FastAPI+PostgreSQL/PostGIS+Redis+Celery
ML: PyTorch+PyTorch Geometric(GNN)+LSTM+MLflow+LangChain
Data: Airflow+Selenium/Playwright+Bronze/Silver/Gold

## 코드 규칙
- 응답·주석·문서: 한국어, 기술 용어 영문 병기
- Backend: 라우터 app/api/v1/, 스키마 app/schemas/, 모델 app/models/, 로직 app/services/. 타입 힌트 필수
- Frontend: 함수형+훅, API는 src/lib/api.ts로 일원화, @/ 경로 별칭
- ML: 모델 ml/models/, 학습 ml/training/, 서빙 ml/inference/, 실험은 MLflow
- Data: 모든 파이프라인 Bronze→Silver→Gold 준수, 크롤러 data/crawlers/
- 더미 데이터에는 반드시 `# TODO: 실제 연동` 주석으로 연동 지점 명시

## 성능 목표
AI 공실 예측 70%+(Phase1) | 3D 맵 로딩 <3초 | API p95 <200ms
```

## 2.4 MCP 서버 연결 — `.mcp.json`

> 📌 **MCP(Model Context Protocol)** — AI가 외부 도구(DB·GitHub 등)에 붙는 표준 규격. **`.mcp.json`** — 이 프로젝트에서 Claude가 쓸 MCP 서버 목록을 정의하는 파일(여기선 DB·파일시스템·GitHub).

```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres",
               "postgresql://localhost:5432/spaceos"]
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./data"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" }
    }
  }
}
```

```bash
# CLI로 추가도 가능
claude mcp add postgres -- npx -y @modelcontextprotocol/server-postgres "postgresql://localhost:5432/spaceos"
claude mcp list            # 연결 확인
```

## 2.5 권한·설정 — `.claude/settings.json`

> 📌 **`settings.json`** — Claude Code의 **권한 설정** 파일. `allow`(허용)·`deny`(차단)로 어떤 명령 실행·파일 편집을 자동 승인할지 정한다. 위험 명령(`rm -rf`)·비밀파일(`.env`)은 차단.

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run *)",
      "Bash(pytest*)",
      "Bash(python ml/*)",
      "Bash(docker compose *)",
      "Edit(apps/**)",
      "Edit(ml/**)",
      "Edit(data/**)"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Read(./.env)",
      "Read(./**/*secret*)"
    ]
  },
  "env": { "PYTHONUNBUFFERED": "1" }
}
```

## 2.6 서브에이전트 / 스킬

> 📌 **서브에이전트(Subagent)** — 특정 역할(데이터·ML·FE)에 특화된 보조 AI. 큰 작업을 분담시켜 정확도↑. **스킬(Skill)** — 자주 쓰는 작업 절차를 재사용하도록 묶어둔 것.

```bash
.claude/agents/
├── data-engineer.md      # 크롤러·ETL·DAG 전담 (data/ 작업)
├── ml-engineer.md        # LSTM/GNN 모델·학습·서빙 (ml/ 작업)
└── fe-designer.md        # React·Three.js·디자인 시스템 (apps/frontend/)
```

> SpaceOS 전용 스킬을 함께 사용한다: **spaceos-data-pipeline**(크롤링·ETL), **spaceos-tech-expert**(아키텍처·코드), **spaceos-strategy-expert**(전략·IR).

## 2.7 환경변수 / 시크릿 — `.env.example`

> 📌 **`.env`** — 비밀키·DB주소 등 **환경변수**를 담는 파일(git에 올리지 않음). **`.env.example`** — 값을 비운 **공유용 템플릿**(어떤 키가 필요한지 양식만 보여줌).

```bash
# DB / 캐시
DATABASE_URL=postgresql://localhost:5432/spaceos
REDIS_URL=redis://localhost:6379/0
# 외부 API 키 (실제 키는 .env에만, git 커밋 금지)
NAVER_CLIENT_ID=
NCP_MAP_KEY_ID=
OPENAI_API_KEY=
# 데이터 저장
S3_BRONZE_BUCKET=spaceos-bronze
```

> `.env`는 `.gitignore`에 포함, `.env.example`만 커밋. 키 입력은 사용자가 직접(보안).

## 2.8 바이브 코딩 루프 (공통 작업 방식)

> 📌 **PRD(Product Requirements Document)** — '무엇을·왜·제약'을 적은 **요구사항 문서**. 바이브 코딩의 입력(프롬프트)이 된다. **커밋(Commit)** — 변경을 의미 단위로 git에 저장하는 것.

```
① PRD 작성  →  ② Claude로 생성  →  ③ 검증  →  ④ 커밋
   (자연어)       (Cursor/Claude)    (테스트/타입/스크린샷)   (의미 단위)
```

1. **PRD** — "무엇을/왜/제약"을 자연어로. 본 문서 4장의 프롬프트 템플릿 사용.
2. **생성** — Cursor Composer(빠른 단일 파일) 또는 Claude Code(멀티파일·MCP).
3. **검증** — `pytest` / `npm run build`(타입체크) / 3D·대시보드는 스크린샷 확인.
4. **커밋** — 트랙·기능 단위로 작게. `feat(platform): GNN 추천 API 초안`.

```bash
# .claude/commands/verify.md  → /verify 로 호출하는 공통 검증 루틴
cd apps/backend && pytest -q
cd apps/frontend && npm run build
cd ml && python -c "import torch; print('torch ok', torch.__version__)"
```

## 2.9 셋업 체크리스트

- [ ] Node 18+ / Python 3.11 / Docker 설치 확인
- [ ] `npm i -g @anthropic-ai/claude-code` 후 `claude` 인증
- [ ] 모노레포 골격 생성 + `CLAUDE.md` 작성
- [ ] `.mcp.json`(postgres/filesystem/github) 연결 → `claude mcp list`
- [ ] `.claude/settings.json` 권한 설정
- [ ] `.env.example` 작성, `.env`는 gitignore
- [ ] `/verify` 명령 동작 확인

---

# 3. 데이터 수집·저장 폴더 구조

> 바이브 코딩 **각 단계마다** 데이터를 수집·정제·서비스용으로 분리해 저장한다. 표준은 **Bronze → Silver → Gold** 3계층.

## 3.1 원칙 — Bronze / Silver / Gold

> 📌 **Bronze/Silver/Gold** — 데이터를 성숙도별 3층으로 나눠 관리하는 표준(원본→정제→분석용). **Parquet** — 컬럼 단위로 압축 저장하는 포맷으로 분석 조회가 CSV보다 빠르다. **append-only** — 원본을 고치지 않고 덧붙이기만 함(무결성 보존).

| 레이어 | 명칭 | 저장 형태 | 역할 |
|--------|------|-----------|------|
| **Bronze** | Raw | JSON · CSV · HTML | 원본 무결성 보존, **변형 없이** 저장 (불변) |
| **Silver** | Cleaned | **Parquet** | 결측치 처리, 중복 제거, 주소 정규화, 표준화 |
| **Gold** | Analytics | PostGIS · Feature Table | ML 학습 피처, API 서비스 제공 데이터 |

**규칙**: 흐름은 항상 `Bronze → Silver → Gold` 단방향. Bronze는 절대 덮어쓰지 않는다(append-only).

## 3.2 전체 데이터 폴더 트리

```
data/
├── bronze/                          # 원본·불변 (JSON/CSV/HTML)
│   ├── platform/
│   │   ├── reviews/                 # naver_place, google_maps 리뷰
│   │   ├── footfall/                # 유동인구(통신사/공공)
│   │   └── business_permits/        # 인허가·개폐업(행안부)
│   ├── page/
│   │   ├── vacancy/                 # 공실 현황(전수조사·크롤링)
│   │   └── buildings/               # 건축물대장·building footprint
│   ├── posting/
│   │   ├── card_sales/              # 카드사 매출(구매 데이터)
│   │   └── rent/                    # 임대 시세(직방/네이버부동산)
│   └── program/
│       ├── sns/                     # 인스타 해시태그·네이버 블로그
│       └── events/                  # 지역 행사·축제
├── silver/                          # 정제 (Parquet) — bronze와 동일 하위구조
│   ├── platform/   ├── page/   ├── posting/   └── program/
├── gold/                            # 분석·서비스용
│   ├── features/                    # ML 학습 피처 테이블(GNN/LSTM)
│   ├── geo/                         # PostGIS 적재용(100m×100m 그리드)
│   └── serving/                     # API 응답 캐시(JSON)
├── crawlers/                        # 수집 코드(트랙별)
│   ├── platform/  page/  posting/  program/
│   └── common/                      # 주소 정규화·중복 제거 등 공통 유틸
├── dags/                            # Airflow DAG (수집→정제→적재 스케줄)
├── schemas/                         # 레이어별 스키마 정의(JSON Schema / SQL)
├── manifests/                       # 수집 메타데이터(언제·어디서·몇 건)
└── assets/                          # ⬅ Design 트랙 에셋
    ├── design-tokens/               # tokens.json (색·타이포·간격)
    ├── figma-exports/               # 시안 export(svg/png)
    ├── icons/                       # 아이콘 세트
    └── 3d-models/                   # glTF / CityGML 건물 모델
```

## 3.3 단계별(PPPP·디자인) 데이터 매핑

| 단계 | 주요 데이터 | 원천 | 수집 방법 | 저장 위치(Bronze) |
|------|------------|------|-----------|------------------|
| **Platform** | 리뷰·유동인구·개폐업 | 네이버/구글, 통신사, 행안부 | 크롤링 + 공공API | `bronze/platform/` |
| **Page** | 공실·건축물대장 | 전수조사, 공공데이터포털 | 크롤링 + REST API | `bronze/page/` |
| **Posting** | 카드 매출·임대 시세 | 카드사, 직방/네이버부동산 | 데이터 구매 + 크롤링 | `bronze/posting/` |
| **Program** | SNS 트렌드·행사 | 인스타/블로그, 지자체 | 크롤링 + 공공API | `bronze/program/` |
| **Design** | 디자인 토큰·3D 모델 | Figma, CityGML/glTF | export · 변환 | `data/assets/` |

## 3.4 네이밍 · 파티셔닝 규약

> 📌 **파티셔닝(Partitioning)** — 데이터를 지역·날짜 기준으로 폴더 분할 저장 → 필요한 부분만 빠르게 조회. **slug** — URL·경로용 영문 식별자(예: lapesta). **grid_id** — 100m×100m 격자 한 칸의 고유 ID(공간 키).

```
# 파일명:  {source}_{district}_{YYYYMMDD}.{ext}
bronze/platform/reviews/lapesta/202606/naver_lapesta_20260604.json

# 파티션:  {track}/{dataset}/{district}/{YYYYMM}/
#  - district: 거점 상권 슬러그 (lapesta, hongdae, yongbong …)
#  - 기간 단위: 월별(Weekly 보완), 시간은 파일 단위로 분리
```

- **Silver/Gold**는 Parquet 파티션 컬럼으로 `district`, `year_month`을 명시.
- **Gold/geo**는 100m×100m 그리드 ID(`grid_id`)를 공간 키로 사용(PostGIS).

## 3.5 메타데이터 / 매니페스트

> 📌 **매니페스트(Manifest)** — '언제·어디서·몇 건' 수집했는지 적은 메타데이터 기록. 재현성·품질 추적용. **sha256** — 원본이 바뀌지 않았는지 확인하는 지문(해시값).

> 모든 수집 작업은 `manifests/`에 1건씩 기록 → 재현성·품질 추적.

```json
// data/manifests/platform_reviews_lapesta_20260604.json
{
  "track": "platform",
  "dataset": "reviews",
  "source": "naver_place",
  "district": "lapesta",
  "period": "2026-06",
  "collected_at": "2026-06-04T10:21:00+09:00",
  "row_count": 1842,
  "schema_version": "v1",
  "sha256": "8f2c…",            // 원본 무결성 검증
  "notes": "리뷰 평점/텍스트/작성일 수집, 사진 URL 제외"
}
```

## 3.6 `.gitignore` / 보안

> 📌 **K-익명성(K-anonymity)** — 개인을 특정 못 하게 같은 속성 그룹을 K명 이상으로 묶는 비식별화. **PostGIS** — PostgreSQL에 좌표·면적 공간 연산을 더한 확장.

```gitignore
# 대용량 원본·정제 데이터는 git 제외 (S3/GCS로 관리)
data/bronze/**
data/silver/**
data/gold/**
data/assets/3d-models/**

# 코드·스키마·매니페스트는 git 추적(재현성)
!data/schemas/**
!data/manifests/**
!data/crawlers/**
```

- 개인정보(유동인구 등)는 **비식별화·K-익명성** 처리 후에만 Silver 이상으로 이동.
- 카드사·통신사 **구매 데이터**는 계약상 보관 위치 분리, 접근 권한 최소화.

---

# 4. 프롬프트 + 바이브 코딩 코드

> 각 트랙마다 **① Claude 프롬프트(PRD)** → **② 복붙용 코드 스니펫** 순으로 제공한다. 프롬프트를 Cursor/Claude Code에 붙여넣어 생성하고, 아래 코드를 기준 골격으로 검증한다.

## 4.0 프롬프트 작성 공통 규칙 (PRD 템플릿)

> 📌 **PRD 템플릿** — 역할·목표·입력·제약·산출물·검증 6칸을 채우면 그대로 프롬프트가 된다. 경로·스키마를 명시할수록 AI 추측이 줄어든다.

```text
# 역할(Role)
너는 SpaceOS {트랙} 담당 개발자다. CLAUDE.md 규칙을 따른다.

# 목표(Goal)
{한 문장으로 무엇을 만드는가}

# 입력 데이터(Input)
- 경로: {silver/ 또는 gold/ 경로}
- 스키마: {컬럼명: 타입, ...}

# 제약(Constraints)
- 기술스택: {확정 스택만 사용}
- 주석/문서는 한국어, 기술 용어 영문 병기
- 더미 데이터에는 반드시 `# TODO: 실제 연동` 명시
- Python 타입 힌트 필수 / TypeScript strict

# 산출물(Deliverable)
- 파일: {정확한 경로}
- 인터페이스: {함수 시그니처 / API 엔드포인트}

# 검증(Verify)
- {테스트·실행으로 통과해야 할 기준}
```

**팁** — 프롬프트는 항상 *경로·스키마·검증 기준*을 명시한다. 모호하면 Claude가 가정으로 채우므로 "추측 최소화" 원칙에 어긋난다.

## 4.1 Platform — GNN 업종 추천

> 📌 **GNN(Graph Neural Network)** — 노드(업종)와 엣지(관계)로 된 그래프를 학습하는 신경망. **GraphSAGE** — 이웃 노드 정보를 모아 임베딩을 만드는 대표 GNN 기법. **forward pass** — 입력→출력까지 한 번 계산. **logit** — 확률로 바꾸기 전의 원점수.

### 프롬프트

```text
# 역할
너는 SpaceOS Platform 트랙의 ML 엔지니어다. CLAUDE.md를 따른다.
# 목표
상권 그래프(업종=노드, 시너지=엣지)를 입력받아 특정 입지(grid)에 최적 업종 Top-5를 추천하는 GNN과 추론 API를 만든다.
# 입력 데이터
- gold/features/platform_graph_{district}.parquet
  node: [industry_code, avg_sales, review_cnt, sentiment]  edge: [synergy_weight]
# 제약
- PyTorch + PyTorch Geometric. 모델 ml/models/gnn/, 서빙 ml/inference/
- 추론 API: FastAPI apps/backend/app/api/v1/ai.py → POST /api/v1/ai/recommend
# 산출물
- ml/models/gnn/recommend_gnn.py (GraphSAGE 2-layer)
- apps/backend/app/api/v1/ai.py (recommend 엔드포인트)
# 검증
- 더미 그래프로 forward pass 통과, Top-5 (업종, 점수) 정렬 반환
```

### 코드 — GNN 모델

```python
# ml/models/gnn/recommend_gnn.py
"""상권 업종 추천 GNN (GraphSAGE 2-layer).
입력: 업종 그래프(노드 피처 + 엣지) → 출력: 노드별 적합도 스코어.
TODO: gold/features/platform_graph_*.parquet 실제 로딩 연결.
"""
from __future__ import annotations
import torch
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv


class RecommendGNN(torch.nn.Module):
    def __init__(self, in_dim: int, hidden: int = 64, out_dim: int = 32) -> None:
        super().__init__()
        self.conv1 = SAGEConv(in_dim, hidden)
        self.conv2 = SAGEConv(hidden, out_dim)
        self.score = torch.nn.Linear(out_dim, 1)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        h = F.relu(self.conv1(x, edge_index))
        h = F.dropout(h, p=0.3, training=self.training)
        h = F.relu(self.conv2(h, edge_index))
        return self.score(h).squeeze(-1)  # 노드별 적합도(logit)


def recommend_top_k(model, x, edge_index, labels: list[str], k: int = 5):
    model.eval()
    with torch.no_grad():
        scores = torch.sigmoid(model(x, edge_index))
    top = torch.topk(scores, k=min(k, scores.numel()))
    return [(labels[i], round(float(scores[i]), 4)) for i in top.indices]


if __name__ == "__main__":
    # 더미 그래프(업종 8개) — TODO: 실제 Parquet 로딩으로 교체
    n, in_dim = 8, 4
    x = torch.randn(n, in_dim)
    edge_index = torch.randint(0, n, (2, 16))
    labels = [f"업종_{i}" for i in range(n)]
    print(recommend_top_k(RecommendGNN(in_dim), x, edge_index, labels))
```

### 코드 — 추론 API

> 📌 **APIRouter** — FastAPI에서 엔드포인트(주소)를 묶는 라우터. **Pydantic BaseModel** — 입·출력 데이터의 형식·검증을 정의하는 클래스(잘못된 입력을 자동 거른다).

```python
# apps/backend/app/api/v1/ai.py
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


class RecommendRequest(BaseModel):
    district: str           # 거점 상권 슬러그 (예: lapesta)
    grid_id: str            # 100m×100m 그리드 ID
    top_k: int = 5


class IndustryScore(BaseModel):
    industry: str
    score: float


@router.post("/recommend", response_model=list[IndustryScore])
async def recommend(req: RecommendRequest) -> list[IndustryScore]:
    # TODO: gold/features 로딩 + 학습된 GNN 가중치 로드(ml/inference/gnn_service)
    from ml.inference.gnn_service import predict_top_k
    pairs = predict_top_k(req.district, req.grid_id, req.top_k)
    return [IndustryScore(industry=n, score=s) for n, s in pairs]
```

## 4.2 Page — 공실 히트맵 + 3D 디지털 트윈

> 📌 **heatmap 레이어** — 점 데이터를 밀도에 따라 색으로 칠하는 지도 표현. **@react-three/fiber** — React에서 Three.js 3D를 그리는 래퍼. **Canvas** — 3D를 그리는 화면(그림판). **OrbitControls** — 마우스로 시점 회전·확대.

### 프롬프트

```text
# 역할
너는 SpaceOS Page 트랙의 프론트엔드 개발자다. CLAUDE.md를 따른다.
# 목표
거점 상권의 공실을 2D 지도 히트맵으로, 선택 건물은 3D 디지털 트윈으로 보여주는 React 컴포넌트를 만든다.
# 입력 데이터
- GET /api/v1/heatmap?district=lapesta → [{grid_id, lng, lat, vacancy_rate}]
- GET /api/v1/buildings/{id}/history → [{level, industry, vacant}]
# 제약
- React+TS, @react-three/fiber, Mapbox GL, Tailwind. API 호출은 src/lib/api.ts로 일원화
- 3D 맵 로딩 < 3초
# 산출물
- apps/frontend/src/components/VacancyHeatmap.tsx
- apps/frontend/src/components/BuildingTwin.tsx
# 검증
- 더미 데이터로 히트맵 렌더, 건물 클릭 시 3D 패널 표시
```

### 코드 — 공실 히트맵 (Mapbox)

```tsx
// apps/frontend/src/components/VacancyHeatmap.tsx
import { useEffect, useRef } from "react";
import mapboxgl from "mapbox-gl";
import { fetchHeatmap } from "@/lib/api";

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN;

export default function VacancyHeatmap({ district }: { district: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const map = new mapboxgl.Map({
      container: ref.current,
      style: "mapbox://styles/mapbox/light-v11",
      center: [126.77, 37.658], // TODO: district별 중심좌표 매핑
      zoom: 15,
    });

    map.on("load", async () => {
      const cells = await fetchHeatmap(district); // [{lng,lat,vacancy_rate}]
      map.addSource("vacancy", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: cells.map((c) => ({
            type: "Feature",
            properties: { w: c.vacancy_rate },
            geometry: { type: "Point", coordinates: [c.lng, c.lat] },
          })),
        },
      });
      map.addLayer({
        id: "vacancy-heat",
        type: "heatmap",
        source: "vacancy",
        paint: {
          "heatmap-weight": ["get", "w"],
          "heatmap-radius": 28,
          "heatmap-color": [
            "interpolate", ["linear"], ["heatmap-density"],
            0, "rgba(0,0,0,0)", 0.4, "#fde68a", 0.7, "#fb923c", 1, "#dc2626",
          ],
        },
      });
    });
    return () => map.remove();
  }, [district]);

  return <div ref={ref} className="w-full h-[600px] rounded-xl" />;
}
```

### 코드 — 3D 건물 트윈 (react-three-fiber)

```tsx
// apps/frontend/src/components/BuildingTwin.tsx
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";

type Floor = { level: number; industry: string; vacant: boolean };

export default function BuildingTwin({ floors }: { floors: Floor[] }) {
  return (
    <Canvas camera={{ position: [6, 6, 6], fov: 45 }} className="h-[480px]">
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 10, 5]} />
      {floors.map((f, i) => (
        <mesh key={f.level} position={[0, i * 1.1, 0]}>
          <boxGeometry args={[3, 1, 3]} />
          {/* 공실=회색, 영업중=브랜드색 */}
          <meshStandardMaterial color={f.vacant ? "#9ca3af" : "#2563eb"} />
        </mesh>
      ))}
      <OrbitControls enableDamping />
    </Canvas>
  );
}
```

### 코드 — API 일원화 (참고)

```ts
// apps/frontend/src/lib/api.ts
const BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export async function fetchHeatmap(district: string) {
  const r = await fetch(`${BASE}/heatmap?district=${district}`);
  if (!r.ok) throw new Error("heatmap fetch 실패");
  return r.json() as Promise<{ grid_id: string; lng: number; lat: number; vacancy_rate: number }[]>;
}
```

## 4.3 Posting — 입점 솔루션 (비용-효용 3축)

> 📌 **@dataclass** — 데이터 보관용 파이썬 클래스를 간단히 만드는 데코레이터. **ROI(Return on Investment)** — 투자 회수 기간/수익률. **상각(2년 상각)** — 초기 비용을 기간(24개월)으로 나눠 분산 반영.

### 프롬프트

```text
# 역할
너는 SpaceOS Posting 트랙의 백엔드/ML 엔지니어다. CLAUDE.md를 따른다.
# 목표
후보 업종을 고급화/가성비/기능중심 3축으로 비용-효용 점수화하고, LSTM 예상 매출과 ROI(회수 개월)를 산출하는 서비스를 만든다.
# 입력 데이터
- gold/features/posting_{district}.parquet
  [monthly_rent, fitout_cost, expected_sales_series, margin_rate]
# 제약
- Python. 서비스 app/services/posting.py, LSTM 호출은 ml/inference/lstm_service
- POST /api/v1/ai/simulate
# 산출물
- apps/backend/app/services/posting.py
# 검증
- 더미 입력으로 3축 점수 + ROI(개월) 반환
```

### 코드 — 비용-효용 스코어링

```python
# apps/backend/app/services/posting.py
"""입점 솔루션 — 비용-효용(cost-benefit) 3축 분석 + ROI.
축: 고급화(premium) / 가성비(value) / 기능중심(function).
TODO: gold/features/posting_*.parquet, LSTM 매출예측(ml/inference) 연동.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class PostingInput:
    monthly_rent: float        # 월 임대료(만원)
    fitout_cost: float         # 초기 인테리어(만원)
    expected_sales: float      # LSTM 예상 월매출(만원)
    margin_rate: float = 0.30  # 영업이익률


# 축별 (매출가중, 비용가중) 성향
AXIS_WEIGHTS = {
    "premium":  (0.7, 0.3),    # 고급화: 매출 상방 중시
    "value":    (0.4, 0.6),    # 가성비: 비용 절감 중시
    "function": (0.5, 0.5),    # 기능중심: 균형
}


def score_axes(p: PostingInput) -> dict[str, float]:
    profit = p.expected_sales * p.margin_rate
    cost = p.monthly_rent + p.fitout_cost / 24  # 2년 상각
    out: dict[str, float] = {}
    for axis, (ws, wc) in AXIS_WEIGHTS.items():
        raw = ws * profit - wc * cost              # 효용
        out[axis] = round(max(0.0, min(100.0, 50 + raw / 10)), 1)
    return out


def roi_months(p: PostingInput) -> float | None:
    monthly_profit = p.expected_sales * p.margin_rate - p.monthly_rent
    if monthly_profit <= 0:
        return None  # 회수 불가
    return round(p.fitout_cost / monthly_profit, 1)


if __name__ == "__main__":
    demo = PostingInput(monthly_rent=350, fitout_cost=6000, expected_sales=2200)
    print("3축 점수:", score_axes(demo), "| ROI(개월):", roi_months(demo))
```

## 4.4 Program — 마케팅 자동화 (LLM)

> 📌 **LangChain** — LLM 호출·프롬프트·체인을 조립하는 프레임워크. **ChatPromptTemplate** — system/human 메시지 양식(빈칸 {district} 등을 채움). **temperature** — 답변의 무작위성(↑창의적, ↓일관적).

### 프롬프트

```text
# 역할
너는 SpaceOS Program 트랙의 LLM 엔지니어다. CLAUDE.md를 따른다.
# 목표
상권 감성 키워드·분석 결과로 SNS 포스팅 초안과 지역 행사 아이디어를 자동 생성한다.
톤은 Humanistic Authority(균형·공생·공감)를 반드시 지킨다.
# 입력 데이터
- gold/serving/sentiment_{district}.json  [top_keywords, mood, tone]
# 제약
- LangChain + LLM. 서비스 app/services/marketing.py, 키는 .env
- POST /api/v1/marketing/generate
# 산출물
- apps/backend/app/services/marketing.py
# 검증
- 더미 키워드로 포스팅 3종 + 행사 1종 반환
```

### 코드 — LLM 콘텐츠 생성

```python
# apps/backend/app/services/marketing.py
"""Program 트랙 — 마케팅 콘텐츠 자동 생성(LLM).
상권 감성 키워드 → SNS 포스팅 + 지역 행사 아이디어.
원칙(Humanistic Authority): 균형·공생·공감을 톤 기준으로.
TODO: gold/serving/sentiment_*.json 실제 로딩, LLM 키는 .env.
"""
from __future__ import annotations
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

_SYSTEM = (
    "너는 지역 상권 마케터다. 상권 고유의 분위기·역사를 존중하고(공감), "
    "특정 업종에 편중되지 않으며(균형), 상인-주민 상생을 지향한다(공생). "
    "과장·허위 표현을 쓰지 않는다."
)

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM),
    ("human",
     "상권: {district}\n감성 키워드: {keywords}\n분위기: {mood}\n"
     "위 정보로 (1) 인스타 포스팅 3종(각 2문장 + 해시태그), "
     "(2) 지역 행사 아이디어 1종(제목 + 한 줄 설명)을 한국어로 작성."),
])


def generate_marketing(district: str, keywords: list[str], mood: str) -> str:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)  # 키는 .env
    chain = _PROMPT | llm
    return chain.invoke({
        "district": district,
        "keywords": ", ".join(keywords),
        "mood": mood,
    }).content


if __name__ == "__main__":
    print(generate_marketing("라페스타", ["레트로", "야장", "청춘"], "활기찬 저녁"))
```

## 4.5 Design — 디자인 시스템 + 화면 설계 + FE

> 📌 **디자인 토큰** — 색·폰트·간격을 변수로 정의한 것(한 곳만 바꾸면 전체 반영). **Atomic Design** — Atom→Molecule→…→Page 단계로 쌓는 컴포넌트 설계. **Tailwind config** — 토큰을 Tailwind 클래스로 연결하는 설정.

### 프롬프트

```text
# 역할
너는 SpaceOS Design 트랙의 디자인 시스템 엔지니어다. CLAUDE.md를 따른다.
# 목표
PPPP 산출물을 하나의 앱으로 묶는 디자인 시스템(토큰+컴포넌트)과 상권 대시보드 레이아웃을 만든다.
# 입력
- data/assets/design-tokens/tokens.json (색·타이포·간격)
- 화면: 대시보드(좌: 히트맵, 우: 추천/시뮬레이션 패널)
# 제약
- React+TS+Tailwind. Atomic Design. 접근성(색대비 AA)·반응형
# 산출물
- data/assets/design-tokens/tokens.json
- apps/frontend/tailwind.config.js (토큰 연결)
- apps/frontend/src/components/ui/Card.tsx (Atom)
- apps/frontend/src/pages/Dashboard.tsx (Template)
# 검증
- npm run build 통과, 토큰이 Tailwind 클래스로 적용
```

### 코드 — 디자인 토큰

```json
// data/assets/design-tokens/tokens.json
{
  "color": {
    "primary":   "#2563eb",
    "vacant":    "#9ca3af",
    "heat-low":  "#fde68a",
    "heat-high": "#dc2626",
    "bg":        "#f8fafc",
    "text":      "#0f172a"
  },
  "font":   { "sans": "Pretendard, system-ui, sans-serif" },
  "radius": { "card": "0.75rem" }
}
```

### 코드 — Tailwind 연결

```js
// apps/frontend/tailwind.config.js
import tokens from "../../data/assets/design-tokens/tokens.json";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { primary: tokens.color.primary, vacant: tokens.color.vacant },
      fontFamily: { sans: tokens.font.sans.split(", ") },
      borderRadius: { card: tokens.radius.card },
    },
  },
  plugins: [],
};
```

### 코드 — 컴포넌트 (Atom) + 대시보드 (Template)

```tsx
// apps/frontend/src/components/ui/Card.tsx — Atom
import type { ReactNode } from "react";

export default function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="bg-white rounded-card shadow-sm p-6" aria-label={title}>
      <h3 className="font-sans font-semibold mb-3 text-slate-900">{title}</h3>
      {children}
    </section>
  );
}
```

```tsx
// apps/frontend/src/pages/Dashboard.tsx — Template
import VacancyHeatmap from "@/components/VacancyHeatmap";
import Card from "@/components/ui/Card";

export default function Dashboard({ district = "lapesta" }: { district?: string }) {
  return (
    <main className="grid grid-cols-1 lg:grid-cols-3 gap-6 p-6 bg-slate-50 min-h-screen">
      <div className="lg:col-span-2">
        <Card title="공실 히트맵 (Page)">
          <VacancyHeatmap district={district} />
        </Card>
      </div>
      <aside className="space-y-6">
        <Card title="AI 업종 추천 (Platform)">{/* TODO: /ai/recommend 연결 */}</Card>
        <Card title="입점 시뮬레이션 (Posting)">{/* TODO: /ai/simulate 연결 */}</Card>
        <Card title="마케팅 자동 생성 (Program)">{/* TODO: /marketing/generate 연결 */}</Card>
      </aside>
    </main>
  );
}
```

## 4.6 검증 프롬프트 (공통)

```text
# 역할
너는 SpaceOS 코드 리뷰어다.
# 작업
방금 생성한 {파일}을 검증한다:
1. CLAUDE.md 규칙 준수 — 경로/타입힌트/한국어 주석/`# TODO` 표기
2. 더미 데이터 실행: {예: python apps/backend/app/services/posting.py}
3. 실패 시 원인과 수정안(diff)을 제시
# 출력
- 통과/실패 체크리스트 + 수정 diff
```

---

## 📌 부록 — 빠른 시작 체크리스트

1. **셋업** (2장) — Claude Code 설치 → 모노레포 골격 → `CLAUDE.md` → `.mcp.json` → 권한 → `/verify`
2. **데이터** (3장) — 트랙별 `bronze/`에 수집 → `silver/` 정제 → `gold/` 피처/서비스, `manifests/` 기록
3. **트랙 구현** (4장) — 각 트랙: PRD 프롬프트 붙여넣기 → 코드 생성 → 검증 프롬프트로 점검
4. **순서 권장** — Page(눈에 보이는 결과) → Platform(추천) → Posting(시뮬) → Program(콘텐츠) → Design(통합)

> 모든 단계 공통 원칙: **데이터 기반 · 추측 최소화 · 더미엔 `# TODO` · 한국어 주석(영문 병기)**.
