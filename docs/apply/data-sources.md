# C7 — 데이터 출처·라이선스 표

신청서의 **데이터 확보 경로**를 대는 자리다. 공간정보 경진대회에서는 이 표가 배점 1위
항목(데이터 확보 용이성)에 직접 대응하고, 나머지 대회에서도 "무슨 데이터를 어떻게
확보했나"의 답이 된다. 원고에서 이 표를 인용한다.

> **핵심 주장**: 서빙 66거점(건축물대장 기반)의 재료가 **전량 공개된 공공 API·공공
> 데이터포털**에서 나온다. 수집기가 저장소에 있고 실행 명령이 문서화돼 있어, 제3자가
> 같은 경로로 같은 자료를 재확보할 수 있다.

---

## 국가공간정보 — 브이월드

| 항목 | 내용 |
|---|---|
| 데이터명 | GIS건물통합정보 — 건물 footprint 폴리곤 |
| 출처기관 | 국토교통부 공간정보 오픈플랫폼(브이월드) |
| 접근 | WFS `getBldgisSpceWFS` · 레이어 `dt_d010` · `VWORLD_API_KEY` 즉시발급 |
| 받는 것 | PNU · 층수 · 연면적 · 높이 · 용도코드 + 좌표 |
| 실호출 검증 | 2026-07-08 완료 |
| 수집기 | `data/collectors/vworld_bldg.py` |
| 쓰이는 곳 | `data/pipelines/build_page_master.py` (서빙) · 거점 온보딩 체인 |
| 갱신주기 | 확인필요(주기) |
| 이용조건 | 확인필요(라이선스) |

<!-- 확인필요(전략): 이 표를 만들며 드러난 사실 — SpaceOS 는 브이월드를 **쓰고 있다.**
     그것도 주변부가 아니라 건물 폴리곤의 원천이고, 서빙 파이프라인과 거점 온보딩
     체인에 들어 있다. 공간정보 경진대회 신청서를 "브이월드를 쓰지 않는다"는 전제로
     쓰면 안 된다 — 반대로 이것이 그 대회에서 가장 강한 카드다. -->

## 건축물대장 계열 — Page 트랙의 분모·분자

| 데이터명 | 출처기관 | 접근 | 수집기 | 갱신주기 | 이용조건 |
|---|---|---|---|---|---|
| 건축물대장(전유부·층별개요) | 국토교통부 건축HUB | `apis.data.go.kr/1613000/BldRgstHubService` · 일일 쿼터 | `data/collectors/building_vacancy.py` · `floor_capacity.py` | 확인필요(주기) | 확인필요 |
| 상가(상권)정보 | 소상공인시장진흥공단 | `apis.data.go.kr/B553077/api/open/sdsc2` | `data/collectors/building_vacancy.py` | 확인필요(주기) | 확인필요 |
| 지방행정 인허가데이터 | 행정안전부 LOCALDATA | `localdata.go.kr/platform/rest/TO0/openDataApi` | `data/collectors/localdata.py` | 수시(확인필요) | 확인필요 |
| 서울 인허가 | 서울 열린데이터광장 | `openapi.seoul.go.kr` | `data/collectors/seoul_licensing.py` | 확인필요(주기) | 확인필요 |

> 건축HUB 는 **일일 쿼터**가 있어 수집을 하루 단위로 끊어 돌린다. 프리플라이트 절차가
> `scripts/quota_preflight.py` 로 문서화돼 있다 — 확보 경로가 절차로 서 있다는 근거다.

## 임대·상권 시계열 — Platform 트랙

| 데이터명 | 출처기관 | 접근 | 수집기 | 갱신주기 | 이용조건 |
|---|---|---|---|---|---|
| 상업용부동산 임대동향(공실률·임대료) | 한국부동산원 R-ONE | `reb.or.kr/r-one/openapi/SttsApiTblData.do` | `data/collectors/rone_rent.py` | **분기** | 확인필요 |
| 서울시 상권분석서비스(TRDAR) | 서울 열린데이터광장 | `openapi.seoul.go.kr` | `data/collectors/seoul_trdar.py` | **분기** | 확인필요 |

> R-ONE 은 앵커(대조 기준)로 쓴다. 거점↔R-ONE 상권 매핑은 `data/config/rone_districts.py`
> 한 곳이 단일 출처다. 표본 개편(2024Q3)이 있어 시계열을 이을 때 주의가 필요하다.

## 유동·수요 신호 — Page/Posting/Program

| 데이터명 | 출처기관 | 접근 | 수집기 | 갱신주기 | 이용조건 |
|---|---|---|---|---|---|
| 집계구 단위 생활인구 | 서울 열린데이터광장 | `datafile.seoul.go.kr` 대용량 파일 | `data/collectors/living_population_jipgyegu.py` | 확인필요(주기) | 확인필요 |
| 생활이동 | 서울 열린데이터광장 | `openapi.seoul.go.kr` | `data/collectors/living_migration.py` | 확인필요(주기) | 확인필요 |
| 서울시 문화행사 | 서울 열린데이터광장 | `openapi.seoul.go.kr` | `data/collectors/seoul_events.py` | 확인필요(주기) | 확인필요 |

## 민간 API — 지도·검색

| 데이터명 | 출처기관 | 용도 | 수집기 / 모듈 | 이용조건 |
|---|---|---|---|---|
| 지도 · 거리뷰 파노라마 | 네이버 클라우드 플랫폼 | 화면 베이스맵 | `apps/frontend/src/lib/naverMap.ts` | 확인필요(상용 조건) |
| 검색어 트렌드(데이터랩) | 네이버 | Program 트렌드 라벨 | `data/collectors/naver_datalab.py` | 확인필요 |
| 블로그 검색 | 네이버 | Program 콘텐츠 컨텍스트 | `data/collectors/naver_blog.py` | 확인필요 |
| 로컬(장소·카테고리) | 카카오 | 크로스체크 | `data/collectors/kakao_local.py` | 확인필요 |

> 민간 API 는 **크롤링이 아니라 공식 API**로만 받는다. 채널별 가능·불가 판정을 전수로
> 남겨 두었다(Program 트랙). 신청서에서 데이터 취득의 적법성을 묻는 자리에 이 사실을 쓴다.

---

## 이 표에서 아직 비어 있는 것

**`확인필요(라이선스)` 를 지어내지 않았다.** 각 포털의 이용조건(공공누리 유형·상업적
이용 가부·출처표시 의무)은 코드에서 읽을 수 없고, 포털 페이지에서 확인해야 한다.
정부 공모전 신청서에 **틀린 라이선스 표기를 넣는 것이 빈칸보다 나쁘다** — 제출 전에
각 포털에서 확인해 채운다. 갱신주기도 같다(R-ONE·TRDAR 분기만 코드로 확인됨).

이것이 이 저장소의 제1원칙(`AGENTS.md` §0)을 문서에 적용한 결과다 — 근거 없는 값을
채우지 않는다. 막힌 값을 만나면 채우지 않고 표시한다.

## 재확보 절차 (제3자 재현)

```bash
python scripts/check_api_keys.py        # 필요한 키가 무엇인지 목록으로 나온다
python scripts/quota_preflight.py       # 건축HUB 쿼터·잔여 확인
python scripts/chain_status.py --all    # 거점별 수집 진행 상태
```

키 발급처와 스펙은 `docs/api-keys-and-specs.md` · `docs/api-key-checklist.md` 에 있다.
