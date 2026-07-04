# PoC 설계 — 건물 단위 공실 추정 (Building-level Vacancy Estimation)

> 출처: 2026.06.27 회의 「Page 방향성」 ※중요포인트 — *"실제 공실 건물의 위치를 어떻게 얻고, 어떻게 시각적으로 구현할 것인가?"*
>
> 기존 [`data/collectors/vacancy.py`](../data/collectors/vacancy.py)는 **구(자치구) 단위** 공실 프록시까지만 산출한다. 본 PoC는 그 위에 **건물(BLDG) 단위** 공실 추정 레이어를 얹어 [`buildings.py`](../apps/backend/app/api/v1/buildings.py)의 더미를 실데이터로 대체하는 것을 목표로 한다.

---

## 설계 근거 — Q1·Q2 (2026.06.27 회의 ※중요포인트)

> 본 PoC와 Page 구현이 답해야 하는 두 핵심 질문에 대한 확정 답. 모든 설계 결정의 출발점.

### Q1. 유동인구·공실 로데이터를 어떻게 얻는가
전제: 통신사 원본(CDR)과 "건물이 비었다"는 사실은 날것으로 공개되지 않는다 → **① 받아오는 것**과 **② 결합해 만드는 것**으로 나뉜다.

- **유동인구(받아온다·무료)**: 주력 = **서울시 생활인구(SPOP, 서울시+KT 추계, 행정동·집계구×1시간)**. 실시간 흐름 데모 = 서울 실시간 도시데이터(50m×5분). 전국·세밀 확장 = SKT 지오비전/KDX(유료).
- **공실(거시는 받고, 건물단위는 만든다)**: 거시 공실률 = 한국부동산원 임대동향조사를 그대로 수신. 건물 단위는 직접 로데이터 부재 → **소상공인 상가정보(활성 점포=분자) ⊕ 건축물대장 전유공용면적(상업 호 수=분모)** 결합으로 `공실률=1−점유율` 산출.
- **한 줄**: 유동인구는 생활인구를 로데이터로 받고, 공실은 거시는 부동산원에서 받되 건물단위는 상가정보+건축물대장을 결합해 만든다. → 이 "만든다"가 곧 §2 추정 로직.

### Q2. 실제 공실 위치·유동인구 흐름을 어떻게 시각화하는가
베이스: 회의 1번대로 **네이버 지도(Naver Maps JS API v3) 확대** 위 2개 오버레이.

- **공실 위치**: GIS건물통합정보 footprint를 `naver.maps.Polygon`으로 그리고 `fillColor`를 점유율 상태(🟢full→🟡partial→🟠high→🔴suspected_empty)로 매핑. 건물 클릭 → 상세 패널 + Three.js 3D 디지털 트윈.
- **유동인구 흐름**: `naver.maps.visualization.HeatMap`(생활인구 밀도) + **시간 슬라이더 애니메이션**(시간대별 값 재생 = 흐름 근사). 진짜 이동 벡터(OD 유선)는 생활이동/PLIP 확보 시 확장.
- **한 줄**: 공실은 네이버 지도 위 건물 폴리곤 색상+클릭 3D 트윈, 유동인구는 생활인구 히트맵+시간 슬라이더.

---

## 0. 핵심 결론 (요약)

- **건물이 "지금 비어있다"는 직접 데이터는 공공에 없다.** → **capacity(수용 상가 수) 대비 occupancy(활성 점포 수)** 로 **추정**한다.
- 추정 공식: `공실률_bldg = 1 − (매칭된 활성 점포 수 / 건물의 상가 수용 능력)`
- 두 데이터원의 **결합**이 전부다:
  1. **소상공인 상가정보** → 건물에 실제 영업 중인 점포(분자, occupancy)
  2. **건축물대장(건축HUB)** → 건물이 담을 수 있는 상가 호 수(분모, capacity)
  3. **GIS건물통합정보** → 건물 폴리곤(지도 시각화 + 좌표 매칭 보정)
- 조인은 2단계(D1 확정): 상가정보 **`건물관리번호(bdMgtSn)`로 점포를 건물별 그룹핑** → 그 건물의 **지번(시군구+법정동+본번+부번)으로 건축물대장 조회**. (bdMgtSn은 대장 PK와 별개 식별자)
- **PoC 범위: 서울 강남구 신사동 「가로수길」 코어 축** (§0.5 참조).

---

## 0.5. PoC 거점 선정 — 강남구 신사동 가로수길

목표 지역은 **서울 강남구**. 강남구 주요 상권을 SpaceOS 선정 기준(데이터 가용성 + 공실 신호 + 경계 명확성 + B2B 접근성)으로 비교한 결과 **신사동 가로수길**로 확정한다.

### 강남구 상권 비교 (2025년 기준)
| 상권 | 공실률 | 규모/유동인구 | 경계 | 적합도 |
|---|---|---|---|---|
| **가로수길(신사동)** | **41.6%** (서울 최고, 3년째↑) | 중, 선형 가로 | 명확 | **최상** |
| 강남역·강남대로 | 13.2% (중대형) | 최대 | 너무 넓음 | 중(1주 PoC 과대) |
| 청담 명품거리 | 15.7% | 중 | 보통 | 중 |
| 압구정로데오 | 8.3% (회복세) | 중~상 | 보통 | 하(공실 신호 약) |

### 선정 근거 (SpaceOS 관점)
1. **공실 신호 압도적** — 41.6%(서울 최고). 건물 단위 추정 로직의 **검증·시연에 이상적**(공실 표본이 풍부해야 precision/recall 측정 가능). 압구정로데오(8.3%)는 신호가 약해 데모 임팩트 낮음.
2. **거시 지표가 실체를 숨기는 사례** — 가두상권 공실률 **41.6%** vs 신사역 집합상가 **9.99%**. 거시 통계로 안 보이는 건물별 실상을 디지털 트윈이 드러낸다는 SpaceOS 핵심 가치제안을 그대로 증명.
3. **B2B 내러티브 최강** — "몰락한 상권의 재생 진단"은 자산운용사·건물주·강남구청이 즉시 반응 → M&A/파일럿 연결.
4. **경계가 좁고 명확** — 행정동 신사동 내 선형 축이라 1주 PoC에 적정한 건물 수.

### 공간 범위 정의 (구현 파라미터)
- **행정동**: 강남구 신사동 (법정·행정동 동일).
- **코어 축**: 가로수길 중심(신사역 8번 출구 ~ 압구정 방향) **중심좌표 ≈ (lat 37.5205, lon 127.0230) 반경 400m**.
- **API 수집 파라미터**: `storeListInRadius`(cx/cy/radius=400) **또는** `storeListInDong`(신사동 행정동코드) 후 반경 필터.
- **건물 후보**: 위 반경 내 GIS건물통합정보 폴리곤(상업 주용도) 전수.

---

## 1. 데이터원과 필드

### 1-1. 소상공인시장진흥공단 상가(상권)정보 — *분자(occupancy)*
- 포털: `data.go.kr/data/15083033` · API 기관 `B553077` 엔드포인트 `apis.data.go.kr/B553077/api/open/sdsc2`
- 조회 방식: `storeListInDong`(행정동), `storeListInRadius`(반경), **`storeListInBuilding`(건물관리번호 단위)**
- 핵심 필드:

| 필드 | 의미 | 용도 |
|---|---|---|
| `bizesId` | 상가업소번호 | 점포 고유 ID |
| `bldMngNo` | **건물관리번호(25자리)** | **← 건축물대장 조인 골든 키** |
| `flrNo` / `hoNo` | 층정보 / 호정보 | 층·호 단위 매칭, capacity 정밀화 |
| `lon` / `lat` | 경도 / 위도 | 폴리곤 point-in-polygon 매칭 |
| `indsLclsNm` 등 | 업종 대/중/소분류 | 상업 점포 필터, Program/GNN 연동 |
| `rdnmAdr` / `lnoAdr` | 도로명 / 지번 주소 | 주소 정규화 매칭(폴백) |

- **한계**: 국세청 등록 기반 → 분기 갱신, 신규·무등록·온라인 업종 누락, **폐업≠즉시 반영**.

### 1-2. 국토교통부 건축HUB 건축물대장 — *분모(capacity)*
- 포털: `data.go.kr/data/15134735` (건축HUB 건축물대장정보 서비스)
- 사용 서브 API:

| 서브 API | 제공 | capacity 산출 기여 |
|---|---|---|
| 표제부 `getBrTitleInfo` | 주용도(`mainPurpsCdNm`), 연면적, 지상층수, 사용승인일, 위치 | 상업용 건물 여부 판별 |
| 층별개요 `getBrFlrOulnInfo` | 층별 용도(`etcPurps`)·면적 | 상업 용도 층 식별 |
| 전유부 `getBrExposInfo` | 집합건물의 **호(unit) 목록** + 호별 용도 | **집합건물 상가 호 수 = capacity** |

- **capacity 추정 규칙**:
  - **집합건물**(상가/오피스텔 등): 전유부에서 `근린생활시설·판매시설·업무시설` 용도 **호 수**를 직접 카운트 → 가장 정확.
  - **일반(비집합)건물**: 층별개요의 상업용도 층수 × (층당 점포 추정치) **또는** 상업 연면적 ÷ 표준 점포면적(예 33㎡) 으로 근사.
- 조인키: `bldMngNo` / PNU(19자리, 대지위치 파생) / `mgmBldrgstPk`.

### 1-3. 국토교통부 GIS건물통합정보 — *시각화 + 매칭 보정*
- 포털: `data.go.kr/data/15083092` — 건물 **footprint 폴리곤** + PNU + 대표 좌표.
- 용도: (a) 지도·3D 트윈 렌더용 건물 형상, (b) 상가 좌표를 폴리곤에 **point-in-polygon**으로 떨궈 `bldMngNo` 누락·오표기 보정(PostGIS `ST_Contains`).

---

## 2. 추정 로직 (Estimation)

### 2-1. 점포 → 건물 매칭 (D1 확정 조인)

> **D1 검증 결과(중요 정정):** 상가정보의 `건물관리번호(bdMgtSn, 25자리)`는 건축물대장(건축HUB) API의 PK(`mgmBldrgstPk`)와 **동일 식별자가 아니다.** 건축물대장은 **지번(시군구+법정동+본번+부번)**으로 조회된다. 따라서 조인은 두 단계로 분리한다.

1. **건물 그룹핑 = `bdMgtSn`** — 같은 `bdMgtSn`을 가진 점포들을 한 물리 건물로 묶어 **활성 점포 수(분자)**를 센다. (상가정보는 `bdMgtSn`을 실제로 제공 — D1 확인)
2. **대장 조회 = 지번** — 그 건물 그룹의 점포가 가진 **시군구코드·법정동코드·지번본번·지번부번**을 건축HUB 요청 파라미터(`sigunguCd`/`bjdongCd`/`bun`/`ji`)로 넘겨 표제부·전유공용면적을 받아 **capacity(분모)**를 산출한다.
3. **좌표 point-in-polygon (보정·폴백)** — `bdMgtSn`/지번이 누락·불일치인 점포는 `lon/lat`를 GIS건물폴리곤에 `ST_Contains`로 떨궈 건물에 귀속.

> 매칭 결과에 `match_method`(bdMgtSn_group / pip / addr)와 신뢰도 플래그를 남겨 품질을 추적한다.

### 2-2. 건물 단위 지표 산출
```
active_stores  = 건물에 매칭된 '상업 업종' 활성 점포 수      # 분자
capacity       = 건물의 상가 수용 호 수(§1-2 규칙)          # 분모
occupancy      = clamp(active_stores / capacity, 0, 1)
vacancy_bldg   = round((1 - occupancy) * 100, 1)            # 0~100
```

### 2-3. 상태 분류 (지도 색상 매핑)
| occupancy | status | 색상(예) |
|---|---|---|
| ≥ 0.9 | `full` (만실) | 녹색 |
| 0.5 ~ 0.9 | `partial` (부분공실) | 황색 |
| 0 < x < 0.5 | `high_vacancy` (고공실) | 주황 |
| = 0 & 상업용도 | `suspected_empty` (공실 의심 건물) | 적색 |
| 상업용도 아님 | `n/a` (제외) | 회색 |

---

## 3. 보정·검증 (Calibration & Validation)

1. **거시 정합(구 단위 앵커)**: 건물 추정 공실률을 자치구로 재집계 → **한국부동산원 공식 공실률**과 비교, 보정계수 α로 스케일 정렬. 이 α가 기존 `vacancy.py`의 `base` 앵커와 물리적으로 연결된다.
2. **지상 검증(ground truth)**: 거점 상권 **샘플 20~30개 건물**을 네이버 지도/로드뷰·현장으로 라벨링 → precision/recall 측정.
3. **품질 지표**: 매칭률(`match_method`별), capacity 추정 커버리지, 구-집계 오차(±%p).

### 알려진 편향(문서화 필수)
- 상가정보 갱신 지연(분기) → **폐업 후에도 한동안 "영업 중"으로 잡힘**.
- capacity 근사 오차(일반건물 층당 점포수 가정).
- 사무실·주거는 상가정보에 없음 → **상업용 건물로 대상 한정**.
- 결과는 반드시 **"추정치(estimate)"** 로 라벨링, 확정 공실로 오인 금지.

---

## 4. 아키텍처 정합 (Bronze / Silver / Gold)

```
Bronze  data/collectors/  raw JSON 적재
  ├─ stores_raw          storeListInDong/Building 응답
  ├─ bldg_ledger_raw     건축HUB 표제부/층별/전유부
  └─ bldg_gis_raw        GIS건물통합정보 폴리곤

Silver  정규화 + 매칭 (PostGIS)
  ├─ dim_building        건물 마스터(bldMngNo, PNU, geom, capacity, 주용도)
  ├─ fact_store          점포(bizesId, bldMngNo, geom, 업종, active)
  └─ map_store_building  매칭 테이블(match_method, 신뢰도)

Gold  집계 산출물
  └─ building_vacancy    건물별 occupancy/vacancy_bldg/status  → API·GeoJSON 소스
```

- **신규 콜렉터**: `data/collectors/building_vacancy.py` (기존 `vacancy.py`는 구 단위 유지, 본 모듈이 건물 단위 담당).
- **API 연동**:
  - `districts.py` `/heatmap` → 건물 폴리곤 + `vacancy_bldg` 속성의 **GeoJSON FeatureCollection** (feature-page.md 3-①).
  - `buildings.py` `/{id}/history` → `dim_building` + 점포 변천으로 더미 교체.
- **ML 연동**: `building_vacancy` Gold 테이블이 [`vacancy_lstm.py`](../ml/models/lstm/vacancy_lstm.py)의 시계열 입력 피처가 되어 "공실 예측 70%+" KPI로 연결.

---

## 5. PoC 실행 계획 (강남구 신사동 가로수길, ~1주)

| 단계 | 작업 | 산출물 |
|---|---|---|
| D1 | `DATA_GO_KR_SERVICE_KEY` 발급, 3개 API 응답 스키마 확정, 신사동 행정동코드·가로수길 중심좌표 확정 | API 필드 매핑표 |
| D2 | Bronze 수집: 가로수길 반경 400m 점포(`storeListInRadius`)·대장·폴리곤 raw 적재 | `*_raw.json` |
| D3 | Silver: `bldMngNo` 직접 조인 + PIP 폴백 매칭 | `map_store_building` |
| D4 | capacity 산출(집합=전유부 호수 / 일반=면적근사) + occupancy 계산 | `building_vacancy` |
| D5 | 상권 집계 vs 부동산원(신사역 상권) 공실률 α보정, 로드뷰 라벨 20~30건 검증 | 검증 리포트 |
| D6 | `/heatmap` GeoJSON 출력 + Mapbox 색상 렌더 | 가로수길 건물 공실 히트맵 |

### 성공 기준 (PoC exit)
- 가로수길 코어 축 내 **상업 건물 전수에 대해 `occupancy` 산출** 및 지도 색상 시각화.
- **상권 집계치가 부동산원 신사역/가두상권 공실률과 정합**(±5%p, 단 가두상권 41.6% vs 집합상가 9.99% 이원성 반영), 로드뷰 라벨 대비 **status 정확도 70%+**.
- `bldMngNo` 직접 매칭률 리포트(잔여는 PIP/주소 폴백 커버).

> **가로수길 특이점(검증 시 반영):** 공실률이 매우 높아(41.6%) `suspected_empty`·`high_vacancy` 표본이 풍부 → precision/recall 측정에 유리. 단 부동산원 "가두상권(도로변 1층)" 수치와 "집합상가 전체" 수치가 크게 다르므로, 검증 시 **1층 도로변 건물**과 **후면 집합건물**을 분리 집계해 비교한다.

---

## 6. 최소 코드 스케치 (설계 확인용 · 미구현)

```python
# data/collectors/building_vacancy.py  (설계 초안)
COMMERCIAL_PURPS = {"제1종근린생활시설", "제2종근린생활시설", "판매시설", "업무시설"}

def estimate_building_vacancy(bld_mng_no: str, key: str) -> dict:
    ledger  = fetch_ledger(bld_mng_no, key)          # 표제부/층별/전유부
    stores  = fetch_stores_in_building(bld_mng_no, key)  # storeListInBuilding
    capacity = count_commercial_units(ledger)        # 집합=전유부 호수 / 일반=면적근사
    active   = sum(1 for s in stores if is_commercial(s))
    occ      = min(active / capacity, 1.0) if capacity else None
    return {
        "bldMngNo": bld_mng_no,
        "capacity": capacity, "active_stores": active,
        "occupancy": occ,
        "vacancy_bldg": None if occ is None else round((1 - occ) * 100, 1),
        "status": classify(occ, ledger),            # full/partial/high_vacancy/suspected_empty
        "match_method": "exact_bldMngNo",
    }
```

---

## 관련 문서·코드
- [feature-page.md](feature-page.md) — Page(공실 히트맵 + 3D 트윈) 전체 스펙
- [vacancy.py](../data/collectors/vacancy.py) — 기존 구 단위 공실 프록시(본 PoC의 거시 앵커)
- [buildings.py](../apps/backend/app/api/v1/buildings.py) — 교체 대상(더미 → 실데이터)
- [vacancy_lstm.py](../ml/models/lstm/vacancy_lstm.py) — 공실 예측 모델(Gold 입력)
