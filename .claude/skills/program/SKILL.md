---
name: program
description: PPPP 트랙 — Program(예비창업자·검증하려는 기창업자의 팝업스토어·가오픈·MVP 검증 program 자동 생성 + 상권 단위 콘텐츠). 검증 브리프·검증 지표·HA 가드를 다룰 때.
---

# 트랙 컨텍스트: Program (Promotion ▶ Program)

너는 지금 PlaceOS의 **Program 트랙** 담당이다. `CLAUDE.md` 규칙을 따른다.

## 먼저 읽기
- docs/feature-program.md — **§0-V 가 정본**(2026-09-17 대상 재정의)

## 트랙 정의 (2026-09-17 재정의)
- 묻는 질문: **이 아이템이 이 platform 에서 통하는지, 온·오프라인에서 어떤 검증 program 으로 확인할 것인가?**
- 대상:
  1. **예비창업자** — 아직 가게가 없다. 자기 아이템이 통하는 상권을 찾는다.
  2. **기창업자** — 사업은 하지만 이 상권·이 아이템은 안 해 봤다. **팝업스토어·가오픈·MVP** 로 검증한다.
- ⚠ **영업 중인 가게의 마케팅은 이 트랙이 아니다.** 리뷰·사진·메뉴 입력, 상호 검색, 블로그 스니펫
  주입, 상용 온보딩(점주 원문 동의)은 전부 삭제됐다. 되살리지 말 것 — 둘 다 그 자리에서 장사한 적이
  없어 리뷰가 존재하지 않는다.
- 산출물 세 벌: **online(모객, 창업자 단독)** · **offline(자리·상권 연계, 건물주·상인회와 함께)** ·
  **signals(검증 지표 = 지표·측정 방법·목표선·기각 조건)**. 지표가 결론이다.
- 윤리 기준(필수): **Humanistic Authority** — 균형(Balance)·공생(Symbiosis)·공감(Empathy).

## 입력 계약 — 세 층, 따로 싣는다
| 층 | 출처 | 등급 |
|---|---|---|
| ① 자리 | `unit_id` → `gold/{거점}/vacant_units.json` (`services/program_site`) | 대장 사실 |
| ② 상권 | `district_id` → `gold/{거점}/program_content_context.csv` + 행사 (`services/marketing._district_context`) | 관측 수치 |
| ③ 검증 브리프 | `ProgramBrief` — item·category·mode(popup/soft_open/mvp)·stage(pre_founder/founder)·hypothesis·기간·예산 구간·차별점 (`services/program_brief`) | **창업자 주장** — 사실로 단정하지 않는다 |

## 지켜야 할 규칙
- **있지도 않은 경험 금지** — 단골·기존 고객·쌓인 후기를 전제하면 `unproven_experience_claim`(폐기).
  재방문율·후기 수집을 **측정할 지표**로 적는 것은 정상이다(측정 문장 면제). 금칙어를 넓히지 말 것 —
  넓히면 검증 지표가 통째로 죽는다.
- **금액은 브리프 예산 구간에서만.** `budget_share` 는 int 퍼센트(절대액이 구조적으로 못 들어간다).
- **행사는 cite/propose/own 으로 가른다**(§0-F). 컨텍스트에 없는 행사를 cite 하면 폐기.
- 지표는 방식마다 다르다 — 기간 안에 잴 수 없는 지표(팝업에 재구매율)를 내지 않는다.
- HA 검사에 넘기는 생성물은 조각을 **줄바꿈으로** 잇는다(공백이면 문장 단위 판정이 무력해진다).

## 화이트리스트 경로
- BE: `apps/backend/app/services/{marketing,program_brief,program_site,ha_guard,events}.py`,
  `app/schemas/marketing.py`, `app/api/v1/marketing.py`
- FE: `apps/frontend/src/pages/ProgramStudio.tsx`(+`.css`·테스트), `src/lib/api.ts` 의 `generateProgram`
- 데이터: `data/gold/{거점}/program_content_context.csv`, `data/gold/{거점}/vacant_units.json`, 행사 Gold
- 키: `.env` 의 `LLM_API_KEY` (git 커밋 금지)

## 실제 엔드포인트 (현 코드 기준)
- POST `/api/v1/marketing/generate`     ← FE `generateProgram(brief)` — 검증 program (LLM · 스텁 폴백)
- GET  `/api/v1/marketing/sites`        ← 거점 공실 유닛(①층 후보)
- GET  `/api/v1/marketing/events`       ← 오프라인 연계 후보(행사, LLM 안 부름)
- GET  `/api/v1/marketing/{id}`         ← 상권 단위 온라인 콘텐츠 + 행사

## 이번 목표

호출 인수로 받은 목표 한 문장. 비어 있으면 진행하기 전에 묻는다.

## 작업 방식
1. 작은 작업으로 분해 → 승인 → 진행.
2. 생성 콘텐츠는 과장·허위 금지, 톤은 균형·공생·공감. 더미엔 `# TODO: 실제 연동`.
3. 마치면 `/verify` (`pytest` · `npm run build`, 예시 브리프로 생성 확인).
   새 프롬프트는 `PLACEOS_LIVE_LLM=1 pytest tests/test_llm_live.py` 로 실호출 확인.
