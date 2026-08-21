# Page — 공실 히트맵 + 3D 디지털 트윈

> PPPP: **Product/Price → Page**. 어떤 업장이 어디에 있는지를 신뢰도 높은 시각 인터페이스로 표현. 공실 히트맵과 3D 건물 디지털 트윈이 핵심.

## 0. 구현 현황

**층별개요 수집 종결 — 잔여 650동은 "회수할 것"이 아니다 (2026-08-19 · 08-20).**
`--only-approx` 로 50거점 672동에 재호출해 **22동, 4거점만** 회수했다
(nambu 8 · jangan 6 · gongdeok 4 · jamsilsaenae 4). 나머지 46거점은 회수율 **0.0%**.

**0% 는 실패가 아니다.** 응답없음 0 · 429 0 으로 층별개요를 전부 정상 수신했고, 그 응답에
**상업 층이 0** 이라 근거 없는 capacity 를 지어내지 않고 `floor_approx` 를 유지한 것이다
(07-26 교정 조항). 몇 번을 호출해도 안 바뀐다.

회수된 4거점을 `recalc_capacity` + `build_page_master` 로 재산출했다:

| 거점 | 대표 집계 공실률 | 커버리지 |
|---|---|---|
| nambu | 61.6% (268동) | 98.5% |
| jamsilsaenae | 41.1% (286동) | 96.6% |
| jangan | 43.6% (175동) | 96.7% |
| gongdeok | 50.4% (226동) | 100.0% — `floor_approx` 가 서빙 집합에서 완전히 소멸 |

🐞 **쿼터 672콜을 태워 22동을 얻었다 — 프리플라이트가 유도한 낭비다 (08-20 교정).**
"잔여 동수"는 회수 가능성과 무관한데 프리플라이트가 그것을 명령줄과 함께 찍었다.
그날 데이터를 시도 이력으로 가르면 결론이 하나로 떨어진다:

| 그날 시도한 672동 | 회수 | 판정(상업층 0) | 회수율 |
|---|---|---|---|
| 미시도였음 | 22 | 1 | **95.7%** |
| 이미 시도했었음 | 0 | 649 | **0.0%** |

미시도 95.7% 는 `quota.md` 08-17 표(94.3~96.2%)와 같은 값이고 기시도는 예외가 없다 —
**필터가 있었으면 23콜로 끝날 일이었다(29배).**

고침은 추정을 버리고 **직접 보는 것**이다. mtime 으로는 못 잰다 — `floor_capacity` 가 bronze
를 쓴 직후 같은 실행에서 gold 를 제자리 갱신하고 **회수가 0 인 거점도** `_persist` 를 타서,
08-19 실행이 46거점의 mtime 까지 올려놨다. 그래서 `bronze/<slug>/*/bldg_flr_raw.json` 을
날짜별로 합쳐 그 건물 `lnoCd` 가 들어 있는지로 시도 여부를 판정한다(`_tried`).
bronze raw 262MB 를 파싱해 11초 걸리지만 수천 콜을 가르는 판단이라 값을 한다.

현재 상태(`python scripts/quota_preflight.py`): **잔여 650동 / 50거점 — 미시도 0 · 판정완료
650.** 명령줄이 아예 안 찍힌다. **새 거점을 넣거나 대장을 새로 받기 전까지 층별개요로
회수할 것은 없다.**

**3D 트윈 층 실배치 — 연결 완료 (2026-08-17).**
트윈이 "몇 층이 비었나"를 **실측 층 번호**로 그린다. 종전에는 점유율만큼 **아래부터 채우는
근사**여서, 3층이 비고 1층이 찬 건물도 1층부터 찬 것으로 그려졌다.

원인은 데이터 부재가 아니라 **파이프라인이 층 번호를 버린 것**이었다. `build_page_master._aggregate`
는 상업층 집합(`capacity_floors`)과 점포 확인 층(`store_flr_nos ∪ 인허가 층`)을 이미 계산해
놓고 **개수만**(`active_floors_lo/hi`) 남겼다. 층 번호를 산출물에 실어 프론트로 흘린다.

| 새 property | 뜻 |
|---|---|
| `com_floors` | 상업 용도 층 번호 — 공실률의 **분모** |
| `occ_floors` | 점포(상가정보 flrNo)·인허가로 **확인된** 영업 층 — 분자의 하한 |
| `unknown_n` | 층 미상 점포로 빈 상업층에 배정된 층 수(상한 − 하한) |

트윈은 층을 4색으로 구분한다: 영업 확인(녹) · 층 미상 배정(황) · 공실(상태색) ·
**비상업 층(회, 좁게)**. 마지막이 특히 중요하다 — 종전 트윈은 주거·업무 층까지 상가인 양
그렸다. `com=[1,4,5]` 인 건물이면 2·3층은 분모 밖이라는 게 화면에 드러난다.

- 층 미상 점포를 앉히는 규칙은 파이프라인과 **동일**하게 맞췄다(빈 상업층에 낮은 층부터).
  어긋나면 트윈의 녹색 층 수와 카드의 `vacancy_rate` 가 서로 안 맞는다.
- 층 근거가 없는 건물은 **종전 근사로 폴백**하되, 캡션에 "아래부터 채운 근사"라고 밝힌다.
- 배선: `_aggregate` → gold 마스터 properties → `services/building_vacancy` 는 gold 를 그대로
  통과시키므로 **백엔드 변경 없음** → `MapShell` · `PageDashboard` → `BuildingTwin`.
- 재산출 영향: 54거점 coverage.json 이 전부 `built_at` 한 줄만 바뀌었다 — **수치 드리프트 0**.
  마스터 합계 29.7 → 30.7MB (+3.4%).

**커버리지 확대 — 41거점 recalc 반영 (2026-08-17).**
`capacity_floors` 를 남기는 `recalc_floor_ouln` 이 13거점에서만 돌아 있어 층 실배치가
**18.7%(8,515동)** 에 그쳤다. 나머지 41거점에 돌려 **58.1%(26,461/45,580동)** 로 넓혔다.
50% 이상 거점 12 → **43곳**, 0% 거점 **0곳**. 정합성 검사 26,461동 **위반 0**.

수치 영향(대표 집계 공실률, 40거점 변동): 중앙 **+2.6%p** · 평균 +2.4%p · 범위 −7.8%p
(chungmuro 26.4→18.6) ~ +15.9%p (garak 22.4→38.3). **0%/100% 로 붕괴한 거점 없음,
커버리지 하락 거점 없음.** 앵커는 `calibrate_vacancy` 로 54거점 재산출했다.

🐞 **`load_latest` 가 부분 수집본을 집는 결함 — 이때 드러났다.**
층별개요는 건축HUB 일일 쿼터 때문에 **날짜를 나눠 조금씩** 모은다. 그런데
`recalc_floor_ouln` 이 `common.load_latest`(가장 최근 날짜 폴더)로 원본을 읽어,
그날 받은 일부만 담긴 스냅샷이 앞서 모은 완전본을 **가렸다**.

| 거점 | 최신 스냅샷 | 실제 최대 | 1차 실행 결과 |
|---|---|---|---|
| dangsan | 08-17 **18**지번 | 08-08 160지번 | 공실 19.5% → **0.0%** |
| mullae | 08-17 **60** | 08-15 548 | 15.5% → **0.0%** |
| yongsan | 08-17 **51** | 08-08 279 | 15.8% → **1.0%** |
| chungmuro · anam · samcheong | 〃 | 〃 | −10.5 ~ −7.8%p |

분모(상업층)가 비면 층 매칭이 안 붙어 레거시로 폴백하고, `active > capacity` 가 되며
occupancy 가 1.0 으로 포화된다 → **공실률 0% 아티팩트**. 이 문서 상단이 경고하는
"측정값이 아니라 아티팩트"와 같은 실패 양상이 입력 선택 단계에서 재발한 것이다.

고침: `recalc_floor_ouln._load_flr()` 이 **전 스냅샷을 병합**한다(같은 지번은 층 레코드가
많은 쪽을 남긴다 — `build_building_attrs` 와 동일 규칙). `build_building_attrs` 는 이미
`glob("*/bldg_flr_raw.json")` 로 전 스냅샷을 순회하고 있었다. 재실행은 **멱등**임을
dangsan 으로 확인했다(두 번 돌려 13.2% 동일).

⚠ 같은 결함이 `load_latest` 를 쓰는 **다른 소비 지점에도 잠재**한다(`stores_raw.json` ·
`bldg_polygons.geojson` 등). 부분 수집이 일어나는 소스인지 확인 후 같은 병합을 적용할 것.

**부수 효과 — 앵커 49 → 54/54.** `calibrate_vacancy` 재산출로 종전 5곳(kyunghee 등)에
없던 `calibration.json` 이 생겼다. 이로써 `test_gold_anchor_comparison_attached` 의
"calibration.json 없음" 실패(기존 결함)가 해소됐다.

🔴 **미해결 — nokdu 앵커 격차 34.55%p 로 가드레일(30) 초과.** 같은 테스트가 이제
nokdu 에서 실패한다(`1 failed, 101 passed, 5 skipped`).

- **분포 이동이 아니라 단독 이상치다.** 2위 sharosugil 23.00p 와 11.5%p 벌어져 있고,
  25~30p 구간 거점은 **0곳**이다. 임계값 문제로 보고 테스트를 늦추면 안 된다.
- **변경 전에도 최대 격차였다** — 종전 대표 공실률 34.2% 기준 격차 ≈28.6p 로 임계
  바로 아래였고, 이번 재산출(34.2 → 40.3%)이 넘긴 것이다. 새로 생긴 이상이 아니라
  **가려져 있던 이상이 드러난 것**으로 읽어야 한다.
- 단서: nokdu 는 **층 미상 점포 비율 55%** 로 인접 거점 중 최고다(sillim 49% ·
  sharosugil 45%). 층별개요 스냅샷 자체는 정상이다(2026-08-15 390지번, 부분수집 아님).
  앵커 5.63% 는 sillim 과 **같은 R-ONE 매핑**인데 sillim 추정은 25.3% 라, 같은 앵커에
  두 배 가까운 추정이 붙는다 — nokdu 쪽 분모·분자 귀속을 따로 봐야 한다.
- 조치 전까지 nokdu 수치는 **신뢰하지 말 것**. 테스트는 실패인 채로 둔다(가리지 않는다).

**미착수(계획 §3 대비)**: 히스토리 타임라인(백엔드 `/history` 는 있으나 프론트 미연결) ·
상세 차트(d3·plotly 설치돼 있으나 import 0건) · 유동/밀도 히트맵 레이어(샘플 상수).
glTF 실측 모델은 자산 0개이며 `/buildings/{id}/model` 은 스텁이다.

⚠ 아래 §2 의 **Mapbox 안내는 낡았다** — 실제 베이스맵은 네이버 지도(`lib/naverMap.ts`)다.

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
