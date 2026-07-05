# SpaceOS 데이터 레이어 규칙 (Bronze / Silver / Gold)

모든 데이터는 3계층 폴더로만 이동한다. 원본을 절대 덮어쓰지 않는다.

```
data/
├── bronze/   원본 그대로 (JSON·CSV·HTML). 수집일자/상권별 하위폴더.
│             예) bronze/seongsu/2026-05-30/naver_reviews.json
├── silver/   정제(결측·중복 제거, 주소→좌표 정규화). Parquet 권장.
│             예) silver/seongsu/stores.parquet
├── gold/     분석·서비스용 피처/집계 테이블 (PostgreSQL/PostGIS 적재 전 단계).
│             예) gold/platform_profile.parquet, gold/vacancy_features.parquet
└── crawlers/ 수집 스크립트 (Selenium/Playwright/BeautifulSoup)
```

## 데이터 출처 → 저장 매핑
| 데이터 | 출처 | 수집방법 | 저장(Bronze) |
|--------|------|---------|-------------|
| 리뷰/별점/사진 | 네이버 지도·구글맵·인스타 | Selenium/Playwright | bronze/{상권}/{날짜}/reviews.json |
| 공실/상가 | 공공데이터포털, 소진공 | REST API | bronze/{상권}/{날짜}/stores.json |
| 임대 매물 | 네이버부동산 등 | Requests/Selenium | bronze/{상권}/{날짜}/listings.json |
| 개·폐업 이력 | 국세청·지방행정인허가 | 공공 API | bronze/{상권}/{날짜}/biz_history.csv |
| 주소→좌표 | 네이버 Geocoding | naver_geo.geocode() | silver/{상권}/stores.parquet |

## B단계 수집기 + Gold 빌더 (PPPP 전체 — docs/api-keys-and-specs.md §8~9)

거점(가로수길) 상수는 `config/garosugil.py`, Bronze 저장 규칙은 `collectors/common.py`가 강제한다.

```bash
py -m data.collectors.seoul_trdar    # [Platform] 상권분석 분기 시계열 (SEOUL_OPENAPI_KEY)
py -m data.collectors.localdata      # [Platform] 개·폐업 인허가 이력 (LOCALDATA_API_KEY)
py -m data.collectors.kakao_local    # [Program/Posting] 현존 점포·카테고리 (KAKAO_REST_API_KEY)
py -m data.collectors.naver_blog     # [Program] 블로그 리뷰 + 데이터랩 트렌드 (NAVER_CLIENT_ID/SECRET)
py -m data.pipelines.build_gold      # Bronze → Gold 4테이블 (platform_district_timeseries 등)
```

키가 없는 수집기는 건너뛰고, Bronze 가 없는 Gold 테이블은 안내만 출력한다(부분 실행 안전).

## 공유 규칙
- 원시 데이터(개인정보 포함 가능)는 git 에 올리지 않는다(.gitignore). 비식별화 후 gold 산출물만 공유.
- 분석 결과물(리포트·대시보드 캡처)은 docs/ 또는 외부(Notion/Drive)로 공유.
