# Posting — 입점 솔루션 (비용-효용 분석)

> PPPP: **Promotion → Posting**. 알고리즘 기반 반복 발행 체계. 공실에 입점하려는 창업자에게 "고급화 / 가성비 / 기능중심" 전략별 비용-효용과 예상 매출·ROI를 제시한다.

## 1. 담당 코드 영역

```
apps/backend/app/services/posting.py      입점 시나리오 비용-효용 계산 (신규)
apps/backend/app/api/v1/ai.py             /simulate-revenue (매출 시뮬레이터)
apps/backend/app/schemas/posting.py       입점 요청/결과 스키마 (신규)
ml/inference/predictor.py                 매출 예측(LSTM) 재사용
```

## 2. Claude Code 설치/환경

별도 설치 없음 — backend 환경을 그대로 사용한다.

```bash
cd apps/backend && source .venv/bin/activate
uvicorn app.main:app --reload
```

## 3. 작성해야 할 코드 (순서)

1. **입점 스키마** (`app/schemas/posting.py`) — 입력: `building_id`, `industry_type`, `strategy`(고급화/가성비/기능중심). 출력: 예상 매출, 초기 투자비, 월 고정비, **ROI(투자 회수 기간)**, 손익분기 시점.
2. **비용-효용 서비스** (`app/services/posting.py`) — 전략별 가정(인테리어 단가, 객단가, 회전율)을 파라미터화. Gold 레이어의 상권 지표 + 매출 예측(LSTM)을 결합해 시나리오별 손익 계산. **더미 가정에는 `TODO`로 실제 데이터 소스 명시.**
3. **매출 시뮬레이터 API** (`app/api/v1/ai.py`) — `/simulate-revenue` 라우트 추가, `services.posting` 호출. 세 전략을 한 번에 비교 반환.
4. **추천 연계** — GNN 업종 추천(Platform)과 결합해 "이 공실에 추천 업종 + 전략별 ROI"를 묶어 제공.

## 4. Claude Code 작업 예시

```
/clear
/backend-dev 입점 솔루션 비용-효용 분석.
  app/schemas/posting.py 에 PostingRequest(building_id, industry_type, strategy)
  와 PostingResult(expected_revenue, initial_cost, monthly_fixed, roi_months, bep_date) 정의.
  app/services/posting.py 에 고급화/가성비/기능중심 3전략 손익 계산 구현,
  ml.inference.predictor 의 매출 예측을 사용. 더미 가정은 TODO 주석으로 표시.
  /api/v1/ai/simulate-revenue 라우트에서 3전략 비교 반환.
```

## 5. 검증

- `cd apps/backend && pytest` — 시나리오 계산 단위 테스트 (입력→ROI 결과)
- ROI·BEP 수치의 가정값이 명시적이고 `TODO`로 실데이터 연동 지점이 표시됐는지 확인
- 데이터 기반·추측 최소화 원칙: 임의 상수는 근거 주석 필수
