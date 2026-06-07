---
description: "PPPP 통합 → Design (디자인시스템·토큰·대시보드 통합)"
argument-hint: "<이번 작업 목표 한 문장>"
---

# 트랙 컨텍스트: Design (PPPP 산출물 통합 레이어)

너는 지금 SpaceOS의 **Design 트랙** 담당이다. `CLAUDE.md` 규칙을 따른다.

## 먼저 읽기
- @docs/feature-design-system.md
- @docs/01-app-design-handoff.md

## 트랙 정의
- 의미: Platform·Page·Posting·Program 산출물을 **하나의 사용 가능한 앱**으로 묶는 UX/UI 전 과정.
- 디자인 토큰 단일출처: `design/tokens/tokens.json` ⇄ `apps/frontend/src/design/tokens/*.ts` (동기화 필수).
- 차별화 지표: **Humanistic Authority**(균형·공생·공감) + 접근성(색대비 AA)·반응형.

## 화이트리스트 경로
- 토큰: `design/tokens/tokens.json`, `apps/frontend/src/design/tokens/`
- 컴포넌트: `apps/frontend/src/design/components/`, `src/components/`
- 통합 화면: `apps/frontend/src/pages/` (CityDashboard, DistrictPPPP)
- 소비: `apps/frontend/src/lib/api.ts` 전체 (`listDistricts` / `getDistrict` 등)

## 통합 규칙
- 대시보드 1화면에서 4트랙을 본다: 감성(Platform)·히트맵(Page)·입점(Posting)·마케팅(Program).
- 색상은 **토큰만** 사용(하드코딩 금지). 네이버 green은 네이버 연동 맥락만, brand teal은 SpaceOS 고유 기능.

## 이번 목표
$ARGUMENTS

## 작업 방식
1. 작은 작업으로 분해 → 승인 → 진행.
2. 토큰 변경 시 json↔ts 동기화. 더미엔 `// TODO: 실제 연동`.
3. 마치면 `/verify` (`npm run build`, 스크린샷).
