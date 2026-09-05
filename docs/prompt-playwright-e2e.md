# 내일 작업용 프롬프트 — Playwright e2e 구축 (13거점 red dot 렌더 검증)

> ⛔ **만료됨 (2026-09-05 표시). 이 프롬프트를 그대로 실행하지 말 것 — 이력이다.**
>
> 세 전제가 전부 깨졌다:
> 1. **거점 13 → 66.** 아래 slug 목록은 2026-07-27 판이다. 현재 목록의 단일 기준은
>    `app.services.districts.PAGES` 이고, 상태는 `python scripts/chain_status.py --all`.
> 2. **`BuildingTwin`(3D 트윈)은 2026-09-05 에 삭제됐다.** 클릭 대상은 이제
>    `components/BuildingViewer.tsx`(2D 층 스택 + 네이버 거리뷰)다 → `feature-posting.md` §0-V.
>    `PageDashboard.tsx` 의 `VacancyMap` 도 `pages/MapShell.tsx` 로 옮겨갔다.
> 3. **화면 검증은 이미 있다.** `@playwright/test`(Node)를 새로 깔 게 아니라,
>    `/verify` 스킬이 Python `playwright`(2026-07-24 설치)로 백엔드+Vite 를 띄워
>    지도 픽셀까지 본다. 실제로 커밋 fd04852 의 결함 둘(거리뷰 미렌더·토글 무반응)을
>    그 경로로 잡았다. **새 e2e 를 짜기 전에 `/verify` 를 먼저 읽을 것.**
>
> 아래 §"참고" 의 검증 항목 네 가지(마커 수 > 0 · 콘솔 에러 0 · 클릭 → 상세 · 토글)는
> 여전히 옳다. 살릴 것이 있다면 그 목록이지 프롬프트가 아니다.

2026-07-27 밤에 13거점 Tier1 대장 수집과 `build_page_master` 재빌드를 끝냈고,
검증은 **데이터 수준(red dot 수 비교)까지만** 했다. 시각 검증은 Playwright가
저장소에 없어서 미뤘다. 아래 프롬프트를 새 세션에 그대로 붙여 넣으면 된다.

---

## 붙여 넣을 프롬프트

```
SpaceOS 프론트에 Playwright e2e를 구축하고, 13거점 red dot 렌더를 시각 검증해줘.

## 배경
2026-07-27에 13거점 건물 대장(Tier1) 수집을 완료하고 build_page_master를 재빌드했다.
capacity가 층수 근사(floor_approx)에서 실제 대장(expos_units/floor_ouln)으로 바뀌었고,
그 결과 거점별 red dot(공실의심, status=empty) 수가 달라졌다.
데이터 수준 비교는 끝났으니, 이번엔 실제 지도 화면에 제대로 그려지는지를 확인한다.

## 현재 상태
- Playwright 미설치 — @playwright/test, 브라우저 바이너리, spec, test 스크립트 전부 없음.
  apps/frontend/node_modules 자체는 설치돼 있다(133 패키지, Vite+React+TS).
- 검증 대상 데이터: data/gold/{slug}/page_building_master.geojson (13개)
- 프론트 컴포넌트: apps/frontend/src/.../PageDashboard.tsx 의 VacancyMap
  (red dot 레이어 + 공실건물/그리드 토글 + 점 클릭 → 3D 트윈 BuildingTwin)

## 해야 할 일
1. apps/frontend 에 @playwright/test 설치 + chromium 브라우저 설치.
   package.json 에 test:e2e 스크립트 추가.
2. playwright.config.ts 작성 — webServer 로 vite dev를 자동 기동시키고,
   백엔드(apps/backend, uvicorn app.main:app)도 함께 필요한지 확인해 반영할 것.
   백엔드 없이 geojson을 직접 읽는 구조라면 프론트만 띄우면 된다.
3. 13거점을 순회하는 spec 작성. 거점 slug:
   garosugil, apgujeong-rodeo, hongdae, yeonnam, ikseon, seochon, myeongdong,
   euljiro, seongsu, seoulsup, itaewon, hannam, songridan
4. 거점마다 검증할 것:
   - 지도가 렌더되고 red dot 레이어가 실제로 그려진다(마커 수 > 0)
   - 브라우저 콘솔 에러 0건
   - red dot 하나를 클릭하면 3D 트윈(BuildingTwin)이 열리고 주소·호수가 표시된다
   - 공실건물/그리드 토글이 동작한다
5. 거점별 스크린샷을 남겨 눈으로도 확인할 수 있게 할 것.

## 완료 기준
- npm run test:e2e 로 13/13 통과, 콘솔 에러 0
- 스크린샷 13장 확보
- CI에서도 돌릴 수 있게 설정(브라우저 설치 단계 포함)

## 주의 (이 환경 특유)
- Windows + PowerShell 5.1 환경이다. .ps1 스크립트를 새로 만들면 반드시 UTF-8 BOM으로
  저장할 것 — BOM이 없으면 PS 5.1이 CP949로 읽어 한글 뒤 따옴표를 삼키고 파싱이 깨진다.
- 긴 작업은 반드시 백그라운드로 돌릴 것. 그리고 노트북이 배터리 상태로 덮개가 닫히면
  Modern Standby로 프로세스가 얼어붙는다 — AC 연결 확인.
```

---

## 참고 — 왜 이 항목들을 검증 대상으로 잡았나

- **red dot 마커 수 > 0**: Tier1 승격으로 status 분포가 바뀌었다. 데이터에 empty가 있는데
  화면에 안 그려지는 회귀를 잡는 게 이번 검증의 핵심이다.
- **콘솔 에러 0**: 2026-07-25 검증 때의 기준을 그대로 유지한다.
- **클릭 → 3D 트윈**: red dot 레이어와 BuildingTwin 연결이 이번 데이터 교체로
  깨지지 않았는지 확인한다.
- **토글**: 공실건물/그리드 전환은 red dot 레이어의 표시 조건과 직접 얽혀 있다.

## 관련 파일

- 데이터: `data/gold/{slug}/page_building_master.geojson`
- 파이프라인: `data/pipelines/build_page_master.py`
- 수집기: `data/collectors/building_vacancy.py`
- 수집 래퍼: `scripts/run_bldgvac_until_done.ps1`
- 기존 수동 확인 절차: `.claude/skills/verify` (spaceos:verify 스킬)
