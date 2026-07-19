---
description: "신규 상권 1곳을 기존 13거점과 동일 구조로 플랫폼에 추가 (seed + TRDAR 매핑 + 실신호 수집)"
argument-hint: "<상권명> <자치구> [대체 상권/역 힌트]"
---

# 신규 상권 추가 커맨드 (13거점 → 확장)

너는 지금 SpaceOS의 **상권 확장** 작업을 수행한다. `CLAUDE.md` 규칙을 따른다.
(한국어·데이터기반·추측 최소화·더미엔 `# TODO: 실제 연동` 주석·기술용어 영문 병기)

## 이번 대상 상권

$ARGUMENTS
→ 첫 토큰 = 상권명, 둘째 토큰 = 자치구. 셋째부터는 TRDAR 미존재 시 대체할 역·골목 힌트(선택).
인수가 상권명·자치구 2개 미만이면 **즉시 질문**하고 시작하지 마라.

## 먼저 읽기 (컨텍스트 로딩)

작업 전 반드시 읽어라 — 신규 항목의 **템플릿·스키마·매핑 규약**이 여기 있다.

```
apps/backend/app/data/seoul_pages.py     # DISTRICTS — 사이트에 보이는 seed (garosugil·seongsu 항목이 템플릿)
data/config/platform_districts.py        # DISTRICT_TRDAR — 상권 → TRDAR_CD 매핑 규약
data/collectors/seoul_trdar.py           # 매출·점포·개폐업 시계열 수집기
data/pipelines/refresh_platform.py       # Gold 재빌드 + LSTM forecast 배치 (재학습은 여기서만)
```

## 절대 규칙 (파괴 금지)

- 기존 gold 산출물(`data/gold/garosugil` PoC·`data/gold/platform13`·`platform_vacancy_forecast.json`)을
  **덮어쓰지 말 것.** 신규 상권은 항상 **새 id·새 줄·새 키**로만 추가한다.
- **LSTM forecast 재학습은 이 커맨드에서 돌리지 않는다.** 여러 상권을 모아 리드가 배치로 1회 실행
  (`python -m data.pipelines.refresh_platform --skip-collect`). 여기서는 seed + 수집 + 검증까지.

---

## STEP 1 — TRDAR 상권코드 확보

`data/bronze/platform13` 의 **TbgisTrdarRelm(상권영역 마스터)** 에서 대상 상권명 관련
`TRDAR_CD_NM` 을 검색해 해당 `TRDAR_CD` 목록을 뽑는다.

- 발달상권·관광특구·핵심 골목상권 위주 채택. 동명이지만 성격이 다른 상권(주거 골목 등)은 제외.
- 대상 상권에 TRDAR 상권이 **없으면** 인수의 대체 힌트(인접 역·핵심 골목)로 매핑하고, **대체 근거를 주석**으로 남긴다.
  (전례: hannam 의 '용리단길' → 한강진역·한남오거리 대체)

## STEP 2 — config 매핑 등록

`data/config/platform_districts.py` 의 `DISTRICT_TRDAR` 에 한 줄 추가:

```python
"{district-id}": ["<TRDAR_CD>", ...],   # <상권명> · <대표 역/골목>
```

- `district-id` = 영문 소문자-하이픈. **STEP 3의 seoul_pages.py 신규 id 와 반드시 동일.**

## STEP 3 — 실데이터 수집 (이 상권만)

`data/collectors` 로 대상 상권 신호를 Bronze 수집한다(기존 분이 최신이면 재사용).

- `seoul_trdar` — 추정매출·점포수·개업률·폐업률 분기 시계열
- `kakao_local` — 점포 구성(업종 분포)
- `naver_blog` — 리뷰·언급 키워드
- R-ONE 키(`REB_RONE_API_KEY`) 동작 시 공실률·임대료 조인, 아니면 `# TODO`.

## STEP 4 — 상권 seed 작성 ★핵심 산출물 (사이트에 보이는 부분)

`apps/backend/app/data/seoul_pages.py` 의 `DISTRICTS` 에 **신규 항목 1개**를 추가한다.
기존 `garosugil`·`seongsu` 항목을 **템플릿**으로, STEP 3에서 수집한 실신호(매출 추이·리뷰
키워드·점포 구성)에 **근거해** 아래를 채운다.

- `zones` **6개** — 감성구역(핫플/노후 혼합, 상승/하락 신호)
- `units` **5개** — 공실유닛(층·업종·임대료·페르소나·추천)
- `events` **3개** — 행사(Humanistic Authority 균형·공생·공감 반영)
- `center`·`poi`·`grid`·`insta` — 네이버 지도 기준 좌표 정합

> 프록시(추정)로 채운 수치에는 **반드시 근거/출처 주석 + 실측 교체 `# TODO`**.
> 프론트(`apps/frontend`)가 이 항목을 문제없이 렌더하는지 확인.

## STEP 5 — PoC 함정 체크리스트 적용 (신규 거점 재발 방지)

가로수길 PoC exit에서 검증된 5항을 신규 상권에도 적용한다.

1. 점포 수집 반경 `STORES_RADIUS_M=600` (폴리곤 ~550m보다 넓게 — 경계 건물 empty 방지)
2. PIP 폴백(`build_page_master`)
3. 층별개요 분모 = 상업 층만(`floor_ouln`)
4. 분자 업종 필터(과학·기술/부동산/시설관리·임대 제외 — 분모와 도메인 정합)
5. 인허가 좌표계 EPSG:2097 + 동서 -257m 자가 보정

## STEP 6 — 검증

`/verify` 절차로 확인:

```
cd apps/backend && pytest          # 라우터·seed 로드 통과
cd apps/frontend && npm run build  # 타입체크 통과
```

---

## 완료 보고 (반드시)

- 추가한 상권 `id`
- 채택 `TRDAR_CD` 목록 (또는 대체 매핑 + 근거)
- 변경 파일 목록
- 수집된 실신호 요약 + 프록시로 남긴 항목(TODO)
- 검증 결과(pytest / build)

> 마지막에 반드시 안내: **forecast 재학습은 아직 미실행 — 리드 배치(refresh_platform)에서 반영됨.**
> 커밋은 **브랜치 + PR**로(여러 팀원이 같은 두 파일을 편집 → main 직접 푸시 금지).

## 호출 예시

```
/district-add 연희동 서대문구
/district-add 망원동 마포구 망원시장,망리단길
/district-add 삼청동 종로구 삼청동길,북촌
```
