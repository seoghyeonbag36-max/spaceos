# Page — 공실 히트맵 + 3D 디지털 트윈

> PPPP: **Product/Price → Page**. 어떤 업장이 어디에 있는지를 신뢰도 높은 시각 인터페이스로 표현. 공실 히트맵과 3D 건물 디지털 트윈이 핵심.

## 1. 담당 코드 영역

```
apps/frontend/src/components/        3D 맵, 히트맵 레이어, 히스토리 타임라인
apps/frontend/src/pages/             상권/건물 상세 페이지
apps/frontend/src/lib/api.ts         백엔드 호출 (getBuildingHistory 등)
apps/backend/app/api/v1/buildings.py 건물 히스토리/3D 모델 경로
apps/backend/app/api/v1/districts.py 상권 정보 + /heatmap GeoJSON
```

## 2. Claude Code 설치/환경

```bash
cd apps/frontend
npm install                 # react, three, @react-three/fiber, mapbox-gl, d3, plotly
npm run dev                 # http://localhost:5173

# Mapbox 토큰 (.env)
echo "VITE_MAPBOX_TOKEN=pk.xxxx" > .env
```

> 백엔드를 함께 띄워야 `/api` 프록시가 동작한다: `cd apps/backend && uvicorn app.main:app --reload`

## 3. 작성해야 할 코드 (순서)

1. **히트맵 API** (`apps/backend/app/api/v1/districts.py`) — `/heatmap` 스텁을 Gold 레이어 공실 데이터 기반 GeoJSON FeatureCollection으로 교체. 각 Feature에 공실률·예측값(Platform 연동) 속성 부여.
2. **Mapbox 베이스맵 컴포넌트** (`src/components/DistrictMap.tsx`) — Mapbox GL 지도 초기화, 거점 상권 좌표로 카메라 이동.
3. **히트맵 레이어** (`src/components/VacancyHeatmap.tsx`) — `/api/v1/heatmap/{id}` GeoJSON을 fill-extrusion 또는 heatmap 레이어로 렌더. 공실률에 따라 색상 매핑.
4. **3D 건물 트윈** (`src/components/BuildingTwin.tsx`) — @react-three/fiber + GLTFLoader로 `/buildings/{id}/model` glTF 로드. Mapbox custom layer로 좌표계 정합. **로딩 <3초 목표** (모델 LOD·캐싱).
5. **공실 히스토리 타임라인** (`src/components/HistoryTimeline.tsx`) — `getBuildingHistory`로 업종 변천사를 타임라인 UI로 표시. 폐업 사유 AI 요약(Program/LLM) 노출.
6. **상세 차트** — D3/Plotly로 공실 추이·예측 그래프.

## 4. Claude Code 작업 예시

```
/clear
/backend-dev 상권 공실 히트맵 GeoJSON 엔드포인트.
  districts.py 의 /heatmap 스텁을 Gold 레이어 기반 FeatureCollection 으로 교체,
  각 Feature properties 에 vacancy_rate 와 predicted_rate 포함.

/frontend-dev Mapbox 기반 DistrictMap + VacancyHeatmap 컴포넌트.
  /api/v1/heatmap 데이터를 받아 공실률 색상 히트맵으로 렌더,
  src/lib/api.ts 에 getHeatmap 추가.
```

## 5. 검증

- `cd apps/frontend && npm run build` — 타입체크 통과
- 브라우저에서 히트맵 색상·3D 모델 렌더 확인, **로딩 3초 이내**
- `cd apps/backend && pytest` — heatmap/buildings 응답 스키마(GeoJSON 유효성)
- 네트워크 탭에서 API p95 <200ms 확인
