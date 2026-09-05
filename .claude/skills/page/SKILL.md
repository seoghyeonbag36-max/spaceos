---
name: page
description: PPPP 트랙 — Page(공실 히트맵 + 층별 매물 목록 + 네이버 거리뷰). 히트맵·건물 레이어·지도 화면 작업의 컨텍스트와 화이트리스트 경로.
---

# 트랙 컨텍스트: Page (Product ▶ Page)

너는 지금 SpaceOS의 **Page 트랙** 담당이다. `CLAUDE.md` 규칙을 따른다.

## 먼저 읽기
- docs/feature-page.md
- docs/feature-naver-integration.md

## 트랙 정의
- 묻는 질문: **이 platform 안에 어떤 page 가 만들어져야 하는가?** 제품·상품이 아니라 page 다.
- 의미: "어떤 업장이 어디에, 어디가 비었나" — **공실 히트맵 + 층별 매물 목록 + 네이버 거리뷰**로
  page 가 놓일 자리를 인터페이스화.
- ⚠ **가격대 판단은 이 트랙이 아니다.** 2026-09-05 재정의로 `Price` 는 Posting 으로 넘어갔다
  (종전 라벨은 `Product/Price → Page`). 정본 `CLAUDE.md` §PPPP Framework.
- 핵심 기술: **네이버 지도**(`naverMap.ts`, ncpKeyId — 지도 + 거리뷰 파노라마),
  **2D 층 스택**(`BuildingViewer.tsx`), 100m 그리드.
  ⚠ 3D 트윈(@react-three/fiber)은 **2026-09-05 에 제거됐다** — 다시 끌어오지 말 것(feature-posting.md §0-V).
- 색상 규칙: 공실 위험도 저→고 = 디자인 토큰 `vacancy` 배열 (#22B07D … #E03E36).

## 화이트리스트 경로
- FE: `apps/frontend/src/lib/naverMap.ts`, `src/components/`, `src/pages/`
- BE: `apps/backend/app/api/v1/heatmap.py`, `app/services/districts.py`
- 토큰: `apps/frontend/src/design/tokens/` (단일출처 `design/tokens/tokens.json`)

## 실제 엔드포인트 / 함수 (현 코드 기준)
- GET `/api/v1/heatmap/vacancy?district=garosugil`  ← FE `getVacancyHeatmap(id)` (서울 13 Page 시드: app/data/seoul_pages.py)
- GET `/api/v1/buildings/{id}/history`             ← FE `getBuildingHistory(id)`
- 지도 키: `.env` 의 `VITE_NAVER_MAPS_KEY_ID` — NCP 콘솔 Web 서비스 URL에 `http://localhost:5173` 등록 필수.

## 이번 목표

호출 인수로 받은 목표 한 문장. 비어 있으면 진행하기 전에 묻는다.

## 작업 방식
1. 작은 작업으로 분해 → 승인 → 진행.
2. 색상·중심좌표 등은 상수로 분리, 더미엔 `// TODO: 실제 연동`.
3. 마치면 `/verify` (`npm run build` 타입체크 + 스크린샷 확인).
