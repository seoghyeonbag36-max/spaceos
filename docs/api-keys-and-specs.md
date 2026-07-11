# API 인증키 발급 절차 + 응답 필드 스펙 — A단계(Page) + B단계(PPPP 전체)

> **A단계(§0~6)**: Page의 4대 데이터(유동인구·공실률·임대시세·인구밀도) 인증키. 조인·시각화 설계 근거는 [poc-building-vacancy.md](poc-building-vacancy.md) 참조.
> **B단계(§8~9)**: Platform·Posting·Program까지 Gold 데이터 구축에 필요한 확장 키. 신규 발급은 2개(카카오·LLM)뿐이고 나머지는 기존 키에 활용신청만 추가한다. (舊 LOCALDATA는 2026-04-16 폐쇄 → data.go.kr 이관, §8-B)

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
> ⚠️ **2026-07 확정: `15134735`(건축HUB, BldRgstHubService)만 사용.** 구 `15044713`(BldRgstService_v2)는 서비스 종료 확인('Unexpected errors' 반환 — 키와 무관). 건축HUB는 동일 키·동일 메서드명·`_type=json` 호환 검증 완료(resultCode 00).
- 신청: [`data.go.kr/data/15134735/openapi.do`](https://www.data.go.kr/data/15134735/openapi.do) → [활용신청] (✅ 완료됨)
- 엔드포인트(base `http://apis.data.go.kr/1613000/BldRgstHubService`):
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

### 1-C. 부동산원 상업용부동산 임대조사 API — 거시 공실률·임대료 (✅ 키 확보됨)
> **2026-07 확보: 팀원이 "상업용부동산임대조사" API 키 발급.** 문서 §4의 CSV 계획을 **자동 증분 API**로 격상. 상권(대분류) 단위라 건물 해상도는 없음 → Page의 **지역 앵커/보정 계수**로 사용(건물별 값은 §1-A×§1-B가 담당).
- 신청: `data.go.kr/data/15002275/openapi.do` (신규환경 `15099345`) / R-ONE 부동산통계 포털([r-one.co.kr](https://www.r-one.co.kr))은 별도 키 발급.
- R-ONE 통계 API 계열: 요청 `serviceKey`(또는 R-ONE 전용키 `REB_RONE_API_KEY`), `STATBL_ID`(통계표ID), `DTACYCLE_CD`(주기, 분기=`QY`), `WRTTIME_IDTFR_ID`(기간), `CLS_ID`(분류) → 응답 `TBL_NM`/`ITM_NM`/`CLS_NM`/`WRTTIME_DESC`/`DTA_VAL`.
- 제공 지표(상권별): **공실률·임대료(㎡당)·임대가격지수·투자수익률·전환율**.
- 활용: Page(거시 공실 앵커, `VACANCY_MODE=base`) + Posting(전략별 임대료·수익률 실데이터 치환) + Platform(공실률·임대료 시계열 피처).
- **참고**: §4 CSV는 오프라인 백업으로 유지(발급처 장애 시 폴백).

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
- **선택(API)**: §1-C — **2026-07 "상업용부동산임대조사" API 키 확보**(자동 증분 수집 가능). CSV는 폴백으로 유지.

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

## 6. 건물 footprint 폴리곤 — GIS건물통합정보 / V-World
- **파일**: `data.go.kr/data/15083092` — 시도별 **파일(shp/GeoJSON) 다운로드**(API 아님). **강남구** 분만 받아 PoC 폴리곤으로.
- **API(실제 사용 중)**: V-World 디지털트윈국토 `VWORLD_API_KEY` — GIS건물통합 WFS/데이터API. 발급: [vworld.kr](https://www.vworld.kr) 로그인 → 인증키 발급(도메인 `http://localhost:5173` 등록). `data/.env`에 이미 설정됨.

---

## 6-B. 토지이음 — 토지이용계획·용도지역·공시지가 (🆕 규제 레이어) `EUM_API_KEY`

> **2026-07 신규 확보.** 상가정보(§1-A)·건축물대장(§1-B)에 **"이 땅에서 무엇을 할 수 있는가"(규제·용도)** 축을 추가하는 신규 레이어. Page 공실 판별 정밀화 + Posting 입점 가능성 판정의 핵심 소스.

### 발급/획득
- 원자료: 토지이음 [eum.go.kr](https://www.eum.go.kr). API: data.go.kr "국토교통부 토지이용계획정보"·"개별공시지가" 계열 활용신청(자동승인) → 발급처에 따라 `DATA_GO_KR_SERVICE_KEY` 공용 또는 전용 `EUM_API_KEY`.

### 제공 정보 & 활용
| 응답 필드(대표) | 의미 | PPPP 활용 |
|---|---|---|
| `prposAreaNm` / 용도지역 | 일반상업·근린상업·일반주거 등 | ★ **Page**: 상업 필터 강화(§1-B 보완) / ★ **Posting**: 용도지역별 허용 업종 판정 |
| 행위제한(허용·금지 업종) | 지역별 입점 규제 | ★ **Posting**: `posting.py` 입점 가능성 더미 상수 치환 |
| `bcRat` / `vlRat` | 건폐율 / 용적률 | 개발 잠재력·capacity 추정 |
| `jimok` / 지목 | 대·잡종지 등 | 필지 성격 |
| `pblntfPclnd` / 개별공시지가 | ㎡당 공시지가 | 임대시세 추정·검증 보조 앵커 |

### 조인 키
- **필지 PNU(19자리)** 또는 지번(§1-A `lnoMnno`/`lnoSlno`) → 건물(`bdMgtSn`) ↔ 점포(`bizesId`)와 연결.

---

## 7. `.env` 체크리스트 (A+B단계 통합)

```ini
# apps/frontend/.env
VITE_NAVER_MAPS_KEY_ID=          # NCP Maps Client ID (도메인 등록 필수)

# data/.env  (수집 파이프라인)
DATA_GO_KR_SERVICE_KEY=          # 공공데이터포털 Decoding 키 (상가·대장·부동산원 + 국세청·가맹정보 공용)
SEOUL_OPENAPI_KEY=               # 서울 열린데이터광장 (생활인구 + 상권분석서비스 공용 — 별도 키 발급 말고 이 1개로 통일)
SGIS_CONSUMER_KEY=               # 통계청 SGIS
SGIS_CONSUMER_SECRET=
EUM_API_KEY=                     # [🆕 규제] 토지이음 토지이용계획·용도지역·공시지가 (§6-B, data.go.kr 공용일 수 있음)
REB_RONE_API_KEY=                # [♻️] 부동산원 상업용부동산 임대조사 (§1-C, R-ONE 전용키. data.go.kr 경로면 DATA_GO_KR 공용)
VWORLD_API_KEY=                  # 건물 폴리곤 V-World WFS/데이터API (§6, 도메인 등록 필수)
# (폐기) LOCALDATA_API_KEY — localdata.go.kr 2026-04-16 폐쇄. 인허가 이력은 DATA_GO_KR_SERVICE_KEY 공용(§8-B)
KAKAO_REST_API_KEY=              # [B·Program/Posting] 카카오 로컬 (장소·카테고리)
NAVER_CLIENT_ID=                 # [B·Program] 검색(블로그·지역)+데이터랩 — 선택→필수 승격
NAVER_CLIENT_SECRET=
INSTAGRAM_ACCESS_TOKEN=          # [B·Program] 보류 (비즈니스 계정+앱 검수 필요)
IG_USER_ID=

# apps/backend/.env
LLM_API_KEY=                     # [B·Program] Anthropic Claude 권장 (console.anthropic.com)
NAVER_MAPS_KEY_ID=               # NCP REST (Geocoding)
NAVER_MAPS_CLIENT_SECRET=
```

### 우선순위 (크리티컬 패스)
1. **`DATA_GO_KR_SERVICE_KEY`** — 건물 공실(1-4)·거시공실·임대 → [probe_garosu_d1.py](../data/probe_garosu_d1.py) 실행 관문. 발급 후 **국세청·가맹정보 활용신청도 같은 날 몰아서** 처리.
2. **`VITE_NAVER_MAPS_KEY_ID`** — 이미 만든 MapShell 지도 렌더.
3. `SEOUL_OPENAPI_KEY` → 유동인구 + 상권분석 시계열(Platform 학습 데이터의 핵심).
4. `SGIS_*` → 인구밀도.
5. 지방행정 인허가(개·폐업 이력, LSTM 라벨) → **data.go.kr 이관(§8-B)** — 기존 `DATA_GO_KR_SERVICE_KEY`로 업종별 인허가 API 활용신청만 추가(자동승인).
6. `KAKAO_REST_API_KEY`·`NAVER_CLIENT_ID/SECRET` → 즉시발급, Program 수집 시점에.
7. `LLM_API_KEY` → Program 구현 착수 시(유일한 유료).

---

## 8. B단계 — Platform·Posting·Program 확장 키

### 0-B. 한눈에 보기 — 기능 × 데이터 × 키

| 기능 | 데이터 | 소스 | .env 변수 | 신규 발급 |
|---|---|---|---|---|
| Platform | 상권 시계열: 추정매출·점포수·개폐업률·길단위인구·소득소비·상권변화지표 | 서울 상권분석서비스 | `SEOUL_OPENAPI_KEY` (기존) | ✕ |
| Platform | 개·폐업 인허가 이력 → LSTM 라벨·공실 히스토리 | 지방행정 인허가(data.go.kr, 舊 LOCALDATA) | `DATA_GO_KR_SERVICE_KEY` (기존) | ✕(활용신청) |
| Platform·Page | 사업자 휴폐업 상태 검증 | 국세청(data.go.kr) | `DATA_GO_KR_SERVICE_KEY` (기존) | ✕(활용신청) |
| Posting | 업종별 창업비용(가맹금·인테리어) | 공정위 가맹정보(data.go.kr) | `DATA_GO_KR_SERVICE_KEY` (기존) | ✕(활용신청) |
| Posting | 임대시세·공실률·추정매출 | §4 CSV + 상권분석 재사용 | — | ✕ |
| Program | LLM 콘텐츠 생성 + 상가 이미지 분석(vision) | Anthropic Claude | `LLM_API_KEY` (backend) | **○**(유료) |
| Program | 블로그 리뷰·검색 트렌드 | 네이버 검색+데이터랩(§5-B) | `NAVER_CLIENT_ID/SECRET` | **○** |
| Program·Posting | 장소·카테고리·좌표 크로스체크 | 카카오 로컬 | `KAKAO_REST_API_KEY` | **○** |
| Program | 인스타그램 해시태그·리뷰 | Meta Graph API / 크롤러 | `INSTAGRAM_ACCESS_TOKEN` | △ 보류 |

> ⚠️ **서울 한정 주의**: 생활인구(§2)·상권분석서비스(§8-A)는 서울시만 제공. 거점을 라페스타(고양시)로 확장하면 경기데이터드림 + 소상공인 상권정보로 대체 설계가 필요하다. PoC 거점(신사동 가로수길)은 문제 없음.

### 8-A. 서울 상권분석서비스 — Platform 시계열 (기존 `SEOUL_OPENAPI_KEY` 공용) ✅
- 발급: 추가 키 불필요 — §2와 동일 키·동일 URL 형식(`http://openapi.seoul.go.kr:8088/{KEY}/json/{SERVICE}/{START}/{END}/…`). 분기 단위 갱신.
- ⚠️ **2026-07 정리**: 팀원이 "서울시 상권분석 서비스" 키를 별도 발급했으나, 열린데이터광장은 **계정당 인증키 1개로 전 서비스 공용**이다 → **기존 `SEOUL_OPENAPI_KEY` 하나로 통일**하고 이중 키 관리는 지양(별도 발급 키는 백업으로만 보관).
- 주요 서비스(상권 단위, 서비스명은 상세페이지 [미리보기]에서 최종 확인):
  `TbgisTrdarRelm`(상권영역 폴리곤) · `VwsmTrdarSelngQq`(추정매출) · `VwsmTrdarStorQq`(점포·개폐업) · `VwsmTrdarFlpopQq`(길단위인구) · `VwsmTrdarRepopQq`(상주인구) · `VwsmTrdarWrcPopltnQq`(직장인구) · `VwsmTrdarIncomeQq`(소득소비) · `VwsmTrdarFcltyQq`(집객시설) · `VwsmTrdarIxQq`(상권변화지표)

| 응답 필드(대표) | 의미 | 용도 |
|---|---|---|
| `TRDAR_CD` / `TRDAR_CD_NM` | 상권 코드/명 | ★ Platform의 조인 키 (가로수길 상권 필터) |
| `STDR_YYQU_CD` | 기준 년분기 | LSTM 시계열 축 |
| `SVC_INDUTY_CD_NM` | 서비스 업종명 | GNN 노드 속성 |
| `THSMON_SELNG_AMT` | 당월(분기) 추정매출액 | LSTM 피처 + Posting 예상매출 근거 |
| `STOR_CO` / `OPBIZ_RT` / `CLSBIZ_RT` | 점포수 / 개업률 / 폐업률 | LSTM 피처·라벨 보조 |

### 8-B. 지방행정 인허가 — 개·폐업 이력 (data.go.kr 이관, 기존 키 공용)
> ⚠️ **2026-04-16 localdata.go.kr 폐쇄.** 행안부가 인허가 195종 + 생활편의 14종을 공공데이터포털(data.go.kr)로 통합 개방(195종에 **이력 데이터 신규 제공** — LSTM 라벨에 오히려 유리). `LOCALDATA_API_KEY`는 폐기.
1. [data.go.kr](https://www.data.go.kr)에서 **"행정안전부 인허가"** 검색 → 필요한 업종(일반음식점·휴게음식점 등)별 API/파일 **활용신청**(자동승인) → 기존 `DATA_GO_KR_SERVICE_KEY` 공용.
2. 초기 적재는 파일(CSV) 다운로드, 증분은 API 권장. 응답 필드(`apvPermYmd`/`dcbYmd`/`trdStateNm` 등)와 요청 파라미터는 이관 후 변경 가능성이 있으므로 **활용신청 후 실제 응답으로 재확정**하고, [data/collectors/localdata.py](../data/collectors/localdata.py)의 폐쇄된 엔드포인트를 신규 스펙으로 교체한다(TODO).

| 응답 필드(대표) | 의미 |
|---|---|
| `apvPermYmd` / `dcbYmd` | 인허가일자 / **폐업일자** (★ LSTM 라벨·공실 히스토리) |
| `trdStateNm` / `dtlStateNm` | 영업상태 / 상세상태 |
| `siteWhlAddr` / `rdnWhlAddr` | 지번/도로명 주소 (§1-A `bdMgtSn`과 조인) |
| `uptaeNm` | 업태명 (GNN 노드 분류) |

- 보조 검증: **국세청 사업자등록상태조회**(data.go.kr `15081808`, 기존 키 공용) — 휴폐업 여부 크로스체크.

### 8-C. 공정위 가맹사업 정보공개서 — Posting 창업비용 (기존 `DATA_GO_KR_SERVICE_KEY` 공용)
- 신청: data.go.kr에서 "공정거래위원회 가맹정보" 검색 → 활용신청(자동승인). 원자료: [franchise.ftc.go.kr](https://franchise.ftc.go.kr).
- 제공: 브랜드별 **가맹금·보증금·인테리어 비용·기준면적, 가맹점 평균 매출** → `posting.py`의 전략별(고급화/가성비/기능중심) 초기 투자비·객단가 가정을 실데이터로 치환하는 소스. 더미 상수의 `TODO` 해소 지점.

### 8-D. LLM `LLM_API_KEY` — Program 콘텐츠 생성 (backend, 유일한 유료 키)
- 권장: **Anthropic Claude** — [console.anthropic.com](https://console.anthropic.com) 가입 → API Keys 발급 → `apps/backend/.env`의 `LLM_API_KEY`. ([config.py](../apps/backend/app/core/config.py) `llm_api_key` 이미 존재)
- 모델: 품질 우선 `claude-sonnet-5`, 대량·저비용 생성 `claude-haiku-4-5-20251001`. **vision 내장**이라 상가 이미지 분석(Program의 이미지 정보 활용)에 별도 Vision API가 불필요.
- `pip install anthropic langchain-anthropic` (requirements.txt에 추가). feature-program.md의 OpenAI/Gemini도 래퍼(`services/llm.py`)만 바꾸면 호환되도록 작성.

### 8-E. 카카오 로컬 `KAKAO_REST_API_KEY` — 장소·카테고리 크로스체크
1. [developers.kakao.com](https://developers.kakao.com) → 애플리케이션 추가 → **REST API 키** 복사(즉시발급, 무료 쿼터).
2. 호출: `GET https://dapi.kakao.com/v2/local/search/keyword.json?query=…&x=…&y=…&radius=…` — 헤더 `Authorization: KakaoAK {KEY}`.
- 용도: §1-A 상가정보의 폐업 반영 지연을 보완하는 **현존 점포 크로스체크** + 카테고리·장소URL(리뷰 크롤링 시드).

### 8-F. 인스타그램·구글 — 보류/선택
- **인스타그램 Graph API**: 해시태그 검색에 비즈니스 계정 + 앱 검수 필요, 주 30개 해시태그 제한 → PoC 단계에서는 보류하고 [data/crawlers](../data/README.md)의 Playwright 크롤러로 대체. `.env` 슬롯(`INSTAGRAM_ACCESS_TOKEN`)만 유지.
- **Google Places API**: 리뷰·평점·사진 확보 가능하나 유료 쿼터 관리 필요 → 네이버·카카오로 부족할 때만.

---

## 9. Gold 레이어 매핑 — 기능별 산출 테이블

| Gold 테이블 | 기능 | 조인 키 | 소스(§) |
|---|---|---|---|
| `gold/page_building_master` | Page | `bdMgtSn` | 1-A + 1-B + 6(폴리곤) + **6-B(용도지역·공시지가)** |
| `gold/platform_district_timeseries` | Platform(LSTM) | `TRDAR_CD` × 년분기 | 8-A + 2 + **1-C/4(부동산원 공실률·임대료 API)** + 8-B(폐업 집계) |
| `gold/platform_store_graph` | Platform(GNN) | `bizesId`(노드) | 1-A + 8-A(업종·매출) + 리뷰 크롤링 |
| `gold/posting_cost_benefit` | Posting | 업종코드 × 전략 | 8-C + 8-A(추정매출·소득소비) + **1-C/4(임대료·수익률)** + **6-B(허용업종·공시지가)** |
| `gold/program_content_context` | Program | `TRDAR_CD` / `bizesId` | 5-B(블로그·트렌드) + 8-E + 크롤링(리뷰·이미지) |

- 공통 조인 축: **건물(`bdMgtSn`) ↔ 점포(`bizesId`) ↔ 상권(`TRDAR_CD`) ↔ 행정동(`adongCd`)**. Silver 단계에서 이 4개 키를 모든 테이블에 부여하는 것이 B단계 정제의 핵심 작업.
