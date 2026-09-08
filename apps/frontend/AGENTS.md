# AGENTS.md — apps/frontend (React + TypeScript + Vite)

루트 [AGENTS.md](../../AGENTS.md) 를 먼저 읽는다. 이 문서는 이 디렉터리에만 더 얹는 규칙이다.

## 구조

```
src/pages/       화면 (MapShell · PageDashboard · PlatformConsole · PostingConsole · ProgramStudio · HubExplorer · AdminCoverage)
src/components/  공용 컴포넌트 (MapHost · BuildingViewer · DistrictPicker)
src/lib/         api.ts(백엔드 호출) · naverMap.ts(지도·거리뷰) · hubBoundary.ts
src/design/      디자인 토큰 + 토큰 기반 컴포넌트
```

## 규칙

- 함수형 컴포넌트 + 훅. `@/` 경로 별칭을 쓴다
- **API 호출은 `src/lib/api.ts` 로 일원화한다.** 컴포넌트에서 `fetch` 를 직접 부르지 않는다
- 색·간격은 `src/design/tokens` 를 쓴다. 화면마다 값을 새로 적지 않는다
- 성능 목표: 지도·건물 상세 로딩 <3초

## 지도는 네이버뿐 — 되돌리지 말 것

- 지도·거리뷰 파노라마는 `src/lib/naverMap.ts` 한 곳이다
- **`three` · `@react-three/fiber` 재도입 금지** (2026-09-05 제거). 3D 트윈이 그리던 절차적 박스는
  실측 형상이 아니라 층 상태를 색으로 말하던 것뿐이라, 2D 층 스택 + 거리뷰로 대체했다
  (번들 832KB → 4KB). → `docs/feature-posting.md` §0-V
- **`mapbox-gl` 재도입 금지** (2026-08-25 커밋 1979bb4 에서 package.json·lock 모두 정리)

## 출처 배지를 지우지 않는다

백엔드가 `vacancy_source` · `inputs_source` 로 값의 출처를 밝히고, 화면은 그걸로 배지를 그린다.
합성값이 실측처럼 보이게 만드는 변경은 이 저장소에서 가장 나쁜 회귀다(루트 §0).

## 통과 조건

```powershell
cd apps/frontend; npm run build    # tsc -b 포함 = 타입체크까지 여기서 난다
cd apps/frontend; npm run lint
cd apps/frontend; npm run test     # vitest — 지도 SDK·fetch 는 전역 목이라 네트워크를 안 탄다
```

`npm run test` 가 보는 것은 **동작** 셋이다(타입·린트가 못 보는 자리):
거점 전환 시 이전 거점의 오버레이·리스너 정리 · 탭이 부르는 API 경로 ·
패널이 데이터 없을 때/있을 때 무엇을 그리는가. 목·픽스처는 `src/test/` 에 있고,
테스트는 대상 옆에 `*.test.tsx` 로 둔다. 실제 지도·실제 백엔드 검증은 `/verify` 몫이다.

`npm run dev` 는 Vite 프록시로 백엔드를 부른다 — 화면이 비면 백엔드가 떠 있는지부터 본다.
