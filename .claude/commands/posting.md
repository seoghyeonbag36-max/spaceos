---
description: "PPPP 트랙 전환 → Posting (입점 솔루션·비용효용 3축·ROI)"
argument-hint: "<이번 작업 목표 한 문장>"
---

# 트랙 컨텍스트: Posting (Promotion → Posting)

너는 지금 SpaceOS의 **Posting 트랙** 담당이다. `CLAUDE.md` 규칙을 따른다.

## 먼저 읽기
- @docs/feature-posting.md

## 트랙 정의
- 의미: 입점 의사결정 정보를 구조화해 "게시" — **고급화/가성비/기능중심 3축** 비용-효용(cost-benefit) + ROI.
- 핵심 기술: **LSTM** 매출/공실 시계열 예측, Scikit-learn 피처, ROI(회수 개월) 산출.

## 화이트리스트 경로
- BE: `apps/backend/app/services/posting.py`, `app/api/v1/ai.py`
- ML: `ml/models/lstm/`, `ml/inference/`
- FE 소비: `apps/frontend/src/lib/api.ts` 의 `getPostings(id)`
- 데이터: `data/gold/features/posting_*.parquet`

## 엔드포인트 / 함수
- GET  `/api/v1/commercial-districts/{id}/postings`  ← FE `getPostings(id)` (3-Tier 시나리오, **현존**)
- POST `/api/v1/ai/simulate-revenue`  (예상매출 / ROI / 손익분기 — **확장 예정**, 본 트랙에서 신설)

## 이번 목표
$ARGUMENTS

## 작업 방식
1. 작은 작업으로 분해 → 승인 → 진행.
2. 3축을 한 번에 비교하는 카드 스키마로 반환, 더미엔 `# TODO: 실제 연동`.
3. 마치면 `/verify` (`pytest`, 더미 입력 실행).
