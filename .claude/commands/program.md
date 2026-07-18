---
description: "PPPP 트랙 전환 → Program (가게 단위 광고 솔루션 자동 생성 → 상권 단위)"
argument-hint: "<이번 작업 목표 한 문장>"
---

# 트랙 컨텍스트: Program (Promotion → Program)

너는 지금 SpaceOS의 **Program 트랙** 담당이다. `CLAUDE.md` 규칙을 따른다.

## 먼저 읽기
- @docs/feature-program.md

## 트랙 정의 (2026-07-18 개정 — 2단계)
1. **가게 단위(우선)**: 네이버 지도에 노출되는 상가의 **사진·정보·이미지·리뷰** 데이터를 활용해 그 가게의 **온/오프라인 마케팅 광고 솔루션을 자동 생성**.
2. **상권 단위(후속)**: **Platform에서 수집한 정보**(상권분석 시계열·감성·리뷰 키워드, `gold/program_content_context`)를 바탕으로 상권 마케팅 솔루션 생성.
- 윤리 기준(필수): **Humanistic Authority** — 균형(Balance)·공생(Symbiosis)·공감(Empathy).
- 핵심 기술: LLM(Claude — **vision 내장**, 상가 이미지 분석) + LangChain, 리뷰 키워드 기반 톤앤매너.

## 데이터 채널 제약 (검증 결과 — 반드시 준수)
- 상가 기본정보(이름·카테고리·좌표): 네이버 지역검색 API·카카오 로컬 (**공식, 허용**).
- 리뷰성 텍스트: 네이버 **블로그 검색 API** (**공식, 허용**).
- **네이버 플레이스 리뷰·사진: 공식 API 없음** → PoC 내부 검증에 한해 크롤러(`data/crawlers/review_crawler.py`) 사용, **상용 서비스는 점주 제공 데이터(B2B 온보딩 동의) 원칙**. 크롤링 산출물을 고객 노출 화면에 직접 서빙하지 말 것.

## 화이트리스트 경로
- BE: `apps/backend/app/services/marketing.py`, `app/schemas/marketing.py`, `app/api/v1/marketing.py`
- FE 소비: `apps/frontend/src/lib/api.ts` 의 `getMarketing(id)`, `generateStoreMarketing(...)`
- 데이터: `data/gold/serving/sentiment_*.json`, `data/bronze/program/`, `data/crawlers/review_crawler.py`
- 키: `.env` 의 LLM 키 (git 커밋 금지)

## 실제 엔드포인트 / 함수 (현 코드 기준)
- GET  `/api/v1/marketing/{id}`          ← FE `getMarketing(id)` (상권 단위 — TODO: Platform Gold 연동)
- POST `/api/v1/marketing/generate`      ← FE `generateStoreMarketing(...)` (가게 단위 — **현존**, LLM 연동 TODO)

## 이번 목표
$ARGUMENTS

## 작업 방식
1. 작은 작업으로 분해 → 승인 → 진행.
2. 생성 콘텐츠는 과장·허위 금지, 톤은 균형·공생·공감. 더미엔 `# TODO: 실제 연동`.
3. 마치면 `/verify` (`pytest`, 더미 상가 프로필로 생성 확인).
