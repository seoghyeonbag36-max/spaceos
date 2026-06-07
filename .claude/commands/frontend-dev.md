---
description: Frontend(React+TS) 컴포넌트/페이지 개발
---

SpaceOS 프론트엔드에 UI를 추가한다. 대상: $ARGUMENTS

규칙:
1. 함수형 컴포넌트 + 훅. 컴포넌트는 `src/components/`, 페이지는 `src/pages/`.
2. 모든 API 호출은 `src/lib/api.ts`에 함수로 추가 후 사용.
3. 3D 맵은 @react-three/fiber + Mapbox GL, 차트는 D3/Plotly.
4. 경로 별칭 `@/` 사용. 작업 후 `npm run build`로 타입체크.
