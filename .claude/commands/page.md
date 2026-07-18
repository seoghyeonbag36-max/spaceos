---
description: "PPPP 트랙 전환 → Page (공실 히트맵 + 3D/네이버 지도)"
argument-hint: "<이번 작업 목표 한 문장>"
---

# 트랙 컨텍스트: Page (Product/Price → Page)

너는 지금 SpaceOS의 **Page 트랙** 담당이다. `CLAUDE.md` 규칙을 따른다.

## 먼저 읽기
- @docs/feature-page.md
- @docs/feature-naver-integration.md

## 트랙 정의
- 의미: "어떤 업장이 어디에" — **공실 히트맵 + 3D 디지털 트윈**으로 가치를 인터페이스화.
- 핵심 기술: **네이버 지도**(`naverMap.ts`, ncpKeyId), **@react-three/fiber** 3D, 100m 그리드.
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
$ARGUMENTS

## 작업 방식
1. 작은 작업으로 분해 → 승인 → 진행.
2. 색상·중심좌표 등은 상수로 분리, 더미엔 `// TODO: 실제 연동`.
3. 마치면 `/verify` (`npm run build` 타입체크 + 스크린샷 확인).
