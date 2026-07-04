# A단계 — 무료 API 인증키 발급 절차 + 응답 필드 스펙

> 빌드 순서(§0-3)의 산출물. Page의 4대 데이터(유동인구·공실률·임대시세·인구밀도)를 확보하기 위한 인증키 발급 방법과 각 API 응답 필드를 한곳에 정리한다. 조인·시각화 설계 근거는 [poc-building-vacancy.md](poc-building-vacancy.md) 참조.

## 0. 한눈에 보기 — 키 5종 × 4대 데이터

| 데이터 | 소스 | .env 변수 | 발급처 | 비용 |
|---|---|---|---|---|
| 공실(건물·거시) | 공공데이터포털: 상가정보 + 건축물대장 | `DATA_GO_KR_SERVICE_KEY` | data.go.kr | 무료 |
| 임대시세·거시공실 | 한국부동산원 임대동향조사 | (CSV) / `DATA_GO_KR_SERVICE_KEY` | data.go.kr | 무료 |
| 유동인구 | 서울 생활인구(서울시+KT) | `SEOUL_OPENAPI_KEY` | data.seoul.go.kr | 무료 |
| 인구밀도 | 통계청 SGIS 총조사 | `SGIS_CONSUMER_KEY/SECRET` | sgis.kostat.go.kr | 무료 |
| 지도(베이스) | 네이버 NCP Maps | `VITE_NAVER_MAPS_KEY_ID` | NCP 콘솔 | 무료(쿼터) |
| 건물 폴리곤 | GIS건물통합정보 | (파일 다운로드) | data.go.kr | 무료 |

> 키는 실질 3개(+지도): **공공데이터포털 1개로 상가·대장·부동산원 공용**, 서울광장 1개, SGIS 2개(key/secret), 네이버 지도 1개.

---

## 1. 공공데이터포털 `DATA_GO_KR_SERVICE_KEY` — 상가정보 + 건축물대장 + 부동산원

### 발급 절차
1. [data.go.kr](https://www.data.go.kr) 회원가입·로그인.
2. 각 API 상세페이지에서 **[활용신청]** 클릭 → 활용목적 입력 → 신청. **자동승인**(즉시).
3. **마이페이지 > 데이터활용 > 인증키**에서 **일반 인증키** 확인. **Decoding(디코딩) 키**를 `.env`에 넣는다(코드에서 URL 인코딩 처리).
4. 하나의 인증키로 신청한 **모든 API 공용**(상가정보·건축물대장·부동산원 각각 활용신청은 필요).

### 1-A. 소상공인 상가(상권)정보 — 공실 *분자(활성 점포)*
- 신청: `data.go.kr/data/15012005/openapi.do`
- 엔드포인트(base `http://apis.data.go.kr/B553077/api/open/sdsc2`):
  `storeListInRadius`(반경) · `storeListInDong`(행정동) · `storeListInBuilding`(건물)
- 요청 파라미터: `serviceKey`, `type=json`, `numOfRows`, `pageNo` + (반경: `radius`,`cx`(경도),`cy`(위도)) / (동: `divId=adongCd`,`key`)

| 응답 필드 | 의미 | PoC 용도 |
|---|---|---|
| `bizesId` / `bizesNm` | 상가업소번호 / 상호명 | 점포 식별 |
| **`bdMgtSn`** | 건물관리번호(25자리) | ★ 건물 그룹핑 |
| `lnoMnno` / `lnoSlno` | 지번 본번 / 부번 | ★ 대장 조회 키 |
| `flrNo` / `hoNo` | 층 / 호 | capacity 정밀화 |
| `lon` / `lat` | 경도 / 위도 | PIP 매칭 |
| `indsLclsNm`·`indsMclsNm`·`indsSclsNm` | 업종 대/중/소 | 상업 필터 |
| `signguCd` / `adongCd` | 시군구 / 행정동 코드 | 지역 필터 |

### 1-B. 건축물대장정보 서비스 — 공실 *분모(상업 호 수)*
> ⚠️ 2종 존재. **권장 = `15044713`(건축물대장정보 서비스, BldRgstService_v2)** — 성숙·자동승인·프로브 코드와 일치. `15134735`(건축HUB)는 신규이나 엔드포인트 경로가 다르고 승인 검토가 있을 수 있어 PoC에는 ①을 쓴다.
- 신청: [`data.go.kr/data/15044713/openapi.do`](https://www.data.go.kr/data/15044713/openapi.do) → [활용신청](보통 자동승인)
- 엔드포인트(base `http://apis.data.go.kr/1613000/BldRgstService_v2`):
  `getBrTitleInfo`(표제부) · `getBrExposPubuseAreaInfo`(전유공용면적) · `getBrFlrOulnInfo`(층별개요)
- 발급 확인(브라우저): `…/getBrTitleInfo?serviceKey={디코딩키}&sigunguCd=11680&bjdongCd=10700&platGbCd=0&bun=0000&ji=0000&_type=json&numOfRows=10&pageNo=1`
- 대안(원기관 직접): 세움터 건축데이터 민간개방 [open.eais.go.kr](https://open.eais.go.kr) / 건축HUB [hub.go.kr](https://www.hub.go.kr)
- 요청 파라미터: `serviceKey`, `sigunguCd`(5), `bjdongCd`(5), `platGbCd`(0=대지/1=산), `bun`(4자리), `ji`(4자리), `_type=json`, `numOfRows`, `pageNo`

| 응답 필드 | 의미 |
|---|---|
| `mainPurpsCdNm` | 주용도명(상업 판별) |
| `totArea` / `grndFlrCnt` / `hoCnt` | 연면적 / 지상층수 / 호수 |
| `exposPubuseGbCdNm` | 전유/공용 구분 (★ 전유 호만 카운트) |
| `mainPurpsCdNm`(호별) | 호별 용도 (★ 상업 전유 호 = capacity) |
| `dongNm` / `hoNm` / `flrNo` | 동 / 호 / 층 |

### 1-C. (선택) 부동산원 임대동향 API — 거시 공실률·임대료
- 신청: `data.go.kr/data/15002275/openapi.do` (신규환경 `15099345`)
- R-ONE 통계 API 계열: 요청 `serviceKey`, `STATBL_ID`(통계표ID), `DTACYCLE_CD`(주기, 분기=`QY`), `WRTTIME_IDTFR_ID`(기간), `CLS_ID`(분류) → 응답 `TBL_NM`/`ITM_NM`/`CLS_NM`/`WRTTIME_DESC`/`DTA_VAL`.
- **권장**: 아래 §4 CSV가 더 단순(분기 갱신이라 파일로 충분).

---

## 2. 서울 열린데이터광장 `SEOUL_OPENAPI_KEY` — 유동인구(생활인구)

### 발급 절차
1. [data.seoul.go.kr](https://data.seoul.go.kr) 회원가입·로그인.
2. **[Open API] > 인증키 신청/관리** → 인증키 발급(**즉시**). URL/앱 정보 입력.

### 생활인구 API (행정동 단위, KT 기반)
- 서비스명: **`SPOP_LOCAL_RESD_DONG`** (행정동 단위 서울 생활인구) — 자치구 단위는 `…_JACHI`
- 요청 URL 형식(경로 파라미터):
  `http://openapi.seoul.go.kr:8088/{KEY}/{TYPE}/{SERVICE}/{START}/{END}/{기준일자}`
  예: `.../{KEY}/json/SPOP_LOCAL_RESD_DONG/1/1000/20250601`

| 응답 필드 | 의미 |
|---|---|
| `STDR_DE_ID` | 기준일(YYYYMMDD) |
| `TMZON_PD_SE` | 시간대(00~23) → **시간 슬라이더 축** |
| `ADSTRD_CODE_SE` | 행정동코드 (신사동으로 필터) |
| `TOT_LVPOP_CO` | 총생활인구수 → **히트맵 밀도값** |
| `MALE_F0T9_LVPOP_CO` 등 | 성별·연령대별 생활인구 |

> 필드명은 데이터셋마다 편차 → 상세페이지 **[미리보기]**에서 최종 확인. 실시간 흐름 데모가 필요하면 서비스 `citydata_ppltn`(실시간 도시데이터·5분·50m 격자) 병행.

---

## 3. 통계청 SGIS `SGIS_CONSUMER_KEY` / `SGIS_CONSUMER_SECRET` — 인구밀도

### 발급 절차
1. [sgis.kostat.go.kr/developer](https://sgis.kostat.go.kr/developer) (국가데이터처 이관: `sgis.mods.go.kr`) 회원가입.
2. **개발지원센터 > 서비스 신청** → 약관동의 → 정보입력 → **테스트키 즉시발급**(`consumer_key`,`consumer_secret`). 상용키는 마이페이지에서 승인 신청.

### 2단계 호출 (인증 → 데이터)
1. **인증(accessToken 발급, 유효 ~4시간)**:
   `GET https://sgisapi.kostat.go.kr/OpenAPI3/auth/authentication.json?consumer_key={KEY}&consumer_secret={SECRET}`
   → 응답 `result.accessToken`
2. **총조사 주요지표(총인구·인구밀도)**:
   `GET https://sgisapi.kostat.go.kr/OpenAPI3/stats/population.json?accessToken={TOKEN}&year={YYYY}&adm_cd={코드}&low_search={0|1|2}`

| 요청 파라미터 | 의미 |
|---|---|
| `year` | 연도(2015~최신) |
| `adm_cd` | 행정구역코드(미지정=전국, 2~8자리) — 강남구 `11680` |
| `low_search` | 하위통계 포함(0/1/2, 기본 1) |

| 응답 필드 | 의미 |
|---|---|
| `adm_cd` / `adm_nm` | 행정구역 코드 / 명 |
| `tot_ppltn` | 총인구 |
| **`ppltn_dnsty`** | **인구밀도** → 코로플레스 값 |
| `avg_age` / `tot_family` / `tot_house` | 평균나이 / 가구 / 주택 |

---

## 4. 한국부동산원 — 공실률 + 임대시세 (권장: CSV)

### 발급/획득 절차
- **권장(파일)**: data.go.kr 로그인 후 아래 CSV **다운로드**(별도 인증키 불필요, 분기 갱신):
  - 공실률: 오피스 `15069730` · 중대형상가 `15069735` · 소규모상가 `15069726`
  - 임대료: 소규모상가 `15069766` (오피스·중대형 동종 계열)
- **선택(API)**: §1-C (data.go.kr 키 공용).

| CSV 주요 컬럼 | 의미 |
|---|---|
| 지역/상권명 | 시도·시군구·상권(예: 강남대로, 신사역) |
| 공실률(%) | 오피스/중대형/소규모 상가별 |
| 임대료(천원/㎡) | **평당 = ㎡값 × 3.3058** |
| 기준분기 | YYYY.Q |

---

## 5. 네이버 — 지도(베이스) + 검색/데이터랩

### 5-A. NCP Maps `VITE_NAVER_MAPS_KEY_ID` (지도 — 필수)
1. [NCP 콘솔](https://console.ncloud.com) > **Services > Maps > Application 등록**.
2. **Web 서비스 URL**에 `http://localhost:5173`(개발) + 배포 도메인 **등록 필수**(미등록 도메인은 인증오류).
3. 발급된 **Client ID(=ncpKeyId)**를 `apps/frontend/.env`의 `VITE_NAVER_MAPS_KEY_ID`에.
   → 로더는 [naverMap.ts](../apps/frontend/src/lib/naverMap.ts)가 `…/maps.js?ncpKeyId={ID}&submodules=visualization`로 사용.

### 5-B. 네이버 개발자센터 `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` (검색·데이터랩 — 선택)
- [developers.naver.com](https://developers.naver.com) > 애플리케이션 등록 > **검색 API + 데이터랩(검색어트렌드)** 사용 설정 → Client ID/Secret.
- 헤더 `X-Naver-Client-Id` / `X-Naver-Client-Secret`로 호출.

---

## 6. GIS건물통합정보 — 건물 footprint 폴리곤 (파일)
- `data.go.kr/data/15083092` — 시도별 **파일(shp/GeoJSON) 다운로드**(API 아님). **강남구** 분만 받아 PoC 폴리곤으로.

---

## 7. `.env` 체크리스트

```ini
# apps/frontend/.env
VITE_NAVER_MAPS_KEY_ID=          # NCP Maps Client ID (도메인 등록 필수)

# data/.env  (백엔드/수집)
DATA_GO_KR_SERVICE_KEY=          # 공공데이터포털 Decoding 키 (상가·대장·부동산원 공용)
SEOUL_OPENAPI_KEY=               # 서울 열린데이터광장 (생활인구)
SGIS_CONSUMER_KEY=               # 통계청 SGIS
SGIS_CONSUMER_SECRET=
NAVER_CLIENT_ID=                 # (선택) 검색/데이터랩
NAVER_CLIENT_SECRET=
```

### 우선순위 (크리티컬 패스)
1. **`DATA_GO_KR_SERVICE_KEY`** — 건물 공실(1-4)·거시공실·임대 → [probe_garosu_d1.py](../data/probe_garosu_d1.py) 실행 관문.
2. **`VITE_NAVER_MAPS_KEY_ID`** — 이미 만든 MapShell 지도 렌더.
3. `SEOUL_OPENAPI_KEY` → 유동인구. 4. `SGIS_*` → 인구밀도.
