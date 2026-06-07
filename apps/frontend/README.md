# SpaceOS Frontend (React + TypeScript + Vite)

3D 디지털 트윈 맵 UI. Three.js / @react-three/fiber + Mapbox GL + D3/Plotly.

## 실행

```bash
cd apps/frontend
npm install
npm run dev
```

- 개발 서버: http://localhost:5173 (`/api` → backend 8000 프록시)
- Mapbox 토큰은 `.env`의 `VITE_MAPBOX_TOKEN`으로 주입 (TODO)

## 구조

- `src/components/` — 재사용 컴포넌트 (3D 맵, 히트맵, 차트)
- `src/pages/` — 페이지
- `src/lib/api.ts` — 백엔드 API 클라이언트
- `src/hooks/` — 커스텀 훅
