# SpaceOS Frontend (React + TypeScript + Vite)

공실 지도 UI. **네이버 지도**(지도 + 거리뷰 파노라마) + D3/Plotly.

⚠ **Three.js / @react-three/fiber 는 2026-09-05 에 제거됐다.** 3D 트윈이 그리던
절차적 박스는 실측 형상이 아니라 층 상태를 색으로 말하던 것뿐이라, 건물 상세를
**2D 층 스택 + 네이버 거리뷰**(`components/BuildingViewer.tsx`)로 갈았다
(번들 832KB → 4KB). 다시 끌어오지 말 것 — 경위는 `docs/feature-posting.md` §0-V.

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

- `src/components/` — 재사용 컴포넌트 (`BuildingViewer` = 2D 층 스택 + 거리뷰, 차트)
- `src/pages/` — 페이지
- `src/lib/api.ts` — 백엔드 API 클라이언트
- `src/hooks/` — 커스텀 훅
