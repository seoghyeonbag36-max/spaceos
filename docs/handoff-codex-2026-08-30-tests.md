# Codex 위임 — 경기 거점 유입에 따른 테스트 4건 정정 (2026-08-30)

> AGENTS.md §5 의 4개 항목을 채운 작업 명세다. 판단은 이 문서가 끝냈고, Codex 는 실행만 한다.

## 배경 (판단은 이미 끝났다 — 되묻지 말 것)

2026-08-30 에 고양 `hwajeong` · 파주 `geumchon` 두 거점이 **Gold 산출물만으로** 서빙
목록에 올랐다(`app/data/measured_pages.py`). 서울 54거점 시드(`app/data/seoul_pages.py`)는
한 줄도 바뀌지 않았고, 거점 목록은 이제 **시드 54 + 실측 N** 이다.

그래서 아래 네 테스트가 깨졌다. **네 건 모두 테스트가 낡은 것이고 서비스 코드는 옳다.**
서비스 코드를 고쳐서 통과시키려 하지 말 것.

두 가지는 "값이 없는 것이 정상"이다. 이것이 이 저장소의 원칙이다 —
**0 은 "쟀더니 0", null 은 "재지 않았다"** 이고, 없는 값을 채우면 합성값이 실측처럼 보인다.

| 축 | 서울 시드 거점 | 실측 거점(고양·파주) | 왜 |
|---|---|---|---|
| `sentiment` · `reviews` · `risk_zones` | 값 있음 | **None** | 감성구역 시드가 없다 |
| `predicted_rate` · `predicted_direction` | 값 있음 | **None** | LSTM 이 서울 54거점 pooled 라 경기 예측이 없다 |
| `vacancy_source` | gold/synthetic | **gold** (둘 다 Tier1) | Gold 대표 집계가 실제로 산출된다 |

---

## 1. 대상 파일 (이 경계 밖은 건드리지 않는다)

```
apps/backend/tests/test_districts.py
apps/backend/tests/test_city_registry.py
apps/backend/tests/test_ai_forecast.py
```

**이 셋만 수정한다.** 아래는 **읽기만** 하고 수정 금지:
`apps/backend/app/**` · `app/data/seoul_pages.py` · `app/data/measured_pages.py` ·
`app/services/districts.py` · `data/**` · `.claude/**`

## 2. 입력 소스와 출처 표기

- 서빙 거점 목록의 단일 출처는 `app.services.districts.PAGES` / `PAGES_BY_ID` 다
  (= 시드 `DISTRICTS` + 실측 `measured_pages.MEASURED`). 테스트가 거점을 셀 때는
  **이것을 쓴다.** `DISTRICTS` 만 세면 실측 거점이 빠져 오탐이 난다.
- 실측 거점 판별은 응답의 `measured_only` 플래그(bool) 또는
  `measured_pages.MEASURED_BY_ID` 로 한다. **거점 id 를 테스트에 하드코딩하지 말 것**
  (거점은 계속 늘어난다 — `hwajeong`/`geumchon` 을 문자열로 박으면 다음 거점에서 또 깨진다).
- 새로 쓰는 주석은 한국어. 왜 이 단언이 이 모양인지(위 표의 근거)를 한 줄로 남긴다.

## 3. 통과 조건 = 테스트 이름

아래 4개가 통과해야 한다.

```bash
cd apps/backend
py -3.11 -m pytest -q tests/test_districts.py::test_list_districts \
  tests/test_districts.py::test_vacancy_source_matches_gold_presence \
  tests/test_city_registry.py::test_district_summary_carries_city \
  tests/test_ai_forecast.py::test_district_summaries_carry_predicted_rate
```

그리고 **전체 스위트에 새 실패가 없어야 한다**(기준선: 2026-08-30 이 4건만 실패):

```bash
cd apps/backend && py -3.11 -m pytest -q
```

### 각 테스트가 무엇을 단언해야 하는가

**① `test_districts.py::test_list_districts`** — 지금 `assert len(data) == len(DISTRICTS) == 54`.
→ 응답 거점 수는 **시드 + 실측** 이어야 한다. 시드가 54 라는 사실은 별도로 유지해도 좋으나,
   응답 길이를 54 로 못박지 말 것.

**② `test_districts.py::test_vacancy_source_matches_gold_presence`** — 헬퍼 `_gold_slugs()`
(같은 파일 180행 근처)가 `DISTRICTS` 만 순회해서 실측 거점을 못 본다. 그래서 geumchon 의
기대값이 `synthetic` 이 되는데 실제 응답은 `gold` 다(둘 다 옳게 Tier1 이다).
→ 헬퍼가 **서빙 목록 전체**를 순회하도록 고친다. 헬퍼의 판정 로직
   (`_gold_master` + `_counted` 로 "대표 집계가 실제로 산출되는가"를 보는 것)은 **그대로 둔다.**

**③ `test_city_registry.py::test_district_summary_carries_city`** — 지금
`all(r["city"] == "seoul")` 로 단언한다(경기 유입 전에 쓴 것이다).
→ **시드 거점은 `city == "seoul"` · `city_name == "서울"`**, 실측 거점은 자기 도시
   (`app.data.cities.CITIES` 에 등록된 슬러그)를 가져야 한다. 모든 거점에 `city` 와
   `city_name` 이 비어 있지 않아야 한다.

**④ `test_ai_forecast.py::test_district_summaries_carry_predicted_rate`** — 지금
모든 거점에 `predicted_rate is not None` 을 요구한다.
→ **시드 거점은 값이 있어야 하고**(범위 0~100, `predicted_direction` 은 "up"/"down"),
   **실측 거점은 `None` 이어도 통과**해야 한다. 단 `None` 일 때도 **키 자체는 존재**해야
   한다(응답 스키마에서 사라지면 안 된다). 값이 있으면 시드와 같은 범위 검사를 적용한다.

## 4. 금지 사항

1. **서비스 코드·시드·데이터를 고치지 않는다.** §1 의 세 테스트 파일만 수정한다.
2. **거점 id 하드코딩 금지**(`hwajeong`·`geumchon` 을 문자열로 박지 말 것).
3. **테스트를 약화시키지 말 것** — `skip`·`xfail`·단언 삭제로 통과시키는 것 금지.
   실측 거점에만 예외를 두고, 시드 거점의 단언은 종전 강도를 유지한다.
4. **없는 값을 채우지 않는다.** 경기 거점에 예측·감성 기본값을 넣어 통과시키려는 시도 금지
   (그 값이 없다는 사실 자체가 화면에 실려야 하는 정보다).
5. **판단 영역 침범 금지**(AGENTS.md §4): `vacancy_source` 표기 규칙, 앵커 대조 해석,
   집계 배제 규칙 3종(`floor_approx` · `expos_units` · `polygon_only`)은 건드리지 않는다.
6. 상위 디렉터리(`../`) 의 무엇도 건드리지 않는다.
7. 브랜치는 `fix/*`. **커밋·푸시는 지시받았을 때만** 한다.

## 참고

- 로그를 파일로 리다이렉트하면 `PYTHONIOENCODING=utf-8` 을 붙인다(cp949 로는 `—` 에서 죽는다).
- 배경 근거: `docs/finding-gyeonggi-aggregate-buildings-2026-08-30.md` ·
  `docs/plan-gyeonggi-expansion-2026-08-29.md` · `app/data/measured_pages.py` 머리말
- 현재 실패 재현: 위 §3 첫 명령 (2026-08-30 14:2x 기준 4건 실패 · 그 외 전부 통과)
