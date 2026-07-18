# Posting — 입점 솔루션 (외부 AI 창업 코파일럿 연동)

> PPPP: **Promotion → Posting**. 공실에 입점하려는 창업자에게 입점 의사결정 정보를 구조화해 제공한다.
> **2026-07-18 개정**: 자체 비용-효용 계산 대신 **외부에서 만든 AI 창업 코파일럿 프로그램을 연동해 적용**하는 것을 1순위로 한다. 내부 3-Tier(고급화/가성비/기능중심) 계산은 폴백·검증용으로 유지.

## 0. 연동 타당성 검증 (2026-07-18)

| 항목 | 판단 | 근거 |
|---|---|---|
| 아키텍처 적합성 | **가능** | Posting은 서비스 계층이 얇아(합성 3-Tier 계산) 어댑터 패턴으로 외부 프로그램 교체가 쉬움 |
| 연동 방식 | **조건부** | 외부 코파일럿의 제공 형태(REST API / Python 패키지 / 별도 앱)가 미확정 — `services/posting.py` 어댑터 한 곳에만 가정을 격리 |
| 폴백 | **필수** | 코파일럿 미설정·장애 시 내부 3-Tier 계산(`services/districts.py::tier_scenarios`)으로 응답 보장 |
| 스키마 | **필수** | 외부 응답을 `PostingResult`(예상 매출·투자비·ROI·손익분기)로 정규화 — FE·리포트가 공급자에 독립 |

## 1. 담당 코드 영역

```
apps/backend/app/services/posting.py      외부 코파일럿 어댑터 + 3-Tier 폴백 (현존)
apps/backend/app/schemas/posting.py       시뮬레이션 요청/결과 스키마 (현존)
apps/backend/app/api/v1/ai.py             POST /simulate-revenue (현존)
apps/backend/app/core/config.py           posting_copilot_url / posting_copilot_key
ml/inference/predictor.py                 매출 예측(LSTM) — 폴백·크로스체크 재사용
```

## 2. 환경 설정

```bash
cd apps/backend && source .venv/bin/activate
# 외부 AI 창업 코파일럿 (미설정 시 내부 3-Tier 폴백으로 동작)
echo "POSTING_COPILOT_URL=https://..." >> .env    # 확정 시 기입
echo "POSTING_COPILOT_KEY=..." >> .env
uvicorn app.main:app --reload
```

## 3. 작업 순서

1. **어댑터 계약 확정** — 외부 코파일럿의 입출력 명세 확보 → `services/posting.py`의 `_call_copilot()` TODO 해소. 그 전까지는 요청/응답을 `PostingRequest`/`PostingResult`로 고정해 둔다.
2. **폴백 유지** — `POSTING_COPILOT_URL` 미설정 또는 호출 실패 시 3-Tier 계산으로 동일 스키마 반환 (`source: "fallback-3tier"` 표기).
3. **정규화 검증** — 코파일럿 응답 필드 ↔ `PostingResult` 매핑 테이블 작성, 단위(만원/월) 불일치 방지.
4. **추천 연계** — GNN 업종 추천(Platform) 결과를 코파일럿 입력(업종 후보)으로 전달해 "이 공실 + 추천 업종 + 전략별 ROI"를 묶어 제공.
5. **근거 데이터 보강(선택)** — 공정위 가맹정보(창업비용, `api-keys-and-specs.md` §8-C)로 폴백 가정을 실데이터로 치환.

## 4. Claude Code 작업 예시

```
/clear
/posting 외부 코파일럿 응답 명세가 확정됨.
  services/posting.py 의 _call_copilot() 을 실제 API 호출로 교체하고
  응답을 PostingResult 로 정규화. 실패 시 3-Tier 폴백 유지.
  tests/test_posting.py 에 mock 응답 정규화 테스트 추가.
```

## 5. 검증

- `cd apps/backend && pytest` — 폴백 계산·스키마 정규화 단위 테스트
- 코파일럿 미설정 상태에서 `/api/v1/ai/simulate-revenue`가 3-Tier 결과를 반환하는지 확인
- 외부 응답 매핑에 단위·통화 가정이 주석으로 명시됐는지 확인 (`TODO: 실제 연동` 규칙 준수)
