# SpaceOS 바이브 코딩 빌드 순서 (Page 중심 → 전체 PPPP)

> 목적: "SpaceOS를 만들기 위해 바이브 코딩으로 수행할 단계"를 의존성 순서로 정리. 지금까지 한 작업(거점 확정·데이터 조사·건물공실 PoC 설계·D1 스키마)이 어디에 위치하는지, 앞서 미뤄둔 (A)·(B)가 언제 들어오는지 명시한다.

## 원칙
- **1단계 = 1 바이브 사이클**: PRD(자연어) → AI 코드 생성(Cursor/Claude Code + 슬래시 명령) → `/verify` 검증.
- **데이터 흐름**: Bronze(수집) → Silver(정제·매칭) → Gold(분석·GeoJSON). `/api/v1/...` 규약.
- **데이터가 UI를 결정(회의 3번)**: 먼저 데이터를 확보하고, 지도 위 표현 방식을 그 데이터로 결정.
- **회의 1번(네이버 지도 확대)**은 데이터와 독립 → 언제든 병렬 착수 가능.

---

## Phase 0 — 결정·기반 (대부분 완료)
| # | 단계 | 상태 | 산출물 |
|---|---|---|---|
| 0-1 | PoC 거점 확정 = 강남구 신사동 **가로수길** | ✅ | [poc-building-vacancy.md §0.5](poc-building-vacancy.md) |
| 0-2 | 4대 데이터 소스 조사 + 건물공실 PoC 설계 + D1 스키마 확정 | ✅ | poc-building-vacancy.md, [probe_garosu_d1.py](../data/probe_garosu_d1.py) |
| 0-3 | **(A) 인증키 5종 발급 + 응답 필드 스펙 확정** | ⬅ **다음 필수** | `.env` 채움 + 필드 매핑표 |

**(A) 발급 대상 5종:**
1. 공공데이터포털 `DATA_GO_KR_SERVICE_KEY` — ① 소상공인 상가정보(15012005) ② 건축물대장(15134735 건축HUB — 구 15044713 서비스 종료) *두 API 한 키로 공용*
2. 서울 열린데이터광장 `SEOUL_OPENAPI_KEY` — 실시간 도시데이터/생활인구(유동인구)
3. 통계청 SGIS 키 — 인구밀도(총조사 격자)
4. 한국부동산원 R-ONE / data.go.kr 키 — 공실률·임대시세 (①의 data.go.kr 키로 공용 가능)
5. 네이버 개발자센터 `NAVER_CLIENT_ID/SECRET` — 지도 + 검색/데이터랩
> → GIS건물통합정보(15083092)는 API가 아니라 **강남구 폴리곤 파일 다운로드**.

---

## Phase 1 — 데이터 수집 (Bronze) · 쉬운→어려운 순, 상호 독립이라 병렬 가능
| # | 데이터 | 소스 | 명령 | 난이도 |
|---|---|---|---|---|
| 1-1 | **임대시세 + 거시 공실률** | 한국부동산원 API | `/backend-dev` 콜렉터 | 하 |
| 1-2 | **인구밀도** | 통계청 SGIS API | 콜렉터 | 하 |
| 1-3 | **유동인구** | 서울 실시간 도시데이터 API | `living_population.py` 확장 | 중 |
| 1-4 | **건물 단위 공실** | 상가정보×건축물대장×GIS폴리곤 | `probe_garosu_d1` 관통 → `building_vacancy.py` | **상(핵심)** |

---

## Phase 2 — 가공 (Silver/Gold + PostGIS)
| # | 단계 | 산출물 |
|---|---|---|
| 2-1 | PostGIS 스키마 생성 (`dim_building`, `fact_store`, `building_vacancy`) | DB 마이그레이션 |
| 2-2 | 점포↔건물 매칭 (`bdMgtSn` 그룹핑 + 좌표 PIP) → occupancy 산출 | `map_store_building` |
| 2-3 | 4대 데이터 → Gold GeoJSON (구 단위 히트맵 + 건물 포인트) | `*.geojson` |

---

## Phase 3 — 백엔드 API (더미 → 실데이터)
| # | 단계 | 대상 파일 | 명령 |
|---|---|---|---|
| 3-1 | `/api/v1/heatmap` GeoJSON (Gold 기반) | `districts.py` 스텁 교체 | `/backend-dev` |
| 3-2 | `/api/v1/buildings/{id}` 공실·히스토리 실데이터 | `buildings.py` 더미 교체 | `/backend-dev` |
| 3-3 | 4대 데이터 레이어 토글 응답(유동/공실/임대/밀도) | `heatmap.py` | `/backend-dev` |

---

## Phase 4 — 프론트 Page (회의 1·3번)
| # | 단계 | 명령 | 비고 |
|---|---|---|---|
| 4-1 | **(B) 네이버 지도 영역 확대·레이아웃** | `/page`, `/frontend-dev` | **회의 1번. 데이터 불필요 → 지금 병렬 착수 가능** |
| 4-2 | 4대 데이터 히트맵 레이어 + 토글 | `/page` | **회의 3번**: 데이터 보고 표현 확정 |
| 4-3 | 건물 클릭 → 공실 상세 / 3D 디지털 트윈 | `/page` | `BuildingTwin` |
| 4-4 | 시간 슬라이더 = 유동인구 흐름 애니메이션 | `/page` | 회의 ※중요포인트 "흐름 시각화" |

---

## Phase 5 — ML (Platform 지능화)
| # | 단계 | 대상 | 명령 |
|---|---|---|---|
| 5-1 | LSTM 공실 예측 → 예측 레이어 | `ml/models/lstm/vacancy_lstm.py` | `/ml-train` |
| 5-2 | GNN 업종 추천 → 상권 AI 추천 | `ml/models/gnn/industry_gnn.py` | `/platform` |

## Phase 6 — 나머지 PPPP
| # | 단계 | 명령 |
|---|---|---|
| 6-1 | Posting — 입점 솔루션(비용-효용 분석) | `/posting` |
| 6-2 | Program — 마케팅 자동화(LLM 콘텐츠) | `/program` |

---

## 크리티컬 패스 (데이터가 지도에 뜨는 최단 경로)
```
(A)키발급 → 1-1·1-4 수집 → 2-2·2-3 가공 → 3-1 API → 4-2 지도 레이어
```
그 외 병렬: **4-1(지도 확대)은 지금 즉시**, Phase 1 각 데이터는 서로 독립 수집.

## (A)·(B) 위치 요약
- **(A)** = 0-3. Phase 1 전체의 전제 조건 → **가장 먼저**.
- **(B)** = 4-1. 데이터와 독립 → **(A)와 병렬로 지금 시작 가능**.
