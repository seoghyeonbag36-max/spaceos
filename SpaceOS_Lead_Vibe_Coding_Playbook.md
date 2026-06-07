# SpaceOS — 리드(총괄) 바이브 코딩 플레이북

> **대상** — SpaceOS를 총괄하며 **Platform · Page · Posting · Program · Design을 모두 오가는** 사람(리드).
> **목적** — 한 트랙만 보는 팀원과 달리, 전 트랙을 빠르게 전환하며 바이브 코딩하기 위한 **터미널 경로 · 폴더 · 프롬프트 · 코드** 단일 기준.
> **관계** — 팀원 공용 문서 `SpaceOS_PPPP_Design_Vibe_Coding_Guide.md`는 그대로 두고, 본 문서는 그 위에 얹는 **리드 전용 오케스트레이션** 레이어.
> **원칙** — 데이터 기반 · 추측 최소화 · 더미엔 `TODO` · 한국어(기술용어 영문 병기).

> ⚙️ **본 플레이북과 함께 실제 동작하는 설정 파일이 레포에 생성되어 있다**(4장 참조):
> `.claude/commands/{platform,page,posting,program,design,pppp-status,verify}.md` · `.claude/agents/{data-engineer,ml-engineer,fe-designer}.md` · `.claude/settings.lead.json` · `.mcp.json`

---

## 0. TL;DR — 리드의 하루 (3줄)

```powershell
# 1) 레포 루트에서 시작 (항상 여기)
cd C:\Users\USER\Documents\Claude\Projects\SpaceOS ; claude
```
```text
# 2) 오케스트레이션: 전 트랙 상태 + 오늘 할 일
/pppp-status 오늘은 라페스타 데모 우선

# 3) 트랙 전환하며 작업 → 검증
/page 건물 클릭 시 공실 히스토리 패널 추가
/verify
```

**리드 vs 팀원 셋업 차이 한눈에:**

| 구분 | 팀원 (트랙 1개) | 리드 (전 트랙) |
|------|----------------|----------------|
| 터미널 시작 위치 | 자기 앱 폴더 (예: `apps/frontend`) | **레포 루트** (전체 트리 + `CLAUDE.md`) |
| 권한 설정 | `settings.json` (공용, 폴더 한정) | **`settings.local.json`** (개인, 전 트랙 `Edit`) |
| 슬래시 명령 | 자기 레이어 1개 | **PPPP 5종 + `/pppp-status`** 전부 |
| 작업 모드 | 직접 코딩 | **오케스트레이션 + 서브에이전트 위임** |
| 컨텍스트 | 좁고 깊게 | 트랙 전환 시 `/clear` 후 재로딩 |

---

## 1. 터미널 접속 경로 (Windows · PowerShell / cmd)

### 1.1 어디서 여는가 — 항상 레포 루트
리드는 항상 **레포 루트**에서 `claude`를 실행한다. 그래야 `CLAUDE.md`와 전체 트리가 컨텍스트에 들어와 **어느 트랙이든 바로 편집·검증**할 수 있다. (팀원은 자기 앱 폴더에서 시작해 좁게 본다.)

```
루트 경로:  C:\Users\USER\Documents\Claude\Projects\SpaceOS
```

### 1.2 그 폴더에서 터미널 여는 3가지 방법
1. **탐색기 주소창** — 해당 폴더를 연 뒤 주소창에 `powershell` (또는 `cmd`) 입력 → Enter. 그 폴더에서 바로 열린다.
2. **Shift + 우클릭** — 폴더 빈 공간에서 Shift+우클릭 → "여기에 PowerShell 창 열기".
3. **Windows Terminal**(권장) — 탭으로 여러 셸을 동시에. 폴더 우클릭 → "터미널에서 열기".

### 1.3 PowerShell 권장 (cmd와의 차이)
PowerShell(또는 Windows Terminal)을 권장한다. cmd로 작업할 때 자주 막히는 차이:

| 작업 | PowerShell | cmd |
|------|-----------|-----|
| 명령 연결 | `cd apps\backend ; pytest` (PS7+는 `&&`도 가능) | `cd apps\backend && pytest` |
| 환경변수 설정 | `$env:VITE_NAVER_MAPS_KEY_ID="9nbzrvj8qj"` | `set VITE_NAVER_MAPS_KEY_ID=9nbzrvj8qj` |
| 가상환경 활성화 | `.\.venv\Scripts\Activate.ps1` | `.venv\Scripts\activate.bat` |
| 경로 구분자 | `\`(권장) 또는 `/` 모두 가능 | `\` |

> PowerShell 실행정책으로 `Activate.ps1`이 막히면(최초 1회): `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### 1.4 멀티 터미널 레이아웃 (리드 표준)
리드는 보통 터미널 3~4개를 동시에 띄운다 (Windows Terminal 탭 권장):

| 탭 | 시작 위치 | 명령 | 역할 |
|----|-----------|------|------|
| **T1 오케스트레이션** | 레포 루트 | `claude` | PPPP 전환·편집·검증 (메인) |
| **T2 백엔드** | `apps\backend` | `uvicorn app.main:app --reload` | API 서버 :8000 |
| **T3 프론트** | `apps\frontend` | `npm run dev` | Vite 개발서버 :5173 (`/api`→:8000 프록시) |
| **T4 자유** | 레포 루트 | `git` · `mlflow ui` · 로그 | 보조 |

### 1.5 최초 1회 셋업 (복붙)
```powershell
# 레포 루트에서
cd C:\Users\USER\Documents\Claude\Projects\SpaceOS

# 런타임 확인
node -v ; python --version ; git --version

# Claude Code 전역 설치 + 인증
npm install -g @anthropic-ai/claude-code
claude   # 브라우저로 인증

# 리드 개인 권한 적용 (팀원과 다른 셋팅의 정체 — 4.1 참조)
Copy-Item .claude\settings.lead.json .claude\settings.local.json

# MCP 연결 확인
claude mcp list
```

---

## 2. 폴더 조직화 (리드 관점)

### 2.1 실제 모노레포 트리 (현 상태 기준)
```
SpaceOS/
├── apps/
│   ├── backend/   app/api/v1/(ai·buildings·districts·heatmap·marketing·payments) · services · schemas · models
│   └── frontend/  src/(components · pages · design/{tokens,components} · lib/{api.ts,naverMap.ts})
├── ml/            models/{lstm,gnn} · training · inference · notebooks      (PyTorch + MLflow)
├── data/          bronze/ silver/ gold/ · crawlers/ · pipelines/ · collectors/   (Bronze→Silver→Gold)
├── design/        tokens/tokens.json(단일출처) · brand/ · assets/{navermap,naverpay}
├── docs/          feature-{platform,page,posting,program,design-system,naver-integration}.md · VIBE-PROMPTS.md …
├── infra/         docker/ · k8s/ · github/
├── .claude/       commands/(슬래시 명령) · agents/(서브에이전트) · settings.json(공용) · settings.local.json(리드)
├── .mcp.json      프로젝트 MCP (postgres · filesystem · github)
└── CLAUDE.md      매 세션 자동 로드되는 프로젝트 규칙
```

### 2.2 리드의 지도 — PPPP ↔ 폴더 · 엔드포인트 · api.ts (핵심)
트랙을 오갈 때 "어디를 건드리는가"를 한 장으로. (현 코드 실제값)

| 트랙 | 슬래시 | 주 편집 폴더 | 백엔드 엔드포인트 | FE 호출 (`src/lib/api.ts`) |
|------|--------|-------------|-------------------|----------------------------|
| **Platform** | `/platform` | `ml/models/gnn`, `app/api/v1/ai.py` | `POST /ai/recommend-industry` · `POST /ai/predict-vacancy` · `GET /commercial-districts/{id}/sentiment` | `getSentiment(id)` |
| **Page** | `/page` | `frontend/src/lib/naverMap.ts`, `app/api/v1/heatmap.py` | `GET /heatmap/vacancy?district=` · `GET /buildings/{id}/history` | `getVacancyHeatmap(id)` · `getBuildingHistory(id)` |
| **Posting** | `/posting` | `app/services/posting.py`, `ml/models/lstm` | `POST /ai/simulate-revenue`(확장) · `GET /commercial-districts/{id}/postings` | `getPostings(id)` |
| **Program** | `/program` | `app/services/marketing.py`, `app/api/v1/marketing.py` | `GET /marketing/{id}` · `POST /marketing/generate` | `getMarketing(id)` |
| **Design** | `/design` | `design/tokens`, `frontend/src/design`, `src/pages` | (통합 — 위 전부 소비) | `listDistricts()` · `getDistrict(id)` |

> 이 표가 리드의 핵심 자산이다. 트랙 전환 = 이 행 하나로 점프. 슬래시 명령이 같은 정보를 컨텍스트에 자동 로딩한다(4.2).

### 2.3 "한 곳만 본다" 규칙 (컨텍스트 위생)
트랙을 바꿀 때 다른 트랙 폴더는 건드리지 않는다. 각 슬래시 명령에 **화이트리스트 경로**가 박혀 있어, 리드가 전 권한을 가져도 트랙 간 오염을 막는다.

### 2.4 리드 작업물 보관 — PRD 초안
트랙별 PRD(요구사항) 초안은 `docs/prd/{track}/`에 모은다(없으면 생성). 생성된 결과 코드는 2.2의 정규 폴더로 들어간다.
```
docs/prd/
├── platform/   page/   posting/   program/   design/
```

### 2.5 데이터 레이크 · 디자인 토큰 (단일출처)
- **데이터** — 항상 `Bronze → Silver → Gold` 단방향. 대용량 레이어는 `.gitignore`로 git 제외(이미 설정됨), S3/GCS로 관리. 상세 폴더 규약은 팀원 가이드 3장 참조.
- **디자인 토큰** — 단일출처는 `design/tokens/tokens.json`. 코드 토큰 `apps/frontend/src/design/tokens/*.ts`와 항상 동기화. 색 하드코딩 금지(공실색은 `vacancy` 배열).

---

## 3. 트랙 전환 프롬프트

### 3.1 전환의 기본형 — 슬래시 한 줄
각 트랙 슬래시 명령은 ① 역할 고정 ② 관련 `docs/feature-*.md` 자동 읽기 ③ 화이트리스트 경로·실제 엔드포인트 주입 ④ 작은 작업 분해를 한 번에 한다.
```text
/platform <목표>     /page <목표>     /posting <목표>     /program <목표>     /design <목표>
```
예:
```text
/page 라페스타 공실 히트맵을 네이버 지도 위에 색상으로 표시하고, 건물 클릭 시 과거 3년 업종 변천사 패널을 띄워줘
```

### 3.2 하루의 시작 — 오케스트레이션
```text
/pppp-status 오늘은 라페스타 B2B 데모 준비에 집중
```
→ 전 트랙의 구현/더미/미착수 현황표 + 트랙별 1개씩 3~5개 작업 제안 + 각 작업의 진입 슬래시까지 제시한다.

### 3.3 트랙 전환 시 컨텍스트 위생
한 트랙을 끝내고 다른 트랙으로 갈 때:
```text
/clear            # 이전 트랙 컨텍스트 비우기
/posting 라페스타 1층 공실에 고급화/가성비/기능중심 3축 ROI 시뮬레이션 카드 만들어줘
```
> 같은 세션에서 트랙을 섞으면 컨텍스트가 오염된다. **전환 = `/clear` → 슬래시 명령**을 습관화.

### 3.4 병렬 작업 — 서브에이전트 위임
리드가 한 트랙을 보는 동안, 독립적인 작업은 서브에이전트(`.claude/agents/`)에 위임한다.
```text
data-engineer 서브에이전트로 라페스타 네이버플레이스 리뷰를 data/bronze/platform/reviews 에 수집해줘.
그동안 나는 /page 작업을 계속한다.
```
| 위임 대상 | 서브에이전트 | 적합 작업 |
|-----------|-------------|-----------|
| 수집·ETL | `data-engineer` | 크롤링, Bronze/Silver/Gold, 주소 정규화 |
| 모델 | `ml-engineer` | LSTM/GNN 학습·서빙, MLflow |
| 화면·토큰 | `fe-designer` | 네이버지도·3D·디자인시스템 |

### 3.5 PRD 6칸 템플릿 (모호하면 이걸로)
슬래시 명령에 목표만 줘도 되지만, 정밀도가 필요하면 6칸을 채워 붙인다.
```text
# 역할(Role)       너는 SpaceOS {트랙} 담당. CLAUDE.md 준수.
# 목표(Goal)       {한 문장}
# 입력(Input)      경로 {silver/ 또는 gold/}, 스키마 {컬럼:타입}
# 제약(Constraint) 확정 스택만 / 한국어 주석(영문 병기) / 더미엔 TODO / 타입힌트
# 산출물(Deliver)  파일 {정확한 경로}, 인터페이스 {함수/엔드포인트}
# 검증(Verify)     {통과 기준: 테스트/빌드/스크린샷}
```

---

## 4. 적용 코드 (실제 생성된 설정)

본 플레이북과 함께 아래 파일이 레포에 **이미 생성**되어 바로 동작한다. (요지만 설명; 전체 내용은 각 파일 참조)

### 4.1 리드 개인 권한 — `.claude/settings.local.json` ★ "팀원과 다른 셋팅"의 정체
- 공용 `settings.json`은 그대로 두고, 리드는 **개인** `settings.local.json`을 쓴다 (git 무시됨 — `.gitignore`에 추가 완료).
- 차이: 전 트랙 `Edit(apps/** · ml/** · data/** · design/** · docs/** · .claude/**)` 허용 + `git commit`·`grep`·`mlflow` 허용. 위험 명령(`rm -rf`, `git push`, `.env` 읽기)은 차단.
- 적용: 템플릿을 복사만 하면 된다.
```powershell
Copy-Item .claude\settings.lead.json .claude\settings.local.json
```

### 4.2 PPPP 슬래시 명령 — `.claude/commands/*.md`
`/platform /page /posting /program /design` + `/pppp-status`(오케스트레이션) + `/verify`(공통 검증). 각 파일은 트랙 역할·읽을 문서·화이트리스트 경로·실제 엔드포인트·`$ARGUMENTS` 목표 주입을 담는다. 기존 레이어 명령(`/backend-dev /frontend-dev /ml-train`)과 공존한다.

### 4.3 서브에이전트 — `.claude/agents/*.md`
`data-engineer · ml-engineer · fe-designer`. 리드가 위임하면 각자 **격리된 컨텍스트**에서 자기 폴더만 작업해 메인 컨텍스트를 아낀다.

### 4.4 프로젝트 MCP — `.mcp.json`
`postgres`(PostGIS 쿼리) · `filesystem`(`./data`) · `github`. 키는 `.env`/환경변수로(커밋 금지). 확인: `claude mcp list`. 개인 전용 MCP는 `claude mcp add <name> -s user -- <cmd>`로 추가.

### 4.5 멀티터미널 부트스트랩 (선택) — `scripts/dev-up.ps1`
서버 2개를 새 PowerShell 탭으로 띄우는 스니펫. 필요 시 아래를 `scripts\dev-up.ps1`로 저장해 실행.
```powershell
# scripts/dev-up.ps1 — 백엔드(:8000) + 프론트(:5173) 동시 기동
$root = "C:\Users\USER\Documents\Claude\Projects\SpaceOS"
Start-Process powershell -ArgumentList "-NoExit","-Command","cd $root\apps\backend; uvicorn app.main:app --reload"
Start-Process powershell -ArgumentList "-NoExit","-Command","cd $root\apps\frontend; npm run dev"
Write-Host "backend :8000 / frontend :5173 기동. claude 는 루트 탭에서 별도 실행."
```

---

## 5. 일일 운영 루프 & 체크리스트

### 5.1 리드의 하루 루프
```
① 루트에서 claude  →  ② /pppp-status (현황 + 오늘 할 일)
   →  ③ 트랙 선택: /clear → /page(또는 /platform…) <목표>
   →  ④ 작은 작업 승인하며 진행  →  ⑤ /verify
   →  ⑥ git commit (트랙·기능 단위, 예: feat(page): 공실 패널)
   →  다음 트랙은 ③으로
```

### 5.2 빠른 시작 체크리스트
- [ ] 레포 루트에서 터미널 열기 (`C:\Users\USER\Documents\Claude\Projects\SpaceOS`)
- [ ] `npm i -g @anthropic-ai/claude-code` → `claude` 인증
- [ ] `Copy-Item .claude\settings.lead.json .claude\settings.local.json`
- [ ] `claude mcp list`로 postgres/filesystem/github 확인
- [ ] T2 `uvicorn …`(:8000) · T3 `npm run dev`(:5173) 기동
- [ ] `/pppp-status`로 시작 → 트랙별 `/clear` + 슬래시 명령 → `/verify` → commit

### 부록 A. 트러블슈팅
| 증상 | 원인 | 해결 |
|------|------|------|
| 네이버 지도 안 뜸 | NCP 도메인 미등록 | NCP 콘솔 Maps Application Web URL에 `http://localhost:5173` 등록, `.env`의 `VITE_NAVER_MAPS_KEY_ID` 확인 |
| `/api` 404 | 백엔드 미기동 | T2에서 `uvicorn app.main:app --reload`(:8000). Vite 프록시 `/api`→:8000 |
| `Activate.ps1` 차단 | 실행정책 | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| 한글 docx □ 깨짐 | 폰트 미임베딩 | 문서 산출 시 Pretendard subset 임베딩 (팀원 가이드/메모 참조) |
| 슬래시 명령 안 보임 | 실행 위치 | 레포 루트에서 `claude` 실행해야 `.claude/commands` 로드 |

### 부록 B. 기존 문서와의 관계
- **팀원 공용**: `SpaceOS_PPPP_Design_Vibe_Coding_Guide.md` (용어·공통셋업·데이터구조·트랙별 코드)
- **프롬프트 모음**: `docs/VIBE-PROMPTS.md`, `docs/DESIGN-VIBE-PROMPTS.md`
- **트랙 상세**: `docs/feature-*.md`
- **본 문서**: 그 위에 얹는 **리드 오케스트레이션** (터미널·전환·권한·위임)

> **한 줄 요약** — 루트에서 `claude` → `/pppp-status`로 펼치고 → `/clear` + 트랙 슬래시로 좁히고 → `/verify`로 닫는다.
