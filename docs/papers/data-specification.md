# SpaceOS 논문용 데이터 명세표 — 초기 점검본

목적: AI/MIS 선행연구의 데이터·방법을 SpaceOS에 적용할 수 있는지 판정한다. 아래 내용은 로컬 수집 코드·가공 코드와 일부 산출물 구조를 확인한 결과다. 외부 API 재호출, 전체 원본 전수 검증, 클라우드 업로드는 수행하지 않았다. 표본 수·성능 수치는 이 문서에서 새로 선언하지 않으며 [근거 인덱스](evidence-index.md)의 모집단 조건을 따른다.

## 작업 계약

- 수정 대상: 이 파일만. 제품 코드·원천 데이터·기존 논문 본문은 읽기 전용이다.
- 출처: 아래 저장소 파일. 공공 원천, 가공값, 민간 API, 사용자 입력, 시드·계수를 구분한다.
- 검증 조건: `source_paths_exist`(참조 파일 존재), `artifact_schema_checked`(명시한 표본 구조 대조), `limitations_retained`(한계·미확인 유지).
- 금지: 결측 임의 보완, 원문 미확인 문헌 확정, 추정값의 실측 표기, 모집단 혼합, 기각 결과 변경.

## 데이터와 연구 역할

| 자료 / 해당 P | 입력 소스·수집 방식 | 관측 단위·시간 / 연결 키 | 확인한 변수·용도 | 출처 성격·논문 적용 한계 | 구현 근거 |
|---|---|---|---|---|---|
| 상권분석 / Platform·Posting·Program | 서울 열린데이터광장 상권분석 OpenAPI | 상권·분기 → 거점·분기 / `TRDAR_CD`, `STDR_YYQU_CD` → `district_id`, `quarter` | `selng_amt`, `flpop`, 점포·개폐업 관련 지표; 수요 피처와 시계열 입력 | 공공 통계의 가공값. 추정매출은 개별 점포의 실제 장부 매출이 아니다. 상권과 SpaceOS 거점의 매핑 검증 필요 | [수집](../../data/collectors/seoul_trdar.py), [가공](../../data/pipelines/build_gold.py) |
| 임대동향 / Platform·Page·Posting | 한국부동산원 R-ONE OpenAPI | R-ONE 상권·분기 → 거점·분기 / `district_id`, `quarter` | `vac_small`, `vac_mid`, `rent_small`; 공실 앵커와 임대료 입력 | 공공 조사 통계. 공유 매핑으로 여러 거점이 같은 원천값을 가질 수 있다. 개별 유닛 계약 임대료로 취급하지 않는다 | [수집](../../data/collectors/rone_rent.py), [매핑](../../data/config/rone_districts.py) |
| 점포·건축물대장 / Page·Posting | 소상공인 상가정보와 건축HUB API | 점포·건물·대장 응답의 층/호 / 건물관리번호·지번·좌표 | 활성 점포, 수용량, 상업 면적; 공실 후보 구성 | 원천은 공공 행정자료지만 공실률은 결합·산출한 값이다. 현장 전수 조사나 임대 가능 매물 확정과 구별한다. 집계 제외 규칙을 보존한다 | [수집](../../data/collectors/building_vacancy.py), [Page 마스터](../../data/pipelines/build_page_master.py) |
| 서울 인허가 / Page | 서울 열린데이터광장 인허가 API | 업소·영업상태 / 좌표를 건물 폴리곤에 귀속 | 영업 중 업소로 활성 점포 누락 보강 | 공공 행정자료. 좌표·귀속 오류와 업종별 커버리지 확인 필요. 파일이 있다는 이유만으로 과거 상태 패널로 간주하지 않는다 | [수집](../../data/collectors/seoul_licensing.py) |
| 집계구 생활인구 / Page·Posting | 서울 생활인구 ZIP 안의 일별 CSV; API 방식과 구분 | 집계구·일·시간 / 집계구 코드 및 공간 배정 | 생활인구를 셀·유닛에 연결해 유동 신호 구성 | 공공 집계자료의 공간 가공값. 셀·유닛별 직접 계수값이 아니다. 수집기에는 원천 생산 종료 주석이 있으므로 최신 공급 여부는 외부 공식 확인 전 미확인 | [수집](../../data/collectors/living_population_jipgyegu.py), [셀 가공](../../data/pipelines/build_page_footfall_jipgyegu.py), [유닛 가공](../../data/pipelines/build_unit_foot.py) |
| 행정동 생활인구 / Page | 서울 생활인구 OpenAPI | 행정동·일·시간 / 행정동과 거점 연결 | 시간대 생활인구와 시간 프로필 | 집계구 자료와 해상도가 다르다. 폴백 여부와 응답 출처를 보존한다 | [수집](../../data/collectors/living_population_hourly.py), [가공](../../data/pipelines/build_page_footfall_hourly.py) |
| 공실 유닛 / Page·Posting | Page 산출물과 면적 자료에서 파생 | 후보 유닛 / `id`, 좌표, `floor` | `area`, `capacity`, `active`, `vacancy_rate`, `floor_basis`, `com_area_m2` | 공공 API 자체가 아니라 제품의 가공 인벤토리. 면적 입도와 층 귀속을 별도로 확인해야 한다 | [가공](../../data/pipelines/build_vacant_units.py), [서빙](../../apps/backend/app/services/vacant_inventory.py) |
| 입점 비용 입력 / Posting | R-ONE·생활인구 파생값과 기업 입력 | 거점·층·유닛 / 유닛 식별자와 거점 | `rent`, `foot`, `area`, `prem`; 비용·회수기간 시나리오 | 임대료의 층 계수는 실측 계약값이 아니다. 권리금 미입력 시 전제와 `inputs_source`를 유지한다. 회수기간은 미래 실현 성과가 아니다 | [임대 입력](../../data/pipelines/build_posting_inputs.py), [서빙](../../apps/backend/app/services/vacant_inventory.py) |
| 상권 수요 컨텍스트 / Program | 상권분석 피처에서 파생 | 상권에서 거점으로 집계 / `kind`, `key`, `value` | 시간대·요일·연령·성별 신호를 생성 입력에 사용 | 총량과 구성비의 집계 방식이 다르다. 수요 신호와 실제 광고 전환율을 동일시하지 않는다 | [가공](../../data/pipelines/build_program_demand.py) |
| 검색 트렌드·블로그 / Program | 네이버 DataLab 및 블로그 검색 API | 검색어 그룹·기간 또는 검색 결과 / 거점 매핑 | 트렌드 시계열·상권 콘텐츠 | 민간 API이며 공공데이터가 아니다. 검색 관심은 방문·매출이 아니고 블로그 검색 결과는 점포 리뷰 원문과 다르다. 감성 경로 기각을 유지한다 | [트렌드 수집](../../data/collectors/naver_datalab.py), [블로그 수집](../../data/collectors/naver_blog.py), [트렌드 가공](../../data/pipelines/build_program_trend.py) |

## 산출물 표본 구조 확인

아래는 파일을 실제로 열어 확인한 구조다. 전체 거점의 동일 스키마·결측률을 보증하지 않는다.

| 파일 | 확인한 구조 | 재현·사용 주의 |
|---|---|---|
| [업종추천](../../data/gold/platform_industry_recommend.json) | `model`, `metrics`, `districts` | 예측·평가 산출물이다. 실제 입점 성공 라벨로 쓰지 않는다 |
| [시계열 예측](../../data/gold/platform_vacancy_forecast.json) | `model`, `target`, `trained_at`, `metrics`, `params`, `holdout`, `forecasts` | `target` 정의를 학습 코드와 추가 대조한 뒤 연구 타깃 확정. 공실 대리지표를 실제 공실률이라고 서술하지 않는다 |
| [입점 입력](../../data/gold/platform_posting_inputs.json) | `source`, `quarter`, `built_at`, `rent_unit`, `floor_factor`, `note`, `districts`, `seoul` | 단위와 계수·가정을 함께 인용한다 |
| [가로수길 유닛](../../data/gold/garosugil/vacant_units.json) | `source`, `built_at`, `note`, `units`; 유닛의 면적·층·수용량·활성 점포·공실률 필드 | 가로수길 표본 구조 확인이며 전체 서빙 모집단 전수 결과가 아니다 |
| [가로수길 생성 컨텍스트](../../data/gold/garosugil/program_content_context.csv) | CSV 파일 존재; 가공 코드상 `kind/key/value` 계약 | JSON 파일로 가정하면 안 된다. 원천별 내용·최신성은 후속 전수 점검 대상 |

## 뼈대 논문 선정에 사용할 적합성 기준

| 트랙 | 찾을 데이터·태스크 | 그대로 적용하면 안 되는 경우 |
|---|---|---|
| Platform | 공간 점포 분류·추천, 지역 패널 시계열, 단순 빈도 기준선과의 비교 | 업종 분류 정확도를 창업 성공 확률로 바꾸는 연구 설계 |
| Page | 공공 행정자료 결합, 공간 귀속, 결측·커버리지 평가 | 현장 공실 정답이 필요한데 이를 공공자료 파생값으로 대체 |
| Posting | 집계 임대료와 개별 입력을 결합한 시나리오·민감도 분석 | 실제 비용·매출·회수 성과가 필요한 인과효과 연구 |
| Program | 공공 수요 신호를 조건으로 한 생성과 사실성 평가 | 광고 노출·클릭·구매 로그 없이 캠페인 효과를 입증 |

후보마다 관측 단위, 시간 주기, 타깃, 변수 단위, 공간 조인, 원천 접근 가능성, 평가 분할을 대조한다. Q1 여부와 원문은 아직 조사하지 않았으며 선정된 뼈대 논문은 없다.

## 남은 확인과 클라우드 인계

- 전체 원본의 수집 날짜·관측 기간·중복·결측·단위와 Bronze→Silver→Gold 연결을 전수 확인해야 한다. 현재 표는 코드 경로를 정리한 초기 명세다.
- 수집기 상단의 과거 거점 수와 미배선 주석은 최신 서빙 상태와 충돌할 수 있다. 주석만으로 현황을 확정하지 않는다.
- 과거 실험군과 현재 서빙본은 [근거 인덱스](evidence-index.md)의 조건별로 분리한다.
- 원고에 쓸 새 수치는 인덱스에 출처·재현 경로를 등재하기 전 사용하지 않는다.
- 원천 재배포 조건과 민간 API 자료의 저장·공유 범위는 미확인이다. 파일 업로드 대상 선정 시 확인한다.
- 사용자 제공 클라우드 점검 화면에서 `SpaceOS Papers`의 저장소 접근과 Crossref 접속 통과를 확인했다. 이 로컬 세션에서 클라우드에 직접 접속해 재검증한 결과는 아니다. 다른 출판사 원문 접근 가능 여부는 미확인이다.
- 같은 점검 화면에서 이 명세표의 클라우드 사본 누락과 `pypdf`, `docx` 모듈 미설치가 확인됐다. `docx`의 설치 패키지는 `python-docx`다. 로컬 커밋만으로 클라우드 사본이 갱신되지 않으므로 원격 브랜치 반영과 해당 브랜치 선택이 필요하다.
- 클라우드에서 쓸 자료의 Git 추적 여부·업로드 여부와 해시를 별도로 확인해야 한다. 로컬 파일 존재만으로 클라우드 접근 가능하다고 판단하지 않는다.
