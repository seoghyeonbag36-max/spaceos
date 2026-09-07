# 2026-09-08 Claude Code Cloud 작업표 — 제품 코드 트랙

회사 업무 중에 **휴대폰에서 Claude Code Cloud** 로 돌린다. 시간은 한국시간(KST) 09:00~18:00.
아래 시각은 프롬프트를 보낼 권장 시각이며 자동 예약이 아니다.

논문 트랙(`docs/cloud-workday-2026-09-08.md` 의 A1~A6)은 **이 표에 넣지 않는다.** 같은 원고를 두
에이전트가 만지면 충돌한다. 내일 Claude Code Cloud 는 제품 코드만 만지고, 파일이 겹치지 않는다.

---

## 왜 이 작업들인가 — 2026-09-07 실측

어제 화면 회귀 루프(`scripts/screen_loop.py`)를 66거점 × 4탭 = 264조합으로 처음 전수 실행했고,
**69조합에서 중단**됐다(`reports/screen_loop.json` 의 `finished` 가 없다). 거기까지의 판정은:

| 판정 | 수 |
|---|---|
| pass | 42 |
| fail | 17 |
| error | 10 |

실패를 원인별로 묶으면 이렇다.

| 단계 | 방아쇠 | 건수 | 관측 |
|---|---|---|---|
| S4 | `hub-switch` | 14 | map 탭 거점 전환 렌더가 예산 3,000ms 를 넘는다 |
| S0 | — | 10 | 조작 자체가 20초 타임아웃 (`.hub-select:not([disabled])` 대기, Posting 버튼 클릭) |
| S4 | `tab-open` | 3 | 첫 렌더 4,750 / 5,078 / 7,375ms |
| S3 | — | 2 | 사이드패널 제목 0개 · 거점을 바꿨는데 heatmap 을 안 부른다 |

**가장 중요한 관측** — map 탭 `hub-switch` 렌더 시간이 거점을 바꿀수록 **단조 증가한다.**

```
13234 → 18203 → 24172 → 29969 → 36234 → 37469 → 39422
      → 40328 → 43218 → 43219 → 48046 → 48860 → 234687   (ms)
```

같은 화면을 같은 방식으로 여는데 시간이 계속 늘어난다. 이건 "느리다"가 아니라 **무언가가 쌓인다**는
신호다. 마지막 관측은 234초다. KPI 1순위가 "지도·건물 상세 로딩 3초 이내"이므로 이 한 줄이
제품 완성도 목표를 직접 깨고 있다.

⚠ 위 숫자는 **중단된 실행의 69조합**에서 나온 것이다. 264조합 전체의 실패율이 아니고,
남은 195조합이 같은 비율일 것이라고 가정하지 않는다.

---

## Claude Code Cloud 에서 되는 것과 안 되는 것

컨테이너는 GitHub 저장소를 체크아웃해서 돈다. **PC 의 로컬 파일·로컬 서버·API 키를 갖고 있지 않다.**

| 된다 | 안 된다 |
|---|---|
| 저장소 코드 읽기·수정·커밋·푸시·PR | 로컬 dev 서버(`npm run dev`) 를 띄워 화면 확인 |
| `apps/backend` · `data/tests` pytest (CI 와 같은 조건) | 네이버 지도 렌더 — 키가 없고 브라우저도 없다 |
| `npm ci && npm run build && npm run lint` (네트워크 허용 시) | Playwright 화면 회귀 재실행 |
| `data/gold/*` 직독 — 저장소에 실려 있다 | 건축HUB·공공 API 수집 (키·쿼터 없음) |
| `docs/` 근거 문서 작성 | `private/` 파일 · 로컬 미커밋 변경 읽기 |

여기서 나오는 **가장 중요한 규율**: 클라우드는 화면을 띄울 수 없으므로,
어떤 수정도 "고쳤다"가 아니라 **"근거를 적은 가설 수정"**이다.
실증은 저녁에 PC 에서 `python scripts/screen_loop.py` 를 다시 돌려서 한다.
프롬프트마다 이걸 못 박아 뒀다 — 클라우드가 "성능이 개선됐다"고 쓰지 못하게 한다.

---

## 인계 방식

- 저장소: `seoghyeonbag36-max/spaceos`, PR base 는 `main`.
- **작업마다 별도 브랜치·별도 PR.** C1~C5 는 만지는 파일이 다르므로 순차 대기가 필요 없다.
  앞 작업이 늦어져도 다음 시각에 다음 작업을 보내면 된다.
- 브랜치 이름은 각 항목에 적어 뒀다. 클라우드가 다른 이름을 쓰면 그대로 두고 PR URL 만 챙긴다.
- 머지는 하지 않는다. **저녁에 PC 에서 검증한 뒤 머지한다** — 화면을 못 본 수정을 main 에
  올리면 `deploy.yml` 이 main push 에 반응해 프로덕션까지 나간다.

⚠ `reports/screen_loop.json` 은 오늘 origin 에 없다. 그래서 각 프롬프트에 **필요한 숫자를
직접 박아 뒀다.** 클라우드에게 그 파일을 읽으라고 하지 않는다.

---

## 시간표

| 시각 | ID | 작업 | 성격 | 산출물 |
|---|---|---|---|---|
| 09:00 | **C1** | 지도 거점 전환 렌더 단조 증가 — 원인 규명 | 읽기 전용 | 진단 문서 + PR |
| 10:30 | **C2** | C1 이 특정한 원인 수정 | 코드 수정 | 수정 PR |
| 13:00 | **C3** | S0 조작 실패 10건이 C1 과 같은 뿌리인가 | 판정 | 진단 문서 + PR |
| 14:30 | **C4** | 합정 heatmap 미호출 · 사이드패널 제목 결손 | 판정 + 수정 | PR |
| 16:00 | **C5** | 프론트 테스트 러너 도입 — 회귀를 코드로 고정 | 신규 | PR |
| 17:00 | **C6** | PR·CI 정리, 저녁 PC 검증 목록 | 정리 | 요약 |

지연되면 남은 작업을 생략해 완료로 만들지 않는다. 진행 중인 ID 를 이어서 끝낸다.
**C5 는 선택 항목이다** — C1~C4 가 밀리면 버린다.

---

## 공통 계약 — 모든 프롬프트에 적용된다

각 프롬프트에 "이 문서의 공통 계약을 적용하라"고 적혀 있다. 내용은 이렇다.

1. `CLAUDE.md`, `AGENTS.md` 를 읽고 시작한다. 코드 주석·문서는 한국어, 기술 용어는 영문 병기.
2. **화면을 띄우지 못했다는 사실을 결론에 남긴다.** "성능이 개선됐다" · "3초 이내로 들어왔다" ·
   "회귀가 해소됐다"고 쓰지 않는다. 쓸 수 있는 것은 "이 코드 경로가 원인일 근거"와
   "수정이 그 경로를 없앤다는 근거"까지다.
3. 예산 상수(3,000ms)·타임아웃·판정 기준을 **완화해서 통과시키지 않는다.** 명세가 틀렸다는
   근거를 찾으면 고치지 말고 보고한다.
4. `scripts/screen_loop.py`, `reports/*`, `apps/frontend/tsconfig.tsbuildinfo` 는 **건드리지 않는다.**
   PC 에 다른 세션의 미커밋 변경이 있다.
5. `data/`(bronze/silver/gold)·원천 수집기·`.github/workflows/deploy.yml` 은 수정하지 않는다.
   C5 만 `ci.yml` 에 잡을 추가할 수 있다.
6. `git add .` · `git add -A` · force push · main 직접 푸시·머지 금지. 명시 경로만 stage 한다.
7. 통과 조건은 실제로 돌려서 확인한다. `npm run build`(= `tsc -b && vite build`) 와
   `npm run lint` 가 통과해야 한다. 네트워크가 막혀 `npm ci` 가 안 되면 **그 사실을 적고**
   타입체크 미실행으로 보고한다 — 통과했다고 쓰지 않는다.
8. 최종 응답은 `완료 ID / 바꾼 파일 / 근거 / 실행한 검사와 결과 / 브랜치·SHA / PR URL /
   PC 에서 확인해야 할 것` 순서로 짧게 적는다.

---

## C1 — 09:00 · 지도 거점 전환 렌더가 왜 계속 느려지는가

**읽기 전용 진단이다. 코드를 고치지 않는다.** 원인을 틀리게 짚고 수정부터 하면 되돌리기 어렵다.

```text
seoghyeonbag36-max/spaceos 의 main 에서 작업한다. docs/cloud-workday-claude-2026-09-08.md 의
공통 계약을 적용하라. 브랜치는 chore/cloud-c1-map-hubswitch-diagnosis 다.

[문제]
Playwright 화면 회귀 루프가 66거점을 순회하며 map 탭에서 거점을 바꿀 때, 초기 렌더 완료까지의
시간이 거점을 바꿀수록 단조 증가한다. 예산은 3,000ms 다. 실측(ms, 관측 순서):
13234 18203 24172 29969 36234 37469 39422 40328 43218 43219 48046 48860 234687
같은 실행에서 탭을 처음 여는 tab-open 은 4750~7375ms 였다. 즉 첫 렌더도 느리지만,
진짜 문제는 거점을 바꿀수록 누적된다는 것이다. Platform 탭의 hub-switch 는 6172ms 한 건뿐이라
map 탭에 특유한 현상으로 보인다.

[너의 일]
왜 map 탭에서만, 왜 거점을 바꿀수록 시간이 누적되는지 코드에서 원인을 특정하라. 다음을 읽어라:
  apps/frontend/src/pages/MapShell.tsx
  apps/frontend/src/components/MapHost.tsx
  apps/frontend/src/lib/naverMap.ts
  apps/frontend/src/lib/api.ts
  apps/frontend/src/pages/PageDashboard.tsx
  apps/frontend/src/hooks/ (전부)
특히 거점(districtId)이 바뀔 때 무엇이 만들어지고 무엇이 정리되는지를 짝지어 확인하라.
naver.maps 오버레이·이벤트 리스너·heatmap 인스턴스·거리뷰 파노라마·비동기 응답 각각에 대해
"만드는 자리"와 "지우는 자리"를 표로 대응시켜라. 짝이 없는 것이 있으면 그것이 후보다.
useEffect 의존성 배열과 정리 함수(cleanup)의 반환 시점도 본다.

[산출물]
docs/finding-map-hubswitch-2026-09-08.md 하나를 새로 쓴다. 담을 것:
  - 관측(위 숫자와 그 출처가 어제 중단된 실행의 69조합이라는 한계)
  - 생성/정리 대응표
  - 후보 원인들과 각각을 뒷받침하는 코드 위치(파일:줄)
  - 각 후보가 "단조 증가"라는 관측을 설명하는가 / 설명하지 못하는가
  - 가장 유력한 원인 하나와 그렇게 고른 이유
  - 코드만으로는 판정할 수 없어 PC 실행이 필요한 항목

[통과 조건]
C1_EVIDENCE: 지목한 모든 원인에 파일:줄 근거가 있다. 추측은 추측이라고 적는다.
C1_EXPLAINS: 유력 원인이 "왜 첫 회는 13초인데 마지막은 234초인가"를 설명한다. 설명하지 못하면
             그렇다고 적고 미해결로 남긴다.
C1_NO_EDIT: apps/ 아래 소스가 하나도 바뀌지 않았다. 새 문서 1개만 추가됐다.

[금지]
코드 수정, 예산 상수 완화, scripts/screen_loop.py 나 reports/* 변경, 성능이 개선됐다는 서술.
원인을 못 찾으면 못 찾았다고 적어라. 그럴듯한 원인을 지어내지 마라.

문서 작성 → 커밋 → 위 브랜치 푸시 → draft PR 생성까지 승인한다. main 머지는 하지 마라.
최종 응답에 유력 원인 한 줄, 파일:줄, PR URL 을 적어라.
```

---

## C2 — 10:30 · C1 이 특정한 원인을 고친다

**선행:** C1 의 PR 이 있고 유력 원인이 하나 특정돼 있어야 한다. 원인이 미해결이면 이 작업을 보내지
말고 C3 로 넘어간다.

```text
seoghyeonbag36-max/spaceos 에서 작업한다. docs/cloud-workday-claude-2026-09-08.md 의 공통 계약을
적용하라. 브랜치 chore/cloud-c1-map-hubswitch-diagnosis 의 docs/finding-map-hubswitch-2026-09-08.md
를 먼저 읽어라. 없으면 진행하지 말고 그 사실을 보고하라.

새 브랜치 chore/cloud-c2-map-hubswitch-fix 를 main 에서 만들어 작업한다.

[너의 일]
C1 이 특정한 유력 원인 하나만 고친다. 눈에 띄는 다른 문제를 같이 고치지 마라 — 수정이 여러 개면
저녁에 화면으로 재실행했을 때 무엇이 효과가 있었는지 갈라낼 수 없다. 다른 문제를 발견하면
고치지 말고 PR 본문에 목록으로 적어라.

수정한 자리에는 왜 이렇게 고쳤는지 한국어 주석을 남긴다. 이 저장소는 주석에 "무엇을 했나"가
아니라 "왜 그래야 했나, 안 그러면 무엇이 깨지나"를 적는다. 기존 주석 스타일을 따르라.

[통과 조건]
C2_SCOPE: 바뀐 파일이 C1 이 지목한 경로로 한정된다.
C2_BUILD: apps/frontend 에서 npm ci && npm run build && npm run lint 가 통과한다.
          네트워크가 막혀 실행하지 못했다면 미실행이라고 적는다. 통과했다고 쓰지 않는다.
C2_MECHANISM: PR 본문에 "이 수정이 누적을 없애는 이유"가 코드 수준으로 적혀 있다.
C2_UNVERIFIED: PR 본문 맨 위에 "화면 미확인 — PC 에서 scripts/screen_loop.py 재실행 필요"가 있다.

[금지]
예산 상수·타임아웃 완화, 관계없는 리팩터, 의존성 추가, scripts/screen_loop.py 및 reports/* 변경,
"3초 이내로 개선됐다" 같은 미측정 주장.

커밋 → 푸시 → draft PR 생성까지 승인한다. main 머지는 하지 마라.
최종 응답에 바꾼 파일, 수정 근거 한 줄, 빌드·린트 결과, PR URL 을 적어라.
```

---

## C3 — 13:00 · 조작 실패 10건은 같은 뿌리인가

```text
seoghyeonbag36-max/spaceos 의 main 에서 작업한다. docs/cloud-workday-claude-2026-09-08.md 의
공통 계약을 적용하라. 브랜치는 chore/cloud-c3-s0-operation-failures 다.

[문제]
같은 화면 회귀 실행에서 조작 자체가 실패한 관측이 10건 있었다. 두 종류다:
  (가) map 탭 — Page.wait_for_selector 가 ".hub-select:not([disabled])" 를 20,000ms 기다리다 실패
  (나) posting 탭 — Locator.click 이 role=button name="Posting" 을 20,000ms 기다리다 실패
같은 실행에서 map 탭 hub-switch 렌더가 최대 234,687ms 까지 늘어나 있었다.

[너의 일]
이 10건이 (1) 렌더 지연의 결과인가 — 화면이 234초씩 걸리니 20초 대기가 먼저 끊긴 것인가,
아니면 (2) 별개의 결손인가를 판정하라. 다음을 읽어라:
  apps/frontend/src/pages/MapShell.tsx, PostingConsole.tsx, PageDashboard.tsx
  apps/frontend/src/components/DistrictPicker.tsx
  apps/frontend/src/App.tsx
  scripts/screen_loop.py  (읽기만 한다. 고치지 마라)
hub-select 가 disabled 로 남는 조건, 탭 버튼이 마운트되는 조건, 그 두 가지가 앞선 거점의 미완료
작업에 막힐 수 있는 경로를 확인하라.

[산출물]
docs/finding-screen-s0-2026-09-08.md 하나. 판정을 (1)/(2)/판정 불가 셋 중 하나로 적고 근거를
파일:줄로 단다. (2)라면 원인과 수정 방향까지 적되 수정은 하지 않는다.

[통과 조건]
C3_VERDICT: 두 종류 각각에 판정과 근거가 있다. 판정 불가면 무엇이 있어야 판정되는지 적는다.
C3_NO_EDIT: apps/ 와 scripts/ 아래가 바뀌지 않았다. 새 문서 1개만 추가됐다.

[금지]
코드 수정, 타임아웃 완화, screen_loop 명세 변경, 근거 없는 원인 단정.

문서 작성 → 커밋 → 푸시 → draft PR 까지 승인한다. main 머지는 하지 마라.
```

---

## C4 — 14:30 · 합정에서 heatmap 을 안 부른다 · 사이드패널 제목이 없다

```text
seoghyeonbag36-max/spaceos 의 main 에서 작업한다. docs/cloud-workday-claude-2026-09-08.md 의
공통 계약을 적용하라. 브랜치는 chore/cloud-c4-map-panel-and-heatmap 이다.

[문제] 화면 회귀에서 map 탭의 판정 실패 2건이다.
  (가) "거점을 바꿨는데 /heatmap/buildings?district=hapjeong 를 부르지 않았다"
  (나) ".mapshell .sp-head .sp-title 이(가) 0개 — 1개 이상이어야 한다"

[너의 일]
둘 각각이 (A) 제품 결손인지 (B) 화면 회귀 명세가 틀린 것인지 판정하라.
(가)는 apps/frontend/src/pages/MapShell.tsx 와 lib/api.ts 의 getBuildings 호출 조건, 그리고
apps/backend/app/data/measured_pages.py · page_hubs.py 에서 hapjeong 이 어떤 거점인지 확인하라.
MapShell.tsx 에 합성 거점이면 404 라서 건너뛴다는 취지의 주석이 있다 — 그 분기가 이 관측을
설명하는지 확인하라. 설명한다면 이건 제품 결손이 아니라 명세가 그 분기를 모르는 것이다.
(나)는 sp-head/sp-title 이 언제 렌더되는지, 데이터가 비었을 때 어떻게 되는지 확인하라.

[산출물과 처리]
- (B) 명세 오류로 판정되면 **고치지 마라.** scripts/screen_loop.py 는 PC 에 미커밋 변경이 있다.
  판정과 필요한 명세 수정안을 문서에 적는 데서 멈춘다.
- (A) 제품 결손으로 판정되고 수정이 20줄 안쪽으로 명확하면 고친다. 그보다 크면 문서만 쓴다.
- 문서는 docs/finding-map-panel-heatmap-2026-09-08.md 하나로 쓴다.

[통과 조건]
C4_VERDICT: 두 건 각각 A/B/판정 불가와 근거(파일:줄).
C4_BUILD: 소스를 고쳤다면 npm run build 와 npm run lint 통과. 못 돌렸으면 미실행이라고 적는다.
C4_NO_SPEC_EDIT: scripts/screen_loop.py 가 바뀌지 않았다.

[금지]
screen_loop.py·reports/* 변경, 백엔드 데이터 계약 변경, 거점 등록 변경, 판정 없는 수정.

커밋 → 푸시 → draft PR 까지 승인한다. main 머지는 하지 마라.
```

---

## C5 — 16:00 · 프론트 회귀를 코드로 고정한다 (선택)

⚠ C1~C4 가 밀렸으면 **보내지 않는다.** 이건 급하지 않다.

```text
seoghyeonbag36-max/spaceos 의 main 에서 작업한다. docs/cloud-workday-claude-2026-09-08.md 의
공통 계약을 적용하라. 브랜치는 chore/cloud-c5-frontend-test-runner 다.

[문제]
apps/frontend/package.json 에 테스트 러너가 없다. scripts 는 dev/build/preview/lint 뿐이고
devDependencies 에 vitest 도 testing-library 도 없다. 그래서 지금 프론트 회귀를 막는 수단이
Playwright 전수 실행(264조합, 몇 시간)뿐이다. CI(.github/workflows/ci.yml)의 프론트 잡도
타입체크·빌드·린트만 돈다.

[너의 일]
vitest + @testing-library/react + jsdom 을 devDependency 로 도입하고, 최소한의 테스트를 붙인다.
목표는 커버리지가 아니라 **거점 전환 회귀를 초 단위로 잡는 그물**이다. 다음을 우선한다:
  1. 거점을 바꿨을 때 이전 거점의 오버레이·리스너가 정리되는가 (naver.maps 는 목으로 대체)
  2. 각 탭이 마운트될 때 부르는 API 경로가 기대와 맞는가 (fetch 를 목으로)
  3. 사이드패널이 데이터 없을 때/있을 때 각각 무엇을 렌더하는가
naver 지도 SDK 와 fetch 는 전역 목을 만들어 쓴다. 실제 네트워크·실제 지도를 부르지 않는다.
package.json 에 "test": "vitest run" 을 추가하고, ci.yml 의 frontend 잡에 lint 다음 단계로
테스트를 추가한다. deploy.yml 은 건드리지 않는다.

[통과 조건]
C5_RUNS: npm ci && npm run test 가 실제로 통과한다. 네트워크가 막혀 설치를 못 했으면 그렇게 적고
         커밋은 남기되 통과했다고 쓰지 않는다.
C5_MEANINGFUL: 테스트가 컴포넌트가 존재한다는 것 말고 위 3가지 중 최소 2개의 동작을 확인한다.
C5_CI: ci.yml 의 frontend 잡에만 단계가 추가됐다. 다른 잡·deploy.yml 은 그대로다.
C5_NO_PROD_EDIT: 테스트를 통과시키려고 제품 코드를 바꾸지 않았다. 바꿔야만 한다면 멈추고 보고하라.

[금지]
런타임 dependency 추가, deploy.yml 변경, 기존 잡 수정, 통과를 위한 제품 코드 변경,
스냅샷만 찍는 테스트.

커밋 → 푸시 → draft PR 까지 승인한다. main 머지는 하지 마라.
최종 응답에 추가한 테스트 개수, 실제 실행 결과, PR URL 을 적어라.
```

---

## C6 — 17:00 · 마감 점검

```text
seoghyeonbag36-max/spaceos 를 점검하라. 코드를 고치지 마라.

오늘 만들어진 PR 들(chore/cloud-c1 ~ c5 접두사)을 모두 찾아서 각각에 대해 적어라:
  - PR URL 과 head SHA
  - 바뀐 파일 목록이 그 작업의 허용 범위를 벗어나지 않았는가
  - CI 4개 잡(백엔드 pytest / 서버리스 임포트 / 데이터 pytest / 프론트 빌드)의 현재 결과.
    미실행·대기 중이면 그렇게 적는다. 성공으로 간주하지 마라.
  - 서로 같은 파일을 건드려 머지 충돌이 날 조합이 있는가

그다음 오늘 나온 진단 문서(docs/finding-*-2026-09-08.md)를 읽고, 저녁에 PC 에서 확인해야 할
항목만 골라 순서대로 목록을 만들어라. 각 항목에 "무엇을 실행하고 무엇을 보면 판정되는가"를 적어라.

머지하지 마라. 브랜치를 지우지 마라. 최종 응답은 PR 표 하나와 PC 검증 목록 하나로 끝내라.
```

---

## 저녁에 PC 에서 할 일

클라우드는 화면을 못 봤다. 그러니 오늘의 PR 들은 **전부 미검증 상태**다.

1. C2 브랜치를 체크아웃하고 `cd apps/frontend && npm run dev` 로 띄운다.
2. `python scripts/screen_loop.py` 를 map 탭 위주로 다시 돌린다. 어제와 같은 거점 순서로 돌려야
   단조 증가가 사라졌는지 비교할 수 있다.
3. 렌더 시간이 예산 안으로 들어왔는지 확인한 **뒤에** 머지한다. main 머지는 `deploy.yml` 을 태워
   프로덕션까지 나간다.
4. 어제 중단된 264조합 전수 실행을 다시 건다 (`/autorun` 규칙 — 절전 억제·UTF-8).

⚠ 클라우드 PR 이 "성능이 개선됐다"고 적어 왔다면 그건 공통 계약 위반이다. 그 문장을 믿지 말고
   2번을 직접 돌려서 판정한다.
