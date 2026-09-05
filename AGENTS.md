# AGENTS.md — SpaceOS 작업 지침 (Codex 등 코딩 에이전트용)

**여기가 작업 루트다.** `.git` 이 이 디렉터리에 있다. 상위 폴더에서는 아무것도 만들지 않는다.

SpaceOS는 물리적 상권의 디지털 트윈 SaaS다. 4대 기능을 **PPPP** 라 부르고, 전통 마케팅 4P 와
**1:1** 로 대응한다 (2026-09-05 재정의 — 종전엔 Page 가 Product/Price 를 겸하고 Posting·Program 이
Promotion 을 나눠 가졌다):

- **Place ▶ Platform** — 이 상권은 어떤 플랫폼인가 (상권 AI 추천)
- **Product ▶ Page** — 이 platform 에 어떤 page 를 놓을까 (공실 히트맵·층별 매물 목록·네이버 거리뷰)
- **Price ▶ Posting** — 어느 가격대의 page 를 posting 할까 (입점 솔루션·3-Tier·회수기간)
- **Promotion ▶ Program** — 어떤 홍보 program 을 돌릴까 (마케팅 자동화)

> 이 문서는 Codex 등 외부 에이전트용 요약이다. 설계 배경·판단 이력은
> [CLAUDE.md](CLAUDE.md) 와 [docs/spaceos-vibe-build-sequence.md](docs/spaceos-vibe-build-sequence.md) 에 있다.

---

## 0. 이 저장소의 제1원칙 — 근거 없는 값을 채우지 않는다

**실측처럼 보이는 추정치가 이 프로젝트에서 가장 나쁜 산출물이다.**
데모가 그럴듯해 보이는 대가로 사업화 평가에서 신뢰를 잃기 때문이다.

의도적으로 **비워둔 채 멈춘 지점**들이 있다. 미완성 코드처럼 보이지만 미완성이 아니다 —
데이터가 없어서 멈춘 것이고, 채우는 순간 회귀다.

> ⚠ **2026-08-25 갱신 — 아래 표는 네 행 모두 해소·정정됐다.** 그렇다고 §0 의 원칙이
> 약해진 것이 아니다. **"막힌 값을 만나면 채우지 말고 실패하라"는 그대로다** — 바뀐 것은
> *무엇이 막혀 있는가*이지 *막히면 어떻게 하는가*가 아니다. 낡은 가드는 두 방향으로
> 위험하다: 이미 정당해진 작업을 막고, 틀린 이유를 근거로 남긴다.

| 지점 | 상태 | 채우면 안 되는 이유 |
|---|---|---|
| ~~`prem` · `foot` · `rec`~~ — [services/districts.py:97](apps/backend/app/services/districts.py#L97) `tier_scenarios()` | ~~시드 유지~~ → **셋 다 해소** | ~~공개 데이터 자체가 없다~~ → 셋이 각기 다른 방식으로 풀렸다: **`rec`** 08-16 *회수 최단*으로 정의(`recommend_tier()`) · **`foot`** 08-25 **집계구 생활인구** 실데이터(유닛 528/528, 525유닛 `flpop+jipgyegu`) · **`prem`** 08-24 **입력 계약으로 이관**(권리금은 협상값이라 그 자리에 들어갈 기업만 안다. 안 주면 0 전제 + `inputs_source['prem']` 이 `absent`/`contract` 를 밝힌다). ⚠ **원칙은 유지**: 임의값 금지 · 출처 표기 필수 |
| ~~[build_vacant_units.py](data/pipelines/build_vacant_units.py) 산출물 → `/postings` 배선~~ | ~~산출만 하고 미배선~~ → **배선 완료 08-24** | 위 3개가 정해진 뒤 배선했다 — `services/vacant_inventory` 로 로더를 한 벌 두고 **서빙 66거점 664유닛**이 돈다(2026-09-05 실측 · 08-24 배선 당시엔 54거점 528유닛). ⚠ 그전까지 `resolved_units` 가 **시드 270유닛만** 읽어 Posting 화면이 손으로 적은 예시 위에서 돌고 있었다. 이 행이 '미배선'이라고 적혀 있었지만 실제로 필요한 것은 수집이 아니라 **배선**이었다 |
| 감성 구역 → **행정동 실측 구역으로 교체(2026-09-05)**. 66거점 221구역(거점당 1~11, 중앙 3) · 손으로 적은 324개는 삭제 | 구역은 `실측`, **감성은 `null`** | ⚠ **이유가 바뀌었다.** ~~구역 단위 리뷰 원문이 **0건**~~ → 원문은 **16,605건 있다**(naver_blog.json · 54거점). 그런데도 못 쓴다: 공간 키가 `district_id` 하나뿐이라 어떤 집계값도 **거점 내 상수**이고, 점포 귀속 노드가 **3.18%** 이며, 부정어가 **0.53%** 다(08-25 실측 기각 · feature-platform §0-K). **결론은 같고 근거가 다르다** — "없어서 못 쓴다"가 아니라 "있는데 정보량이 0 이다". Gold 활력 지표(`opbiz_rt`·`flpop` 등)로 대체 금지는 그대로 |
| 상권 행사가 비어 있는 거점 | 빈 상태 표시 | ⚠ **예시가 낡았다** — 가로수길은 이제 행사 **2건**이 있다. `gold/platform_events.json` 은 **52거점** 수록이고 그중 행사 0건인 거점은 **없다**. 여전히 표에 아예 없는 거점이 **둘(`garak`·`sillim`)** 이므로 원칙은 유효하다: 시드로 채우면 지어낸 행사를 지도에 찍는 셈이다 |

**막힌 값을 만나면 채우지 말고 실패하라.** 판단이 필요하면 작업을 멈추고 보고한다.

### 출처 표기는 응답 계약이다
합성값·시드값은 반드시 그렇다고 밝힌다. 프론트가 이 필드로 배지를 그린다.

- `vacancy_source`: `"gold"`(실측) / `"synthetic"`(합성) — **서빙 66거점 전부 `gold`**(2026-09-05 전수 실측).
  폴백 경로(`synthetic`)는 코드에 남아 있지만 서빙 목록에서는 지금 아무 거점도 타지 않는다
- `inputs_source`: 필드별 `"rone"` / `"flpop+seed"` / `"seed"`
- 더미 데이터에는 `TODO` 주석으로 실제 연동 지점을 명시한다

이 필드들의 **의미·규칙을 바꾸는 변경은 이 문서 범위 밖이다** (§4 참조).

---

## 1. 구조

```
apps/backend     FastAPI (Python 3.11) — 라우터 app/api/v1/, 로직 app/services/, 스키마 app/schemas/
apps/frontend    React + TypeScript + Vite — API 호출은 src/lib/api.ts 로 일원화, @/ 별칭
ml               PyTorch LSTM(공실 예측) / GNN(업종 추천) + MLflow
data             수집기 collectors/ · 파이프라인 pipelines/ · Bronze→Silver→Gold 3계층
infra            docker-compose / k8s / GitHub Actions
docs             설계 문서 (진행 상태는 spaceos-vibe-build-sequence.md 가 정본)
```

## 2. 명령어

```bash
# Backend
cd apps/backend && pip install -r requirements.txt && uvicorn app.main:app --reload
cd apps/backend && pytest

# Frontend (build = 타입체크 포함)
cd apps/frontend && npm install && npm run dev
cd apps/frontend && npm run build

# 파이프라인 (Gold 재빌드)
python -m data.pipelines.build_page_master <거점>
python -m data.pipelines.calibrate_vacancy <거점>     # R-ONE 앵커 대조
```

### LLM 테스트 — 목킹 통과는 실호출의 증거가 아니다
`test_posting_marketing.py` 는 `_call_llm` 을 통째로 목킹한다. 모델 ID를 고의로 깨뜨려도
전부 `except` 에 잡혀 **10 passed** 가 난다. 실호출 계약은 별도 스위트가 친다(외부 호출·크레딧 소모, opt-in):

```powershell
$env:SPACEOS_LIVE_LLM=1; py -3.11 -m pytest tests/test_llm_live.py -v
```

## 3. 코드 규칙

- **언어**: 주석·문서·커밋 메시지는 한국어, 기술 용어는 영문 병기
- **Backend**: 타입 힌트 필수. 엔드포인트는 `/api/v1/...` 규약
- **Frontend**: 함수형 컴포넌트 + 훅
- **Data**: Bronze→Silver→Gold 흐름을 지킨다. 계층을 건너뛰지 않는다
- 성능 목표: 지도·건물 상세 로딩 <3초, API p95 <200ms

### 알려진 함정
- **Gold 산출물 배포 누락**: 런타임에 읽는 Gold 파일은 `.gitignore` 예외에 넣어야 한다.
  안 넣으면 로컬은 되고 **프로덕션만 조용히 폴백**한다. 확인은 출력이 아니라 **종료코드**로:
  `git check-ignore <path>; echo $?` → `0` 이면 무시되는 중(= 배포 안 됨)
  단 `check-ignore` 는 **이미 추적 중인 파일을 무시 대상으로 보고하지 않는다.** 그래서 이
  종료코드는 "지금 배포되는가"에는 맞지만 **"규칙이 실제로 적용되는가"에는 답하지 않는다.**
  규칙 자체를 검증할 때는 `--no-index` 를 붙인다 — 이 차이가 `.gitignore` 의 garosugil
  전체 예외가 `data/gold/*/*` 에 덮여 죽은 것을 2026-08-15 까지 가렸다
- **대장 수집은 AC 전원 필수**: 배터리 구동 시 약 7배 느려지고 덮개를 닫으면 절전으로 멈춘다
- **pytest가 트레이스백 없이 죽으면** 코드 문제가 아니라 메모리(OpenBLAS 할당 실패)다

---

## 4. 담당 경계 — Codex가 손대지 않는 것

Claude Code와 병행 작업 중이다. 아래는 **설계·판단 영역이라 넘어오지 않는다.**
해당하면 코드를 고치지 말고 보고한다.

- §0 의 막아둔 지점을 **채우는** 변경 — ⚠ 2026-08-25 기준 그 넷은 모두 해소·정정됐다
  (`prem` 입력계약 · `foot` 집계구 실데이터 · `rec` 정의 · 공실유닛 배선 완료 · 감성 기각).
  **그래도 이 경계는 유지한다**: 해소된 자리를 *되돌리거나 근거를 갈아끼우는* 변경,
  그리고 §0 이 앞으로 새로 막는 지점은 여전히 판단 영역이다. 감성을 다시 넣는 시도는
  특히 그렇다 — 기각 근거가 실측이라 되살리려면 그 실측을 반증해야 한다
- `vacancy_source` · `inputs_source` 등 **출처 표기 규칙**의 변경
- 앵커 대조(`anchor_pct` · `anchor_gap_pp`) 해석과 집계 배제 규칙 3종
  (`floor_approx` · `expos_units`(집합건물) · `polygon_only`)
- 브랜치 머지 판단
- 상위 디렉터리(`../`)의 무엇이든 — 특히 `../archive/`

## 5. 작업 규약

**받은 작업에 아래 4개가 채워져 있어야 착수한다.** 하나라도 비면 착수하지 말고 되묻는다.

1. **대상 파일** — 이 경계 밖은 건드리지 않는다
2. **입력 소스와 출처 표기** — seed면 seed라고 응답에 적는다
3. **통과 조건 = 테스트 이름** — 사람 판단 없이 판정 가능해야 한다
4. **금지 사항** — 기본값: 값이 없으면 채우지 말고 실패한다

**브랜치**: Codex 는 `chore/*` · `fix/*` 에서 작업한다 (`feat/*` 는 Claude Code 몫).
같은 파일을 동시에 고치지 않는다. 커밋·푸시는 지시받았을 때만 한다.
