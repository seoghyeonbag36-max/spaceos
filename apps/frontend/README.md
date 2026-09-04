# SpaceOS Frontend (React + TypeScript + Vite)

3D 디지털 트윈 맵 UI. Three.js / @react-three/fiber + **네이버 지도** + D3/Plotly.

## 실행

```bash
cd apps/frontend
npm install
npm run dev
```

- 개발 서버: http://localhost:5173 (`/api` → backend 8000 프록시)
- 네이버 지도 키는 `.env` 의 `VITE_NAVER_MAPS_KEY_ID` 로 주입한다 (`src/lib/naverMap.ts`).
  NCP 콘솔의 Web 서비스 URL 에 `http://localhost:5173` 을 등록해야 지도가 뜬다.
  ⚠ Mapbox 는 쓰지 않는다 — `mapbox-gl` 은 2026-08-25 에 의존성에서 제거됐다
  (경위: `docs/decision-infra-layer-2026-08-25.md`).

## 구조

- `src/components/` — 재사용 컴포넌트 (3D 맵, 히트맵, 차트)
- `src/pages/` — 페이지
- `src/lib/api.ts` — 백엔드 API 클라이언트
- `src/hooks/` — 커스텀 훅
