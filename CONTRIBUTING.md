# SpaceOS 팀 개발 표준 (CONTRIBUTING)

> 목표: 팀 전원이 **동일한 저장소 + 동일한 환경**에서 일한다.
> 폴더를 복사하지 않는다 — `git clone` 한다. `.env`(시크릿)와 실데이터는 절대 공유하지 않는다.

대상 도구: **GitHub**(단일 진실 공급원) · **GitHub Desktop**(git 워크플로우) · **VS Code**(개발 환경)

---

## 0. 절대 규칙 (3가지)

1. **폴더 통째 복사·동기화 금지.** 저장소는 `git clone`으로만 받는다. 작업 폴더를 Dropbox·OneDrive·Google Drive 같은 동기화 폴더 아래 두지 않는다(= `.git` 손상·덮어쓰기 충돌 방지).
2. **`.env`는 공유·커밋 금지.** 각자 `.env.example`을 복사해 본인 키를 채운다.
3. **`.git` 변경은 GitHub Desktop UI로만.** 터미널에서 `.git` 내부를 직접 건드리지 않는다.

---

## 1. 최초 1회 셋업 (신규 팀원)

### 1-1. 저장소 받기 — GitHub Desktop
1. GitHub Desktop 설치 후 본인 GitHub 계정으로 로그인.
2. **File → Clone repository → `seoghyeonbag36-max/spaceos`** 선택 → 로컬 경로 지정 → Clone.
   - 경로는 동기화 폴더(OneDrive 등)가 **아닌** 일반 폴더로 (예: `C:\dev\spaceos`).
3. **Preferences → Git** 에서 **Name / Email**을 본인 것으로 설정(커밋 작성자 정확히).

### 1-2. 환경 변수 — `.env`
각 디렉터리의 `.env.example`을 같은 위치에 `.env`로 복사한 뒤 값을 채운다.
- `apps/frontend/.env.example` → `apps/frontend/.env`
- `apps/backend/.env.example` → `apps/backend/.env`
- `data/.env.example` → `data/.env`

공용 키(네이버 등)는 git이 아니라 **팀 시크릿 매니저/비밀 채널**로 전달받는다.

### 1-3. VS Code 열기
1. VS Code에서 **clone한 폴더를 연다**.
2. 우하단 "권장 확장을 설치하시겠습니까?" 팝업 → **설치** (또는 확장 탭에서 `@recommended`).
   - 표준 확장: Python · Pylance · Ruff · ESLint · Prettier · Docker · YAML.
3. 저장 시 자동 포맷·테스트 탐색 등은 `.vscode/settings.json`으로 이미 통일돼 있다.

### 1-4. 의존성 설치 / 실행
**방법 A — 로컬**
```
# Backend
cd apps/backend && pip install -r requirements.txt && uvicorn app.main:app --reload
# Frontend
cd apps/frontend && npm install && npm run dev
# ML 골격
cd ml && pip install -r requirements.txt
```
**방법 B — Docker (권장, 환경 동일)**
```
docker compose -f infra/docker/docker-compose.yml up
```

---

## 2. 일상 작업 흐름 (전원 동일) — GitHub Desktop

1. **Fetch origin**으로 최신 `main` 받기.
2. **Current Branch → New Branch** → `feature/<작업명>` (또는 `fix/`, `docs/`).
3. VS Code에서 작업 → 저장(자동 포맷).
4. GitHub Desktop에서 변경 확인 → **Commit to `feature/...`** (메시지: 무엇을·왜).
5. **Push origin** → **Create Pull Request**.
6. 리뷰 1건 통과 후 **Merge**. `main`에 직접 커밋하지 않는다.

> `main`은 GitHub에서 **브랜치 보호**로 직접 push가 막혀 있다(아래 3-2).

---

## 3. 리드 1회 설정 (GitHub 웹)

1. **팀원 초대**: 저장소 → Settings → Collaborators → 팀원 GitHub 계정 추가. (또는 Organization으로 이전 후 팀 단위 관리.)
2. **`main` 브랜치 보호**: Settings → Branches → branch protection/ruleset →
   - Require a pull request before merging (+ 최소 1 approval)
   - Require status checks to pass (CI 추가 시)
   - Do not allow bypassing
3. **시크릿 키 점검**: GitHub Desktop **History**에서 `.env`가 과거 커밋에 포함된 적 있는지 확인. 있었다면 노출 키(네이버 등)를 **즉시 재발급(회전)**.

---

## 4. 커밋하면 안 되는 것 (이미 `.gitignore` 처리됨)

`.env`(모든 변형) · `__pycache__`·`.pytest_cache`·`*.pyc` · `node_modules`·`dist` · 데이터 레이크(`data/bronze|silver|gold`) · `mlruns` · `*.pem`·`secrets/`.

→ 공유되는 것은 **`.env.example`**(키 이름만), 실데이터는 **S3 데이터 레이크**, 모델은 **MLflow/레지스트리**에 둔다.
