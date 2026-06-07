---
description: "PPPP 트랙 전환 → Program (마케팅 자동화·LLM·지역행사)"
argument-hint: "<이번 작업 목표 한 문장>"
---

# 트랙 컨텍스트: Program (Promotion → Program)

너는 지금 SpaceOS의 **Program 트랙** 담당이다. `CLAUDE.md` 규칙을 따른다.

## 먼저 읽기
- @docs/feature-program.md

## 트랙 정의
- 의미: 일회성 광고가 아닌 상인-건물주-소비자 **지속 관계·참여 구조**. LLM 콘텐츠 + 지역 행사/팝업 자동 기획.
- 윤리 기준(필수): **Humanistic Authority** — 균형(Balance)·공생(Symbiosis)·공감(Empathy).
- 핵심 기술: **LangChain** + LLM, 상권 감성 키워드 기반 톤앤매너.

## 화이트리스트 경로
- BE: `apps/backend/app/services/marketing.py`, `app/api/v1/marketing.py`
- FE 소비: `apps/frontend/src/lib/api.ts` 의 `getMarketing(id)`
- 데이터: `data/gold/serving/sentiment_*.json`, `data/bronze/program/`
- 키: `.env` 의 LLM 키 (git 커밋 금지)

## 실제 엔드포인트 / 함수 (현 코드 기준)
- GET  `/api/v1/marketing/{id}`         ← FE `getMarketing(id)` (행사 + 온라인 콘텐츠)
- (확장) POST `/api/v1/marketing/generate`  (LLM 생성)

## 이번 목표
$ARGUMENTS

## 작업 방식
1. 작은 작업으로 분해 → 승인 → 진행.
2. 생성 콘텐츠는 과장·허위 금지, 톤은 균형·공생·공감. 더미엔 `# TODO: 실제 연동`.
3. 마치면 `/verify` (`pytest`, 더미 키워드로 생성 확인).
