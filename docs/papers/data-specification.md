# PlaceOS 논문용 데이터 명세표 — 저장소 대조본

목적: AI/MIS 선행연구의 데이터와 PlaceOS 데이터를 비교하기 전에, 현재 저장소에서 확인할 수
있는 데이터 계약과 한계를 고정한다. 외부 API 재호출, 원본 전수검사, 클라우드 접속은 하지
않았다. 따라서 **로컬에 없는 원본, 외부 제공 현황, 클라우드 보유 여부는 미확인**이다. 수치는
[근거 인덱스](evidence-index.md)에 등재된 것만 사용하며, 새 측정이 필요한 항목은 아래에서
`근거 인덱스 등재 필요`로 표시한다.

## 검증 범위와 판정어

- `확인`: 코드 또는 실제 산출물을 열어 계약을 대조했다.
- `코드만 확인`: 생성·수집 경로는 있으나 대응 원본을 로컬에서 열지 못했다.
- `미확인`: 저장소 자료만으로 판단할 수 없다. 추정으로 보완하지 않는다.
- 원천과 가공 결과를 구분한다. `Bronze`는 수집 원본, `Silver`는 공간 배정·속성 중간물,
  `Gold`는 연구·서빙용 파생물이다. 사용자 입력과 시드·계수는 어느 계층의 실측도 아니다.
- 관측 기간(자료가 나타내는 기간), 수집 시점(파일을 받은 날짜), 빌드 시점(`built_at`)은 서로
  바꾸어 쓰지 않는다.

## 참조 경로 확인 (`source_paths_checked`)

아래 경로는 모두 **존재를 확인**했다. 존재는 내용의 완전성이나 클라우드 업로드를 뜻하지 않는다.

| 자료 | 수집·입력 | 중간 가공 | Gold·서빙 | 판정 |
|---|---|---|---|---|
| 상권분석 | `data/collectors/seoul_trdar.py` | Silver 경로 없음 | `data/pipelines/build_gold.py` | 존재 · 원본 미보유 |
| R-ONE | `data/collectors/rone_rent.py`, `data/config/rone_districts.py` | Silver 경로 없음 | `data/pipelines/build_gold.py`, `data/gold/platform_posting_inputs.json` | 존재 · 원본 미보유 |
| 점포·건축물대장 | `data/collectors/building_vacancy.py` | `data/pipelines/build_building_attrs.py` | `data/pipelines/build_page_master.py` | 존재 · 거점 원본 미보유 |
| 서울 인허가 | `data/collectors/seoul_licensing.py` | 별도 Silver 없음 | `data/pipelines/build_page_master.py` | 존재 · 원본 미보유 |
| 집계구 생활인구 | `data/collectors/living_population_jipgyegu.py` | `data/silver/cell_jipgyegu.json`, `node_jipgyegu.json`, `unit_jipgyegu.json` | `data/pipelines/build_page_footfall_jipgyegu.py`, `build_unit_foot.py` | 코드·Silver 존재 · 원본 미보유 |
| 행정동 생활인구 | `data/collectors/living_population_hourly.py` | 생성 코드가 참조하는 `data/silver/hub_adong.json`은 로컬 누락 | `data/pipelines/build_page_footfall_hourly.py` | 일부 누락 |
| 공실 유닛 | Page Gold·Silver 입력 | `data/pipelines/build_vacant_units.py` | `data/gold/garosugil/vacant_units.json`, `apps/backend/app/services/vacant_inventory.py` | 존재 · 표본 스키마 확인 |
| Posting 입력 | R-ONE·상권분석 Gold, 사용자 계약 입력 | 별도 Silver 없음 | `data/pipelines/build_posting_inputs.py`, `data/gold/platform_posting_inputs.json` | 존재 · 코드 주석 충돌 있음 |
| Program 수요 | `data/gold/features/trdar_demand.parquet` | 별도 Silver 없음 | `data/pipelines/build_program_demand.py`, 거점별 `program_content_context.csv` | 존재 · Gold→Gold 파생 |
| Naver 자료 | `data/collectors/naver_datalab.py`, `data/collectors/naver_blog.py` | 별도 Silver 없음 | `data/pipelines/build_gold.py`, `build_program_trend.py` | 존재 · 원본 미보유 |
| 모델 산출물 | 학습 입력·코드는 본 표의 후속 검증 대상 | 해당 없음 | `platform_industry_recommend.json`, `platform_vacancy_forecast.json` | 산출물 존재 · 입력 계보 일부 미확인 |

**계층 충돌 기록.** 저장소의 데이터 규칙은 Bronze→Silver→Gold를 요구하지만, 상권분석,
R-ONE, 인허가, Naver 경로는 확인한 구현에서 별도 Silver 산출물 없이 Bronze를 Gold 빌더가
직접 읽는다. Program 수요는 기존 Gold parquet에서 Gold CSV를 만든다. 이는 현재 구현을
기술한 것이며, 계층 준수로 판정하지 않는다. 구조 변경은 이번 범위 밖이다.

## 데이터별 명세 (`provenance_preserved`)

| 자료 / P | 제공기관·획득 방식 | 관측 단위·연결 키 | 변수·단위·타깃 | 기간과 시점 | 출처 구분·연구 한계 |
|---|---|---|---|---|---|
| 상권분석 / Platform·Posting·Program | 서울 열린데이터광장 OpenAPI. 서비스별 호출 뒤 `data/bronze/platform13/{수집일}/seoul_trdar_*.json` 저장 | 상권×분기; `TRDAR_CD`, `STDR_YYQU_CD`를 `district_id`, `quarter`로 변환 | `selng_amt` 매출액, `flpop` 생활인구, 점포·개폐업 지표. 분류 피처·시계열·생성 컨텍스트 | 분기는 행의 관측기준; 폴더 날짜는 수집일. 실제 최소·최대 관측분기는 원본 미보유로 미확인 | 공공 통계·파생값. 추정매출은 점포 장부 매출이 아니며 거점은 복수 상권의 집계다. 수집기에는 서비스 필드 최종 확인 TODO와 종료된 소득소비 서비스 기록이 있다 |
| R-ONE / Platform·Page·Posting | 한국부동산원 R-ONE OpenAPI의 분기 통계표 다운로드 | R-ONE 분류지역×분기→거점×분기; `rone_cls`, `quarter`, `district_id`. 한 분류지역이 여러 거점에 공유될 수 있음 | `vac_small`, `vac_mid` 공실률, `rent_small` 임대료; 응답의 `unit`을 함께 저장 | `WRTTIME_DESC`를 분기로 변환; 수집일은 Bronze 폴더. 실제 범위는 원본 미보유로 미확인 | 공공 조사통계. 건물·호실 관측이 아니며 공유 매핑은 독립 관측을 만들지 않는다. `rent_unit`과 층 계수를 함께 보존해야 한다 |
| 점포·건축물대장 / Page·Posting | 소상공인 상가정보 및 건축HUB API | 점포, 건물, 대장 행, 상업층; `bdMgtSn`, 지번/PNU 동형 키, 좌표 PIP | 활성 점포, 수용량, 상업층·상업면적, 파생 공실률. Page의 측정 타깃은 건물 단위 점유 대리값 | 현재 스냅샷과 파일 수집일을 구분; 과거 패널 여부는 미확인 | 공공 행정 원천+PlaceOS 파생값. `floor_approx`, `expos_units`, `polygon_only`의 집계 배제·강등 의미를 유지한다. 현장 공실이나 임대 가능 매물 정답이 아니다 |
| 서울 인허가 / Page | 서울 열린데이터광장 인허가 API; 업종별 스테이지 후 거점 Bronze 병합 | 업소·영업상태; 주소·좌표를 건물 폴리곤에 PIP 귀속 | 영업 중 업소를 활성 점포 보강에 사용; 층은 주소에서 추출 가능한 경우에만 사용 | 수집 시점 스냅샷. 영업일 필드의 과거 이력을 보유한 패널인지는 미확인 | 공공 행정자료. 좌표·층 미상, 업종별 미지원·제외가 있으며 누락 없는 사업체 모집단으로 볼 수 없다 |
| 집계구 생활인구 / Page·Posting | 서울 생활인구 ZIP 파일 다운로드. OpenAPI가 아니라 월 ZIP의 일별 CSV를 추출 | 집계구×일×시간; 집계구 코드(`oa_code`)를 셀·노드·유닛에 공간 배정 | 생활인구와 시간대·주말 비율; 셀 유동 레이어와 유닛 `foot` 신호 | 원천 생산 종료 전 대표 기간이며 수집일과 다름. 최신 공급 여부는 공식 외부 확인 전 미확인 | 공공 집계통계+공간 파생값. 셀·유닛 직접 계수가 아니고 집계구가 셀보다 거칠 수 있다. 원천 종료와 해상도 한계를 유지한다 |
| 행정동 생활인구 / Page | 서울 생활인구 OpenAPI | 행정동×일×시간; 행정동 코드→거점 | 시간별 생활인구 프로필; 집계구 미충족 시 더 거친 출처 | 날짜별 Bronze가 관측일과 수집 캐시 역할을 함께 하므로 메타데이터 대조 필요 | 공공 집계통계. 집계구와 해상도가 다르며 응답의 `time_source` 폴백을 보존한다. `hub_adong.json`이 로컬에 없어 이 세션에서 재현 불가 |
| 공실 유닛 / Page·Posting | Page 건물 Gold와 건물 속성 Silver에서 파생 | 후보 유닛; `id`, `district_id`, 좌표, 건물·층 | `area`, `capacity`, `active`, `vacancy_rate`, `floor_basis`, `com_area_m2`; 연구 타깃은 실제 계약 매물이 아니라 파생 후보 | `built_at`은 빌드 시점. 원천 관측시점과 동일시하지 않음 | Gold 파생 인벤토리. 층별개요가 없으면 `assumed_1f`로 물러나며 면적·층 정밀도 한계를 유지한다 |
| 입점 비용 / Posting | R-ONE·상권분석 파생 입력 + 기업이 제공하는 권리금 계약 입력 | 거점·유닛·층; 유닛 식별자와 `district_id` | `rent`, `foot`, `area`, `prem`, 회수기간 시나리오. 임대료 단위와 층 계수를 함께 사용 | 집계 통계의 분기와 사용자가 값을 입력한 시점을 별도로 기록해야 하나 사용자 입력 시점 스키마는 미확인 | 공공 통계 파생+사용자 입력+계수. `prem` 미입력의 영(零)은 관측이 아니라 전제이며 `inputs_source`를 보존한다. 미래 수익·회수 성과 라벨이 없다 |
| Program 수요 / Program | 상권분석으로 만든 `trdar_demand.parquet`를 빌드 타임에 읽어 CSV에 병합 | 복수 상권→거점; `district_id`, CSV `kind/key/value` | 시간대·요일·연령·성별 구성비, 점포·개폐업 신호. 구성비는 생활인구 가중, 총량은 합 | 원천 분기·빌드 시점이 CSV 행에 직접 보존되는지는 미확인 | 공공 통계의 재파생값. 매출 결측을 영으로 만들지 않으며, 실제 광고 전환·캠페인 효과가 아니다 |
| 검색 트렌드·블로그 / Program | Naver DataLab POST API와 Blog Search API | 검색어 그룹×기간, 검색 결과→거점 `district_id`; Gold는 `kind/key/value` | 상대 검색비율·콘텐츠 키워드; 가드의 방향 컨텍스트 | 완료되지 않은 현재 기간은 제거. API 수집일과 검색 기간을 구분 | 민간 API. 검색 관심은 방문·매출이 아니고 블로그 결과는 점포 귀속 리뷰가 아니다. 공간 키가 거점뿐이어서 감성의 거점 내 정보량 기각을 유지한다 |

### 확인된 구현 충돌

- `data/pipelines/build_vacant_units.py`의 상단 설명은 `prem`을 거점 중앙값 기반 시드로 넣는다고
  적지만, 현재 서빙 계약인 `apps/backend/app/services/vacant_inventory.py`는 사용자 입력이
  없을 때 영(零)을 **전제**로 두고 `inputs_source["prem"]`으로 `absent`/`contract`를 구분한다.
  전자를 현재 출처 계약으로 인용하지 않는다.
- `data/pipelines/build_posting_inputs.py` 상단 표는 `area`와 `prem`을 시드 유지라고 적어 현재
  유닛 Gold의 면적 파생 및 권리금 입력 계약과 충돌한다. 파일이 실제로 만드는 것은 R-ONE
  임대료·상권 유동 입력이며, 주석의 시드 설명은 역사적 기록으로만 취급한다.
- `data/pipelines/build_gold.py`에는 비용 컬럼과 일부 필드명이 TODO인 초기 PoC 경로가 남아
  있다. 실제 Gold가 존재한다는 이유로 TODO 항목이 구현되었다고 간주하지 않는다.

## 실제 산출물 스키마 대조 (`schema_checked`)

| 파일 | 실제로 확인한 스키마 | 확인하지 못한 범위 |
|---|---|---|
| `data/gold/platform_industry_recommend.json` | 최상위 `model`, `metrics`, `districts` | 학습 입력 행 스키마, 라벨 생성 계보, 거점별 결측은 미확인 |
| `data/gold/platform_vacancy_forecast.json` | `model`, `target`, `trained_at`, `metrics`, `params`, `holdout`, `forecasts` | `target`의 원천 열·대리변수 정의는 학습 코드와 추가 대조 필요; 성능 수치는 근거 인덱스 등재 전 사용 불가 |
| `data/gold/platform_posting_inputs.json` | `source`, `quarter`, `built_at`, `rent_unit`, `floor_factor`, `note`, `districts`, `seoul` | 각 거점의 결측·공유 매핑 전수검사는 미실시 |
| `data/gold/garosugil/vacant_units.json` | 최상위 `source`, `built_at`, `note`, `units`; 유닛에 식별자·좌표·면적·층, `floor_mix`, `vac_floor_mix`, 점유층, 수용량·활성·공실률·상업면적 필드 | 한 거점의 표본 구조만 확인. 전체 모집단의 동일 스키마·결측률은 근거 인덱스 등재 필요 |
| `data/gold/garosugil/program_content_context.csv` | 헤더 `kind,key,value`; 실제 행 존재 확인 | 원천별 관측기간·최신성, 모든 거점의 kind 구성은 미확인 |
| 집계구 Silver 세 파일 | 파일 존재 확인 | 개인정보·용량 노출을 피하기 위해 본 작업에서는 내용 전수검사를 하지 않음; 키·결측 전수 수치는 근거 인덱스 등재 필요 |
| 로컬 Bronze | `.gitkeep` 외 대응 원본 없음 | 원본 행 스키마·관측범위·수집일·중복·결측 모두 미확인 |

## P별 연구 가능 범위와 검증 불가 주장 (`limitations_retained`)

| P | 현재 데이터로 가능한 연구 질문 | 추가 데이터 없이는 검증할 수 없는 주장 |
|---|---|---|
| Platform (Place) | 공간·수요 피처가 업종 분류·추천의 기준선 대비 성능과 희소 업종 식별에 어떤 차이를 만드는가? 공간 해상도 승격이 정보량을 실제로 늘리는가? | 추천이 창업 성공, 생존, 매출 증가를 유발한다는 인과 주장; 현재와 다른 모집단으로의 일반화; 실제 선택자의 효용 향상 |
| Page (Product) | 공공 행정자료 결합으로 건물 단위 점유 대리값을 어떻게 구성하며, 공간 귀속·배제 규칙·R-ONE 앵커가 측정 타당성에 어떤 제약을 주는가? | 현장 공실 정답과의 정확도, 실제 임대 가능 호실·면적·층의 완전성, 격자값이 해당 셀 직접 관측이라는 주장 |
| Posting (Price) | 집계 임대료, 파생 면적·유동, 사용자 권리금 입력을 분리한 시나리오에서 가정 변화에 따른 ROI 민감도와 식별 한계는 무엇인가? | 공개 데이터만으로 호실별 계약가격·권리금·층별 매출을 추정할 수 있다는 주장; 회수기간 예측의 실현 정확도나 가격의 인과효과 |
| Program (Promotion) | 이질적 컨텍스트의 출처를 보존한 생성 가드가 사실성 오류를 어떻게 탐지하도록 설계되는가? 결측 컨텍스트에서 조용히 통과하는 실패를 어떻게 평가할 것인가? | 정량적 마케팅 효과, 클릭·구매·방문 증가, 가드의 정확도·재현율. 현재 정량 평가는 없으므로 실증 성능 주장을 할 수 없다 |

이 질문들은 문헌 검색의 비교 축일 뿐 연구 방향이나 뼈대 논문을 확정하지 않는다. 모집단이 다른
서빙본과 과거 실험군의 수치를 한 표에서 성능 변화로 비교하지 않는다.

## 클라우드·재현 인계와 다음 검색 전 해결 항목

### 클라우드에서 누락 또는 미확인인 자료

- 로컬 Bronze에는 대응 원본이 없고, Git 추적 자료도 `.gitkeep`뿐이다. 따라서 상권분석,
  R-ONE, 건축물대장·점포, 인허가, 생활인구, Naver 원본은 **클라우드 보유 미확인**이다.
- `data/silver/hub_adong.json`은 로컬에서 누락되어 행정동 생활인구 경로를 재현할 수 없다.
- 집계구 Silver와 주요 Gold는 로컬에 있으나, 클라우드의 브랜치·업로드 상태와 파일 해시는
  이 세션에서 확인하지 못했다. 로컬 존재를 클라우드 존재로 바꾸어 쓰지 않는다.
- 원천 재배포 조건, Naver API 결과의 저장·공유 조건, 출판사 원문 접근권은 미확인이다.

### 문헌 검색 전에 해결할 항목

1. 보존 가능한 원본에 대해 관측기간·수집일·스키마·중복·결측을 검사하고, 필요한 수치는 먼저
   근거 인덱스에 재현 명령과 함께 등재한다.
2. 모델 산출물의 `target`, 라벨 생성, 입력 피처, 시간·공간 분할을 학습 코드까지 역추적한다.
3. 공실 파생값과 R-ONE 앵커의 비교 지표, Posting 민감도 결과, Program 평가 설계를 마련하되
   인덱스 등재 전에는 논문 수치로 쓰지 않는다.
4. Bronze→Gold 직접 경로와 Gold→Gold 경로를 연구 재현 패키지에서 어떻게 버전 고정할지
   결정한다. 이번 문서에서는 구현을 바꾸지 않는다.
5. 각 후보 논문마다 관측 단위, 모집단, 시간 주기, 타깃 정의, 변수 단위, 공간 조인, 분할,
   원천 접근 가능성을 이 명세와 대조한다. Q1 여부·원문·DOI는 실제 검색 뒤에만 기록한다.
