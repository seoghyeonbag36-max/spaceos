# Platform — 상권 AI 추천 엔진

> PPPP: **Place → Platform**. 각 상권을 데이터·AI가 작동하는 하나의 플랫폼으로 전환. 공실 예측(LSTM)과 업종 추천(GNN)이 핵심.

## 1. 담당 코드 영역

```
ml/models/lstm/vacancy_lstm.py     공실·매출 시계열 예측 (LSTM)
ml/models/gnn/industry_gnn.py      업종 추천 (GNN)
ml/training/                       학습 스크립트 + MLflow
ml/inference/                      backend 서빙 래퍼
apps/backend/app/api/v1/ai.py      추론 API (/predict-vacancy, /recommend-industry)
```

## 2. Claude Code 설치/환경

ML은 별도 가상환경을 권장한다 (백엔드와 의존성 분리).

```bash
cd ml
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # torch, torch-geometric, mlflow, scikit-learn
# GPU 사용 시 torch는 CUDA 빌드로 별도 설치
python models/lstm/vacancy_lstm.py     # 골격 동작 확인 → output shape (2, 1)
```

MLflow 추적 서버(로컬):

```bash
mlflow ui --port 5000   # http://localhost:5000 에서 실험 추적
```

## 3. 작성해야 할 코드 (순서)

1. **데이터 로더** (`ml/training/datasets.py`) — Gold 레이어(PostGIS)에서 상권별 월별 시계열·그래프 피처를 읽어온다. 피처: 공실률, 업종 밀집도, 유동인구 지수, 감성 점수, 임대 시세.
2. **LSTM 학습** (`ml/training/train_lstm.py`) — `VacancyLSTM`을 학습. look_back=30개월, MAE/RMSE로 평가. **목표 정확도 70%+ (Phase1)**. MLflow에 파라미터·메트릭·모델 기록.
3. **GNN 학습** (`ml/training/train_gnn.py`) — 노드=점포/업종, 엣지=공간 근접·고객 공유·리뷰 유사. `IndustryGNN`으로 업종 분류/추천. **추천 정확도 20% 향상 목표**.
4. **추론 래퍼** (`ml/inference/predictor.py`) — 학습된 모델을 로드해 `predict_vacancy(district_id)`, `recommend_industry(building_id)` 함수 제공. MLflow Model Registry에서 최신 버전 로드.
5. **API 연동** (`apps/backend/app/api/v1/ai.py`) — 현재 스텁(`lstm-stub`/`gnn-stub`)을 `ml.inference.predictor` 호출로 교체. 추론 결과를 Redis에 캐싱(p95 <200ms 목표).

## 4. Claude Code 작업 예시

```
/clear
/ml-train 신사동 가로수길 공실률 LSTM 학습 스크립트 작성.
  ml/training/datasets.py 의 로더를 사용하고, look_back 30개월,
  MLflow로 MAE/RMSE 기록, 목표 정확도 70%+ 검증 로직 포함.

# 이후 API 연동
@apps/backend/app/api/v1/ai.py @ml/inference/predictor.py
ai.py 의 predict-vacancy 스텁을 predictor.predict_vacancy 호출로 교체하고
결과를 Redis에 캐싱해줘.
```

## 5. 검증

- `cd ml && python -m pytest`(테스트 추가 후) — 모델 입출력 shape, 추론 함수 동작
- MLflow UI에서 메트릭 확인 — MAE/RMSE 기준 정확도 70%+
- `cd apps/backend && pytest` — `/api/v1/ai/*` 응답 스키마
- 거점 데이터 순서: **신사동 가로수길 → 성수동** (Transfer Learning)
