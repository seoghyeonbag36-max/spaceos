# 01. 앱 디자인 핸드오프 — 외부 작업자용 Claude Code 셋업

SpaceOS의 앱/UI 디자인과 프론트엔드 구현을 **다른 작업자**에게 맡기기 위한 인수인계 가이드. 작업자는 Claude를 처음 쓰며, 프로젝트 파일을 **본인 컴퓨터로 옮겨** 작업하는 상황을 전제로 한다.

작업 범위는 두 가지를 모두 포함한다.
- **디자인 시안/프로토타입** — 화면 흐름·레이아웃·컴포넌트 시안 (이미지/Figma 참조 → 코드 변환)
- **프론트엔드 구현** — React + TypeScript로 실제 화면/컴포넌트 구현 (`apps/frontend`)

---

## 1. 파일 전달 (오너 → 작업자)

### 1-1. 무엇을 전달하나
프로젝트 루트 `SpaceOS/` 폴더 전체를 전달한다. 단, 아래는 **제외**한다.

| 제외 대상 | 이유 |
|----------|------|
| `.env`, `**/.env` | API 키·DB 비밀번호 등 비밀값. 절대 공유 금지 |
| `node_modules/`, `.venv/` | 용량이 크고 작업자가 직접 설치 (`npm install`) |
| `data/bronze|silver|gold/*` | 대용량 원본 데이터. 디자인 작업엔 불필요 |
| `.git/`(선택) | 깃 이력. 새로 시작해도 무방 |

> `.gitignore`가 위 항목을 이미 추적 제외하므로, **git으로 압축하면 자동으로 빠진다**.

### 1-2. 전달 방법 (택1)
- **권장 — Git 원격 저장소**: 오너가 GitHub/GitLab 비공개 저장소에 푸시 → 작업자가 `git clone`. 이력·협업·되돌리기에 유리.
  ```powershell
  # 오너 측 (최초 1회)
  cd C:\Users\USER\Documents\Claude\Projects\SpaceOS
  git init; git add -A; git commit -m "init: SpaceOS"
  git remote add origin <비공개_저장소_URL>
  git push -u origin main
  ```
  ```bash
  # 작업자 측
  git clone <비공개_저장소_URL> SpaceOS
  ```
- **대안 — 압축 파일 전달**: 폴더를 zip으로 압축해 클라우드(드라이브)로 공유. 단 `node_modules`·`.venv`·`.env`는 빼고 압축.

### 1-3. 작업자가 받은 뒤 확인할 것
파일에 다음이 들어 있으면 정상이다.
- `CLAUDE.md` — 프로젝트 컨텍스트 (Claude Code가 자동 로드)
- `.claude/settings.json`, `.claude/commands/*.md` — 권한·슬래시 커맨드
- `apps/frontend/` — 작업 대상 프론트엔드
- `docs/` — 본 가이드 포함 개발 문서

---

## 2. 작업자 컴퓨터 사전 준비물

| 도구 | 버전/비고 | 설치 |
|------|----------|------|
| **Node.js** | 18 이상 (LTS 권장) | https://nodejs.org |
| **Git** | 최신 | https://git-scm.com |
| **Claude 계정** | Claude Code 사용 권한 (Pro/Max 또는 API 키) | https://claude.com |
| 코드 에디터 | VS Code 또는 Cursor 권장 | — |

설치 확인:
```bash
node -v        # v18+ 출력
git --version
```

---

## 3. Claude Code 설치 & 로그인 (작업자, 처음 사용)

```bash
# 1) 전역 설치
npm install -g @anthropic-ai/claude-code

# 2) 프로젝트 폴더로 이동
cd SpaceOS        # (clone 또는 압축 해제한 위치)

# 3) 실행 → 최초 1회 브라우저 로그인
claude
```

- 첫 실행 시 브라우저가 열리며 Claude 계정 로그인을 요청한다. 로그인하면 이후 자동 인증된다.
- 로그인 방식 변경은 세션 안에서 `/login` 입력.
- 실행되면 Claude Code가 `CLAUDE.md`를 자동으로 읽어 프로젝트 맥락(PPPP, 기술 스택, 코드 규칙)을 인식한다.

> 자세한 공통 설정은 [00-claude-code-setup.md](00-claude-code-setup.md) 참고.

---

## 4. 프론트엔드 실행 (디자인 미리보기 환경)

디자인/구현 결과를 눈으로 보려면 개발 서버를 띄운다.

```bash
cd apps/frontend
npm install            # 의존성 설치 (react, three, mapbox-gl 등)
npm run dev            # http://localhost:5173
```

- Mapbox 지도가 필요한 화면은 토큰이 있어야 한다. 작업자는 본인 무료 토큰을 발급(https://account.mapbox.com)받아 `apps/frontend/.env`에 넣는다.
  ```
  VITE_MAPBOX_TOKEN=pk.작업자_본인_토큰
  ```
- 백엔드 데이터가 필요 없는 순수 UI 작업이라면 백엔드를 띄우지 않아도 화면 디자인은 가능하다(데이터는 목업으로).

---

## 5. 디자인 워크플로우 (시안 → 코드)

Claude Code는 이미지·스케치를 보고 코드로 옮길 수 있다.

1. **참조 자료 제공** — Figma 캡처, 손그림, 벤치마크 스크린샷을 프로젝트 폴더(예: `docs/design-refs/`)에 넣고 세션에서 `@docs/design-refs/home.png` 로 참조.
2. **시안 생성/구현 지시** — 슬래시 커맨드 활용:
   ```
   /frontend-dev 첨부 시안(@docs/design-refs/home.png)을 기반으로
     상권 대시보드 홈 화면을 만들어줘. 좌측에 공실 히트맵 지도,
     우측에 선택 건물의 공실 히스토리 패널. Tailwind 스타일.
   ```
3. **반복(바이브 코딩)** — "여백을 더 넓게", "카드 그림자 제거", "모바일에서 1열로" 처럼 자연어로 수정 → 즉시 코드 반영 → `localhost:5173`에서 확인.
4. **컴포넌트 규칙 준수** — 컴포넌트는 `src/components/`, 페이지는 `src/pages/`, API 호출은 `src/lib/api.ts`로 일원화, 경로 별칭 `@/` 사용 (CLAUDE.md 규칙).

### 화면 ↔ 기능(PPPP) 연결
구현할 주요 화면은 PPPP 기능과 매핑된다. 데이터 연동이 필요하면 해당 가이드를 참고.

| 화면 | 기능 | 참고 |
|------|------|------|
| 공실 히트맵·3D 트윈 맵 | Page | [feature-page.md](feature-page.md) |
| AI 업종 추천·매출 시뮬 결과 | Platform | [feature-platform.md](feature-platform.md) |
| 입점 전략 비교(ROI) 화면 | Posting | [feature-posting.md](feature-posting.md) |
| 마케팅 콘텐츠 생성 UI | Program | [feature-program.md](feature-program.md) |

---

## 6. 검증 & 마무리

작업 후 작업자가 확인할 것:
```bash
cd apps/frontend
npm run build          # 타입체크 + 빌드 통과해야 함
```
- 브라우저에서 디자인 의도대로 렌더되는지, 반응형 동작 확인
- 3D 맵이 있는 화면은 **로딩 3초 이내** (CLAUDE.md 성능 목표)

결과 반환(작업자 → 오너):
- Git을 쓰면 기능 단위로 커밋 후 push, 또는 Pull Request 생성
- 압축 전달이면 `node_modules`·`.env` 제외하고 다시 압축해 전달

---

## 7. 작업자 온보딩 체크리스트

- [ ] Node 18+, Git 설치 확인
- [ ] SpaceOS 폴더 수령 (`.env`·`node_modules` 제외 정상)
- [ ] `npm install -g @anthropic-ai/claude-code` 설치
- [ ] 프로젝트 폴더에서 `claude` 실행 + 로그인
- [ ] `cd apps/frontend && npm install && npm run dev` → localhost:5173 확인
- [ ] (지도 화면 시) 본인 Mapbox 토큰을 `apps/frontend/.env`에 설정
- [ ] `/frontend-dev` 슬래시 커맨드로 첫 화면 시안 작업 시도
- [ ] `npm run build` 통과 확인 후 커밋/전달

> 비밀값(`.env`, API 키)은 절대 커밋·공유하지 않는다. `.claude/settings.json`이 `.env` 읽기를 차단하도록 이미 설정돼 있다.
