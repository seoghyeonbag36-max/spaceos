---
name: frontend-dev
description: React+TS 컴포넌트·페이지 추가 규칙 — api.ts 일원화, @/ 별칭, 빌드 타입체크. apps/frontend 에 UI 를 붙일 때.
---

SpaceOS 프론트엔드에 UI를 추가한다. 대상: 호출 인수(추가할 UI). 비어 있으면 무엇을 붙일지 먼저 묻는다.

규칙:
1. 함수형 컴포넌트 + 훅. 컴포넌트는 `src/components/`, 페이지는 `src/pages/`.
2. 모든 API 호출은 `src/lib/api.ts`에 함수로 추가 후 사용.
3. 베이스맵은 **네이버 지도**(`src/lib/naverMap.ts`), 3D 는 @react-three/fiber, 차트는 D3/Plotly.
   Mapbox 를 새로 끌어오지 말 것 — 2026-08-25 에 의존성에서 뺐다.
4. 경로 별칭 `@/` 사용. 작업 후 `npm run build`로 타입체크.
