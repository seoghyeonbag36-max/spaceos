---
description: "PPPP 트랙 전환 → Posting (외부 AI 창업 코파일럿 연동 + 3-Tier ROI 폴백)"
argument-hint: "<이번 작업 목표 한 문장>"
---

# 트랙 컨텍스트: Posting (Promotion → Posting)

너는 지금 SpaceOS의 **Posting 트랙** 담당이다. `CLAUDE.md` 규칙을 따른다.

## 먼저 읽기
- @docs/feature-posting.md

## 트랙 정의 (2026-07-18 개정)
- 의미: 입점 의사결정 솔루션. **외부에서 만든 AI 창업 코파일럿 프로그램을 연동해 적용**하는 것이 1순위.
- 구조: `services/posting.py` **어댑터** — 외부 코파일럿(`POSTING_COPILOT_URL`) 호출 → 실패/미설정 시 내부 **3-Tier(고급화/가성비/기능중심)** 비용-효용 계산으로 폴백.
- 핵심 기술: 외부 코파일럿 API + LSTM 매출/공실 시계열 예측(폴백·검증용), ROI(회수 개월) 산출.
- ⚠️ 외부 코파일럿의 연동 형태(REST/패키지/별도 앱)는 미확정 — 어댑터 경계 밖으로 가정을 퍼뜨리지 말 것.

## 화이트리스트 경로
- BE: `apps/backend/app/services/posting.py`, `app/schemas/posting.py`, `app/api/v1/ai.py`
- ML: `ml/models/lstm/`, `ml/inference/`
- FE 소비: `apps/frontend/src/lib/api.ts` 의 `getPostings(id)`, `simulateRevenue(...)`
- 데이터: `data/gold/features/posting_*.parquet`

## 엔드포인트 / 함수
- GET  `/api/v1/commercial-districts/{id}/postings`  ← FE `getPostings(id)` (3-Tier 시나리오, **현존**)
- POST `/api/v1/ai/simulate-revenue`  ← FE `simulateRevenue(...)` (**현존** — 코파일럿 어댑터 경유, 미설정 시 내부 폴백)

## 이번 목표
$ARGUMENTS

## 작업 방식
1. 작은 작업으로 분해 → 승인 → 진행.
2. 외부 코파일럿 응답은 반드시 `PostingResult` 스키마로 정규화해 반환. 더미엔 `# TODO: 실제 연동`.
3. 마치면 `/verify` (`pytest`, 더미 입력 실행).
