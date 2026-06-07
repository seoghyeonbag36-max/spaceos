---
description: "PPPP 트랙 전환 → Platform (상권 AI 추천 엔진 / GNN·감성)"
argument-hint: "<이번 작업 목표 한 문장>"
---

# 트랙 컨텍스트: Platform (Place → Platform)

너는 지금 SpaceOS의 **Platform 트랙** 담당이다. `CLAUDE.md` 규칙을 따른다.

## 먼저 읽기 (컨텍스트 로딩)
- @docs/10-platform-redefinition.md
- @docs/feature-platform.md

## 트랙 정의
- 의미: 각 상권을 데이터·거버넌스가 작동하는 **디지털 트윈 운영체계(플랫폼)** 로 전환.
- 핵심 기술: **GNN**(업종 시너지/잠식), **PostGIS** 공간쿼리, 상권 감성지수(Sentiment).

## 이 트랙에서만 건드리는 경로 (화이트리스트)
- ML: `ml/models/gnn/`, `ml/training/`, `ml/inference/`
- BE: `apps/backend/app/api/v1/ai.py`, `apps/backend/app/services/`
- FE 소비: `apps/frontend/src/lib/api.ts` 의 `getSentiment(id)`
- 데이터: `data/gold/features/`

## 실제 엔드포인트 / 함수 (현 코드 기준)
- POST `/api/v1/ai/recommend-industry`  (body: building_id)
- POST `/api/v1/ai/predict-vacancy`     (body: district_id, horizon_months)
- GET  `/api/v1/commercial-districts/{id}/sentiment`  ← FE `getSentiment(id)`

## 이번 목표
$ARGUMENTS

## 작업 방식
1. 위 목표를 2~4개 작은 작업으로 쪼개 제안하고, 내 승인 후 하나씩 진행.
2. 더미/합성 데이터에는 반드시 `# TODO: 실제 연동` 주석.
3. 마치면 `/verify` 로 검증(해당 시 `pytest`, ML import).
