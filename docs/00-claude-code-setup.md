# 00. Claude Code 설치 및 공통 설정

SpaceOS를 Claude Code(CLI)로 개발하기 위한 공통 준비 가이드. 기능별 개발은 `feature-*.md` 문서를 참고한다.

---

## 1. 설치

Claude Code는 Node.js 18+ 환경에서 npm으로 설치한다.

```bash
# Node 버전 확인 (18 이상)
node -v

# 전역 설치
npm install -g @anthropic-ai/claude-code

# 설치 확인
claude --version
```

> Windows는 PowerShell 또는 WSL2에서 실행한다. Docker/PostGIS 작업이 많으므로 WSL2를 권장한다.

---

## 2. 인증

```bash
# 프로젝트 폴더에서 최초 1회 실행 → 브라우저 로그인
cd C:\Users\USER\Documents\Claude\Projects\SpaceOS
claude
```

최초 실행 시 Anthropic 계정(또는 API 키)으로 로그인한다. 로그인 방식은 `/login` 슬래시 커맨드로 언제든 변경할 수 있다.

---

## 3. 프로젝트 연결 (이미 셋업됨)

이 저장소에는 Claude Code가 자동으로 읽는 설정이 이미 들어 있다.

| 파일 | 역할 |
|------|------|
| `CLAUDE.md` | 프로젝트 컨텍스트·코드베이스 가이드·코드 규칙 (세션 시작 시 자동 로드) |
| `.claude/settings.json` | 권한 허용/거부 목록 (`.env` 읽기 차단 등) |
| `.claude/commands/*.md` | 슬래시 커맨드 (`/backend-dev`, `/frontend-dev`, `/ml-train`) |

처음 한 번 git 초기화가 필요하다(샌드박스 권한 문제로 자동화하지 못함).

```powershell
cd C:\Users\USER\Documents\Claude\Projects\SpaceOS
git init; git add -A; git commit -m "init: SpaceOS 모노레포 골격"
```

---

## 4. 기본 워크플로우 (바이브 코딩)

SpaceOS는 "자연어 PRD → AI 코드 생성 → 검증" 사이클로 개발한다.

1. **컨텍스트 부여** — Claude Code는 `CLAUDE.md`를 자동 로드한다. 추가 파일은 `@경로`로 참조: `@apps/backend/app/api/v1/ai.py 를 참고해서...`
2. **슬래시 커맨드로 작업 지시** — 예: `/backend-dev 공실 히트맵 GeoJSON 엔드포인트`
3. **검증** — 백엔드는 `pytest`, 프론트는 `npm run build`, ML은 학습 스크립트 실행. CLAUDE.md의 성능 목표(정확도 70%+, 맵 로딩 <3초, API p95 <200ms)를 기준으로 확인.
4. **커밋** — 기능 단위로 작게 커밋.

### 자주 쓰는 슬래시 커맨드

```
/backend-dev <기능>    # FastAPI 라우터/스키마/서비스 추가
/frontend-dev <기능>   # React 컴포넌트/페이지 추가
/ml-train <작업>       # LSTM/GNN 모델 개발·학습
/clear                 # 컨텍스트 초기화 (작업 전환 시)
/review                # PR/변경 코드 리뷰
```

---

## 5. 기능 ↔ 코드 영역 매핑 (PPPP)

| 기능 | 의미 | 주요 코드 영역 | 가이드 |
|------|------|--------------|--------|
| **Platform** | 상권 AI 추천 엔진 | `ml/`, `apps/backend/app/api/v1/ai.py` | [feature-platform.md](feature-platform.md) |
| **Page** | 공실 히트맵 + 3D 디지털 트윈 | `apps/frontend/`, `apps/backend`(buildings/heatmap) | [feature-page.md](feature-page.md) |
| **Posting** | 입점 솔루션(비용-효용 분석) | `apps/backend`(services), `ml`(시뮬) | [feature-posting.md](feature-posting.md) |
| **Program** | LLM 마케팅 자동화 + 행사 추천 | `apps/backend`(marketing), LLM 연동 | [feature-program.md](feature-program.md) |

공통 데이터 기반은 `data/`(Bronze→Silver→Gold)이며 모든 기능이 Gold 레이어(PostGIS)를 소비한다.
