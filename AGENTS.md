# AGENTS.md — SpaceOS 작업 지침 (Codex 등 코딩 에이전트용)

**여기가 작업 루트다.** `.git` 이 이 디렉터리에 있다. 상위 폴더에서는 아무것도 만들지 않는다.

SpaceOS는 물리적 상권의 디지털 트윈 SaaS다. 4대 기능을 **PPPP** 라 부른다 —
Platform(상권 AI 추천) · Page(공실 히트맵·3D 트윈) · Posting(입점 솔루션) · Program(마케팅 자동화).

> 이 문서는 Codex 등 외부 에이전트용 요약이다. 설계 배경·판단 이력은
> [CLAUDE.md](CLAUDE.md) 와 [docs/spaceos-vibe-build-sequence.md](docs/spaceos-vibe-build-sequence.md) 에 있다.

---

## 0. 이 저장소의 제1원칙 — 근거 없는 값을 채우지 않는다

**실측처럼 보이는 추정치가 이 프로젝트에서 가장 나쁜 산출물이다.**
데모가 그럴듯해 보이는 대가로 사업화 평가에서 신뢰를 잃기 때문이다.

의도적으로 **비워둔 채 멈춘 지점**들이 있다. 미완성 코드처럼 보이지만 미완성이 아니다 —
데이터가 없어서 멈춘 것이고, 채우는 순간 회귀다.

| 지점 | 상태 | 채우면 안 되는 이유 |
|---|---|---|
| `prem`(권리금) · `foot`(구역 유동인구) · `rec`(추천 Tier) — [services/districts.py:97](apps/backend/app/services/districts.py#L97) `tier_scenarios()` | 시드 유지 | 공개 데이터 자체가 없다. 임의값을 넣으면 그 위 ROI·회수기간이 전부 가정이 된다 |
| [build_vacant_units.py](data/pipelines/build_vacant_units.py) 산출물 → `/postings` 배선 | **산출만 하고 미배선** | 위 3개가 정해지기 전에는 "실제 건물"이라는 겉모습에 가정값이 올라타 시드보다 위험해진다 |
| 감성 구역(54거점 × 6구역 = 324개) | `추정` 배지 표기 | 구역 단위 리뷰 원문이 **0건**. Gold 활력 지표(`opbiz_rt`·`flpop` 등)로 대체 금지 — 그건 감성이 아니다 |
| 상권 행사가 비어 있는 거점(가로수길 등) | 빈 상태 표시 | 시드로 채우면 지어낸 행사를 지도에 찍는 셈 |

**막힌 값을 만나면 채우지 말고 실패하라.** 판단이 필요하면 작업을 멈추고 보고한다.

### 출처 표기는 응답 계약이다
합성값·시드값은 반드시 그렇다고 밝힌다. 프론트가 이 필드로 배지를 그린다.

- `vacancy_source`: `"gold"`(실측) / `"synthetic"`(합성) — 54거점 중 13곳만 실측
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
- 성능 목표: 3D 맵 로딩 <3초, API p95 <200ms

### 알려진 함정
- **Gold 산출물 배포 누락**: 런타임에 읽는 Gold 파일은 `.gitignore` 예외에 넣어야 한다.
  안 넣으면 로컬은 되고 **프로덕션만 조용히 폴백**한다. 확인은 출력이 아니라 **종료코드**로:
  `git check-ignore <path>; echo $?` → `0` 이면 무시되는 중(= 배포 안 됨)
- **대장 수집은 AC 전원 필수**: 배터리 구동 시 약 7배 느려지고 덮개를 닫으면 절전으로 멈춘다
- **pytest가 트레이스백 없이 죽으면** 코드 문제가 아니라 메모리(OpenBLAS 할당 실패)다

---

## 4. 담당 경계 — Codex가 손대지 않는 것

Claude Code와 병행 작업 중이다. 아래는 **설계·판단 영역이라 넘어오지 않는다.**
해당하면 코드를 고치지 말고 보고한다.

- §0 의 막아둔 지점을 **채우는** 변경 (`prem`·`foot`·`rec`, 공실유닛 배선, 감성 대체)
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
