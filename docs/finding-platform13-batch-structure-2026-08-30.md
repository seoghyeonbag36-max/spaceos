# `platform13` 배치 구조 — 막는 것은 소스가 아니라 거점 목록이다 (2026-08-30)

## 0. 판정

경기 Platform 트랙이 막힌 이유를 "배치 이름이 `platform13` 로 박혀 있다"로 적어 두었는데
(`city-expand` §4-B), **틀렸다.** 실제로 막는 것은 배치 이름이 아니라 **거점 목록이
세 곳에 흩어져 있고 그중 둘이 서울 54곳에 고정**돼 있는 것이다.

그리고 세 산출물 중 **둘은 서울 전용 소스를 아예 쓰지 않는다.**

## 1. 산출물별 소스 의존 — 실측

| Gold 산출물 | 소스 | 서울 전용? | 경기 가능 여부 |
|---|---|---|---|
| `platform_district_timeseries` | 서울 상권분석(TRDAR) `stor·selng·flpop·ix` + R-ONE | **예** | ❌ 대체 소스 필요 |
| `platform_store_graph_{nodes,edges}` | **카카오 로컬** | 아니오 | ✅ 목록만 넓히면 된다 |
| `program_content_context` | **네이버 블로그 + 카카오 로컬** | 아니오 | ✅ 목록만 넓히면 된다 |

카카오·네이버 블로그는 전국 서비스다(`plan-gyeonggi-expansion` §2-A 가 이미 그렇게 적었다).
즉 **Platform·Program 산출물 3개 중 2개는 오늘 당장 경기에서 만들 수 있다.**

## 2. 진짜 병목 — 거점 목록이 셋이다

| 레지스트리 | 거점 수 | 쓰는 곳 | 형식 |
|---|---|---|---|
| `page_hubs.ALL_HUBS` | **74** (서울 54 + 경기 20) | Page 수집 전부 | `PageHub` (slug·name·cx·cy·radius·city·caveat) |
| `platform_places.DISTRICT_PLACES` | 54 | **Platform·Program 수집** | `(lat, lng, radius, name)` 튜플 |
| `platform_districts.DISTRICT_TRDAR` | 54 | 서울 상권분석 매핑 | `{거점: [상권코드…]}` |

경기 20거점은 **`DISTRICT_PLACES` 에 하나도 없다.** 그래서 `kakao_local --platform13` 과
`naver_blog --platform13` 이 경기를 안 돈다. 소스가 없어서가 아니라 **목록에 없어서**다.

`ALL_HUBS` 는 `DISTRICT_PLACES` 를 **완전히 포함한다**(Page 목록에 없는 Platform 거점 0곳).
즉 상위집합이 이미 있고, 좌표·반경·도시·예외까지 갖고 있다.

> 이 저장소에서 **여섯 번째 같은 양식**이다 — 재료가 이미 안에 있는데 배선이 없어
> "못 한다"로 적혀 있었다(feature-platform §0-J 인벤토리 · §0-L 집계구 ·
> posting §0-M 층 · §0-N 서울 기준점 · §0-O R-ONE 서울 행).

## 3. 갈래 — 무엇을 정해야 하나

### 3-A. 거점 목록 통합 (권고)

`DISTRICT_PLACES` 를 지우고 Platform 수집기가 `ALL_HUBS` 를 돌게 한다.
필요한 변환은 `(cy, cx, radius_m, name)` 한 줄이라 형식 차이는 장벽이 아니다.

- **얻는 것**: 거점을 한 곳에만 등록하면 Page·Platform·Program 이 다 따라온다.
  지금은 새 거점마다 두 곳에 적어야 하고, 한쪽을 잊으면 **조용히 빠진다**(경기 20곳이 그랬다).
- **치르는 것**: 서울 54거점의 Platform Bronze 를 다시 받아야 하는가? — **아니다.**
  수집기는 이미 받은 것을 건너뛰고, `DISTRICT_PLACES` 의 반경이 `PageHub.radius_m` 과
  다른 거점이 있으면 그 거점만 값이 달라진다. **반경 차이를 먼저 재야 한다**(§4).

### 3-B. 배치 이름

`platform13` 은 실제로는 54거점이라 이름이 이미 어긋나 있다. 그러나 이름을 바꾸면
`bronze/platform13/` · `gold/platform13/` 경로와 그것을 읽는 모든 소비층이 따라 바뀐다.
**이름은 그대로 두고 주석으로 밝히는 쪽이 싸다** — 경로는 식별자일 뿐이고,
도시 구분은 이미 `district_id` 와 `PageHub.city` 가 한다.

### 3-C. 시계열(TRDAR)은 별개 문제다

`platform_district_timeseries` 는 서울 상권분석이 필수다. 경기 대체재
(경기도 발달·골목상권 추정매출 · 경기데이터드림 생활이동)는 **서비스명·스키마가
아직 미확인**이다(`GENRESTRT` 를 찾을 때처럼 브라우저로 찾아야 한다).

**그래서 순서가 갈린다**: 3-A 를 먼저 하면 경기 거점의 **GNN 노드·엣지와 Program
콘텐츠 컨텍스트**가 서고, LSTM 시계열만 남는다. 시계열을 기다릴 이유가 없다.

## 4. 반경 차이 — 쟀다 (2026-08-30)

`DISTRICT_PLACES` 와 `PageHub.radius_m` 이 **9/54거점에서 다르다.**

| 거점 | Platform | Page |
|---|---:|---:|
| apgujeong-rodeo · yeonnam · seochon · myeongdong · euljiro · seoulsup · itaewon 등 | 300~400m | 500m |

전부 **Platform 쪽이 좁다**(Page 가 나중에 정해진 값이라 그렇다). 그대로 통합하면 이
9거점의 카카오 수집 반경이 넓어져 **노드가 늘고 GNN 게이트 근거값(40,388노드)이 바뀐다.**

→ **통합하되 반경은 거점별로 보존한다.** `PageHub` 에 Platform 전용 반경 필드를 더하거나
(`platform_radius_m`, 기본값 `radius_m`), 통합 어댑터가 `DISTRICT_PLACES` 의 값을
우선 쓰게 한다. **어느 쪽이든 서울 54거점의 수집 범위는 한 미터도 바뀌지 않아야 한다** —
바뀌면 GNN 재학습 없이는 게이트를 인용할 수 없게 된다.

경기 20거점은 종전 값이 없으므로 `PageHub.radius_m` 을 그대로 쓴다.

## 5. 권고

1. §4 반경 차이 측정 (쿼터 0 · 코드 안 고침)
2. 차이가 없거나 작으면 **3-A 통합** — Platform 수집기가 `ALL_HUBS` 를 돈다
3. 경기 거점 카카오·블로그 수집 → GNN 노드·엣지 + `program_content_context` 생성
4. 시계열(TRDAR 대체)은 **별도 과제**로 분리 — 경기 포털 서비스명 탐색이 선행
