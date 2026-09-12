# AGENTS.md — apps/backend (FastAPI)

루트 [AGENTS.md](../../AGENTS.md) 를 먼저 읽는다. 이 문서는 이 디렉터리에만 더 얹는 규칙이다.

## 구조

```
app/api/v1/    라우터 — 도메인당 한 파일 (buildings · districts · heatmap · ai · marketing · auth · payments · admin)
app/services/  비즈니스 로직 — 라우터에 로직을 넣지 않는다
app/schemas/   Pydantic 스키마 (응답 계약)
app/models/    DB 모델 (계정층)
app/core/      설정 — 환경변수는 app.core.config.settings 를 거친다
tests/         pytest
```

## 규칙

- **타입 힌트 필수.** 주석·docstring 은 한국어, 기술 용어는 영문 병기
- 엔드포인트는 `/api/v1/...` 규약. 새 도메인이면 `api/v1/` 에 파일을 하나 더 만들고 `router.py` 에 등록한다
- **Gold 산출물을 라우터에서 직접 열지 않는다.** `services/gold_vacancy` · `services/vacant_inventory`
  같은 로더를 거친다 — 파일 경로가 여러 곳에 흩어지면 배포 누락을 못 잡는다
- 성능 목표: API p95 <200ms

## 응답 계약 — 값을 바꾸지 말고 출처를 밝힌다

`vacancy_source`(`"gold"` / `"synthetic"`) · `inputs_source`(필드별 `"rone"` / `"flpop+seed"` / `"seed"`)
는 프론트가 배지를 그리는 필드다. **이 필드들의 의미·규칙을 바꾸는 변경은 위임 범위 밖이다**
(루트 §4). 값이 없으면 채우지 말고 실패한다.

## 테스트

```powershell
cd apps/backend; python -m pytest              # 전체
cd apps/backend; python -m pytest -k <이름>    # 통과 조건으로 지목받은 것만
```

- **LLM 목킹 통과는 실호출의 증거가 아니다.** `tests/test_posting_marketing.py` 는 `_call_llm` 을
  통째로 목킹해서, 모델 ID 를 고의로 깨뜨려도 전부 `except` 에 잡혀 통과한다.
  실호출 계약은 opt-in 스위트가 친다 (외부 호출·크레딧 소모):
  `$env:PLACEOS_LIVE_LLM=1; python -m pytest tests/test_llm_live.py -v`
- **pytest 가 트레이스백 없이 죽으면** 코드 문제가 아니라 메모리다(OpenBLAS 할당 실패)

## 마이그레이션

`alembic upgrade head` 는 **계정층 DB 전용**이다. 분석 Gold 파이프라인과 무관하니
데이터가 안 보인다고 여기를 건드리지 않는다.
