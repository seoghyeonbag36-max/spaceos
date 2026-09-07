# SpaceOS 모바일 작업 프롬프트

**2026-09-06 전면 재작성.** 이전 판은 "서울 25구"·"미구현 엔드포인트는 mock + TODO"
기준이었는데 **둘 다 낡았다** — 지금은 66거점이고 그 엔드포인트들은 배선이 끝났다.
옛 프롬프트를 그대로 붙여넣으면 **이미 있는 것을 다시 만든다.**

상태는 이 문서가 아니라 스크립트에서 읽는다:

```bash
python scripts/pppp_status.py | grep -v '└'   # 진행률·게이트
python scripts/chain_status.py --all          # 거점별 체인
```

---

## 0. 두 경로 — 무엇을 고르느냐로 할 수 있는 일이 갈린다

| | **클라우드 세션** (claude.ai/code) | **데스크톱 Dispatch** |
|---|---|---|
| 무엇에 붙나 | GitHub `origin/main` | 켜져 있는 내 데스크톱 |
| 데스크톱 필요 | ❌ | ✅ 절전 억제 필수 |
| 프론트·백엔드·문서 | ✅ | ✅ |
| **수집 (건축HUB·R-ONE·네이버)** | ❌ **불가** | ✅ |
| **GNN/LSTM 재학습** | ❌ **불가** | ✅ |
| 네이버 지도 픽셀 확인 | ❌ | ✅ |

### 왜 클라우드에서 수집·학습이 안 되나

`.gitignore` 가 `data/bronze/*` · `data/silver/*` · `*.parquet` 를 막는다.
클라우드 세션은 새 클론이라 **원천 데이터가 없다.** 반면 `data/gold` 는 566개 파일이
git 에 실려 있어서 **테스트·분석·서빙 코드는 그대로 돈다**(CI 가 매 푸시마다 증명한다).

### 클라우드 세션의 절대 조건

**커밋 안 된 작업은 안 보인다.** 폰에서 열기 전에 데스크톱에서:

```bash
git status --short   # 비어 있어야 한다
git push origin main # 백그라운드로 (GCM 인증 창 때문에 포그라운드는 타임아웃)
```

---

## 1. 회원가입·로그인·API키 화면 (클라우드 · KPI② 직결)

> **2026-09-06 웹 디자인 멘토링 이후에 시작한다.** 그 전에 만들면 다시 만든다.
> 백엔드는 2026-08-27 에 이미 섰고 E2E 통과했다 — 막힌 것은 사람이 보는 화면뿐이다.

```
apps/frontend 에 계정 화면 3종을 만든다. 백엔드는 이미 있다 — 새로 만들지 말 것.

기존 엔드포인트: POST /api/v1/auth/signup · /auth/login · /auth/api-keys
(apps/backend/app/api/v1/ 에서 실제 스키마를 먼저 읽고 그 계약에 맞춘다)

1. src/pages/ 에 Signup · Login · ApiKeys 를 추가한다. 기존 페이지들
   (MapShell · PageDashboard · PlatformConsole · PostingConsole · ProgramStudio)과
   같은 셸·토큰을 쓴다 — 새 레이아웃 체계를 만들지 않는다.
2. API 호출은 src/lib/api.ts 로 일원화(직접 fetch 금지). 경로 별칭은 @/.
3. 스타일은 src/design/tokens + styles/tokens.css. Tailwind 를 새로 깔지 않는다.
4. API 키는 발급 직후 한 번만 보이고 이후 마스킹 — 폐기 확인 단계를 둔다.
5. npm run build (타입체크 포함) 통과까지 확인.

완료되면 변경 파일과 각 화면이 치는 엔드포인트를 알려줘.
```

⚠ 멘토링에서 정해진 디자인 방향을 프롬프트에 같이 넣을 것. 안 넣으면 임의로 만든다.

---

## 2. 디자인 시스템 정리 (클라우드)

`docs/feature-design-system.md` 가 36줄로, 다른 feature 문서(600~1,500줄)에 비해 유독 얇다.

```
apps/frontend 의 디자인 토큰을 단일 기준으로 정리한다.

1. src/design/tokens 와 styles/tokens.css 의 색·타이포·간격을 대조해
   불일치를 찾고 한쪽으로 맞춘다. 무엇이 어긋나 있었는지 먼저 보고할 것.
2. 6개 화면(MapShell · PageDashboard · PlatformConsole · PostingConsole ·
   ProgramStudio · HubExplorer)이 공유하는 셸을 컴포넌트로 뽑는다.
   기존 화면 동작을 바꾸지 않는다 — 순수 리팩터.
3. Storybook 은 없다(2026-09-06 삭제). story 파일을 만들지 말 것.
4. 정리한 기준을 docs/feature-design-system.md 에 적는다.

npm run build 통과 확인. 화면 동작이 바뀌었다면 그건 실패다.
```

---

## 3. 논문 절 채우기 (클라우드 또는 Codex)

`docs/papers/` 에 뼈대와 근거 인덱스가 있다. **한 번에 한 절만** 채운다.

```
docs/papers/paper-platform.md 의 §3.2(성능 천장 4회 확인)만 채운다.

근거: docs/papers/evidence-index.md 의 "성능 천장 — 4회 독립 확인" 표.
분량: 400~600자 + 표.
금지: 그 표 밖의 수치 · 문헌 인용 · 다른 절 건드리기.
규칙: docs/papers/AGENTS.md 를 먼저 읽을 것.
```

⚠ **논문 디렉터리에서 가장 하기 쉬운 실수는 그럴듯한 가짜 인용이다.**
문헌이 필요한 자리는 채우지 말고 `<!-- TODO(문헌): ... -->` 로 비워 두게 할 것.

---

## 4. 데스크톱 Dispatch 로만 되는 것

아래는 클라우드에서 **시작조차 못 한다.** 데스크톱이 켜져 있고 절전이 억제된 상태여야 한다.

- **건축HUB 대장 수집** → `/quota` 스킬 (프리플라이트 → 재개 → 소진 시 층별개요)
- **GNN/LSTM 재학습** → `OMP_NUM_THREADS=1 PYTHONIOENCODING=utf-8` 필수
- **새 거점 온보딩** → `/hub-chain` (후보 판정 → 등록 → 수집 → Gold → 앵커 → 서빙 → 검증)
- **`/verify` 전체** — 로컬 앱을 띄워 지도 픽셀까지 보는 단계는 GUI 가 필요하다

장시간 무인 실행 규칙은 `/autorun` 스킬에 있다(절전 억제·인코딩·체크포인트).

---

## 5. 어느 경로든 지키는 것

- **응답·주석·문서는 한국어**, 기술 용어 영문 병기
- **더미 데이터에는 `TODO` 주석으로 실제 연동 지점을 명시** — 근거 없는 값을 채우지 않는다
- **3D(@react-three/fiber)를 새로 깔지 않는다** — 2026-09-05 제거됨(`feature-posting.md` §0-V)
- **mapbox-gl 을 다시 끌어오지 않는다** — 2026-08-25 제거됨. 베이스맵은 네이버뿐
- **`vercel --prod` 를 쓰지 않는다** — 2026-08-28 Cloud Run 으로 이전(무료 플랜 상업적 사용 금지)
- 배포는 `main` 푸시로 자동 (Firebase Hosting → Cloud Run, https://spaceos-twin.web.app)
