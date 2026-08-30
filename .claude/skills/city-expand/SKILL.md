---
name: city-expand
description: 새 도시(서울 밖)로 스택을 확장하는 절차 — 어느 소스가 그대로 가고 어느 것이 서울 전용이라 교체되는지, Phase 0~6 통과 조건. 고양·파주 확장과 그 뒤 도시들.
---

# 도시 확장 — 복사가 아니라 도시 차원을 넣는다

기획 원본: `docs/plan-gyeonggi-expansion-2026-08-29.md`. 이 skill 은 그 판단을 실행 절차로 편 것이다.

**서울 스택의 절반만 그대로 간다.** Page 는 거의 그대로, Platform·Posting·Program 은 절반이다.

## 1. 소스 판정 — 이 표가 확장의 전부다

| 그대로 가는 것 (전국 서비스) | 쓰는 곳 |
|---|---|
| 소상공인 상가정보 · 건축HUB · V-World | Page 분자·분모·폴리곤 |
| R-ONE 임대동향 | Posting 임대료 · LSTM 피처 (**표본 수 확인 필수**) |
| 카카오 로컬 · 네이버 블로그/데이터랩 | Platform 업종·키워드 · Program 콘텐츠 |
| KOSIS · 공정위 · SGIS | 매출앵커·공간단위 |

| 서울 전용 — 교체해야 하는 넷 | 경기 대체재 |
|---|---|
| 서울 상권분석(TRDAR) 추정매출·유동 | 경기도 발달·골목상권 추정매출(data.go.kr 15106677) + 경기도시장상권진흥원 |
| 서울 생활인구 | 경기데이터드림 유입/유출 생활이동인구 |
| 서울 문화행사 | 시 단위 공공데이터 (고양·파주 미확인) |
| 서울 인허가 | **경기데이터드림 `GENRESTRT`** (`data/collectors/gg_licensing.py`) — LOCALDATA 는 폐쇄(실측), 표준데이터 파일 403, data.go.kr 미러는 LINK형 |

경기는 **포털이 3곳이라 키를 3종 뚫어야 한다** — 서울처럼 키 하나로 끝나지 않는다.

## 2. 구조적 제약 둘 — 여기서 거점 수가 정해진다

- **R-ONE 표본**: 경기 35상권 중 고양 2(`경기>고양시청`·`경기>탄현역`) · 파주 1(`경기>파주시청`).
  더 넣으려면 **공유 매핑 + 명시**다 — `inputs_source.rent` 를 `rone` 이 아니라
  `rone-shared` 로 가르고 화면에 "임대 앵커 공유" 배지를 단다. 합성값을 실측처럼 보이지
  않게 하는 원칙은 서울에서 이미 확립됐다.
- **계획상가 밀집**: 건물당 점포 수 >10 이면 우리 공실 분모가 대다수를 놓친다.
  일산 라페스타 37.4 는 그 문제의 정중앙이다 → `hub-onboard` §0.

## 3. 코드에서 도시가 하드코딩된 곳 (여기만 고친다)

| 위치 | 할 일 | 상태 |
|---|---|---|
| `apps/backend/app/data/cities.py` | 도시 레지스트리 — `gus` 로 소속 판정, `sgg_codes`(PNU 앞 5자리)로 산출물 검증 | ✅ 있음 |
| `data/config/page_hubs.py` `PageHub.city` | 거점 → 도시 | ✅ 있음 |
| `app/schemas/district.py` `city`/`city_name` | API 응답에 도시 축 | ✅ 있음 |
| `app/services/districts._summary` | `cities.of_gu()` 로 판정 (시드 54개를 안 건드린다) | ✅ 있음 |
| `data/pipelines/build_gold._is_offsite` | `home_terms` — 자기 도시 이름을 타지명으로 세지 않는다 | ✅ 있음 |
| `data/config/rone_districts.py` | 경기 **정확 3 · 공유 17** 매핑 | ✅ 있음 |
| `data/collectors/gg_licensing.py` | 경기 인허가 `GENRESTRT` — 시군 파라미터를 받는 하나 | ✅ 있음 |
| `data/collectors/gg_*.py` | 나머지 경기 소스 수집기 — **시군 파라미터를 받는 하나**로 | ⬜ |
| `data/bronze|gold/platform13/` | 배치 이름을 상수로 (서울은 `platform13` 유지, 신규는 `goyang`·`paju`) | ⬜ |

## 4. Phase 게이트 — 통과 조건을 먼저 적는다

| Phase | 하는 일 | 통과 조건 |
|---|---|---|
| 0 | 경기 포털 키 · 후보 지점 비율 프로브 | 키 200 응답 · 비율표. 인허가는 `openapi.gg.go.kr/GENRESTRT?KEY=…&SIGUN_NM=고양시` 1콜로 확인 |
| **1. Page 최소 성립 — ✅ 완료** | 거점 등록 → 수집 → 공실 → 지도 (`hub-onboard`) | **20거점 등록 · Tier1 Gold 7거점만 서빙 · 앵커 대조 완료** |
| 2 | 카카오·블로그·트렌드 → `program_content_context` | `/commercial-districts/{id}/platform` 200 · archetype 판정 |
| 3 | 경기 생활이동·추정매출 → `demand` | 시간대·연령·성별 6구간이 **서울과 같은 스키마**로 |
| 4 | R-ONE 매핑 + 공유 표기 → 3-Tier | 회수불가 비율 서울 대역(0.5~3%) 안 · `rone-shared` 배지 |
| 5 | 시 행사 소스 | 실데이터 or **빈 상태 명시**(시드로 채우지 않는다) |
| 6 | LSTM/GNN 에 경기 포함 여부 | **판단을 먼저 쓴다** — pooled 에 넣을지 도시별로 나눌지 |

## 5. 하지 않을 것

1. `archive/goyang-legacy/` 참조·부활 — 2026-07-18 에 버린 정적 프로토타입이다.
2. 서울 소스를 흉내 낸 합성값 — 없는 구간은 **비워 두고 그 사실을 화면에 싣는다**.
3. 도시마다 화면 복제(GoyangDashboard) — 거점 보드에 **도시 필터**를 더한다.
4. 도시마다 수집기 복제(`goyang_*.py`) — 시군 파라미터를 받는 하나면 된다.
5. R-ONE 표본 없는 거점에 임대료를 채워 넣기 — 공유 매핑은 쓰되 공유임을 밝힌다.

## 부록 — 실측으로 확정된 소스 (2026-08-30)

| 항목 | 값 |
|---|---|
| 인허가 | `https://openapi.gg.go.kr/GENRESTRT?KEY={키}&Type=json&SIGUN_NM=고양시` |
| 수집기 | `data/collectors/gg_licensing.py` |
| 필드 | 사업장명 · 인허가일자 · 영업상태 · 폐업일자 · 지번주소 · 위경도 · 면적 · 위생업태명 |
| 막는 것 | **경기데이터드림 인증키**(무료, 회원가입 필요 — 세션이 대신 못 한다) |
| 오류 코드 | `ERROR-310` 서비스명 오류 · `ERROR-290` 인증키 무효 |

근거·죽은 경로 목록: `docs/finding-gyeonggi-licensing-source-2026-08-30.md`
