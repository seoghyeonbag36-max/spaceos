# Platform — 상권 AI 추천 엔진

> PPPP: **Place → Platform**. 각 상권을 데이터·AI가 작동하는 하나의 플랫폼으로 전환. 공실 예측(LSTM)과 업종 추천(GNN)이 핵심.

## 0. 구현 현황 (2026-07-19, /platform-autorun A~E)

**LSTM 공실 예측 — 가동 중.** 13거점 pooled 학습으로 **홀드아웃 방향 정확도 84.6% (11/13, 목표 70% 달성)**, MAE 0.941 / RMSE 1.361 (vac_proxy 원단위).

- 데이터: 서울 상권분석서비스(trdar) 분기 시계열 → `gold/platform13/platform_district_timeseries` (13거점 × 21분기, 2021Q1~2026Q1, 결측 0)
- 타깃: `vac_proxy = (폐업률 − 개업률) − 점포수 증감률(%)` — R-ONE 공실률 미연동 상태의 대리 지표 (직접 공실률 조인은 TODO)
- 학습: 분기 데이터라 look_back 8분기, 거점 원핫 pooled (hidden 64 / 2층). 홀드아웃 = 거점별 마지막 분기. 방향 오답: apgujeong-rodeo, songridan
- 산출: `ml/artifacts/vacancy_lstm.pt` + `data/gold/platform_vacancy_forecast.json`(2026Q2 예측) + `ml/mlruns`
- 서빙: Vercel 서버리스에 torch 를 싣지 않으므로 **forecast json 정적 서빙이 기본 경로** — `apps/backend/app/services/vacancy_forecast.py` (인메모리 TTL 5분, json은 .gitignore/.vercelignore 예외로 배포 포함)
- 노출: `/api/v1/ai/predict-vacancy`(스텁 교체 완료) + 대시보드·히트맵 응답의 `predicted_rate/delta/direction` + 프론트 13거점 카드·심층·범례 ▲▼ 배지

**GNN 업종 추천 — 골격만.** 가로수길 점포 그래프: 노드 209(kakao) + 공간 kNN 엣지 670(k=5, ≤150m, 평균 41.2m, 고립 0) — `data/pipelines/build_store_graph_edges.py`. `ml/training/train_gnn.py` 는 품질 리포트까지만 구현(업종 대분류 18종 중 11종이 10노드 미만 → 병합 필요, 엣지가 공간 근접뿐이라 시너지/잠식 구분 불가). **학습은 엣지 다양화(고객 공유·리뷰 유사도) 후 진행.**

## 1. 담당 코드 영역

```
ml/models/lstm/vacancy_lstm.py     공실·매출 시계열 예측 (LSTM)
ml/models/gnn/industry_gnn.py      업종 추천 (GNN)
ml/training/                       datasets.py + train_lstm.py + train_gnn.py(골격) + MLflow
ml/inference/predictor.py          모델→forecast json 폴백 래퍼 (로컬·torch 환경용)
apps/backend/app/services/vacancy_forecast.py   서버리스 서빙 (forecast json 직접 로드)
apps/backend/app/api/v1/ai.py      추론 API (/predict-vacancy, /recommend-industry)
data/pipelines/build_gold.py       platform13 분기 시계열 빌더
data/pipelines/build_store_graph_edges.py       공간 kNN 엣지 빌더
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

## 3. 작성해야 할 코드 (순서) — §0 구현 현황 반영

1. ~~**데이터 로더** (`ml/training/datasets.py`)~~ **완료** — Gold `platform13/platform_district_timeseries`(분기) 기반. 원계획(월별·PostGIS·유동인구·감성·임대 시세)과 달리 분기 단위 + vac_proxy·매출·점포수·개폐업률 피처로 축소 구현. 잔여: R-ONE 공실률·생활인구 피처 조인.
2. ~~**LSTM 학습** (`ml/training/train_lstm.py`)~~ **완료** — 분기 데이터라 look_back 은 30개월이 아닌 8분기. 방향 정확도 84.6% (목표 70% 달성).
3. **GNN 학습** (`ml/training/train_gnn.py`) — **골격만** (품질 리포트까지). 엣지가 공간 kNN 뿐이라 학습 보류 — 고객 공유·리뷰 유사도 엣지 추가 후 `IndustryGNN` 노드 분류로 진행. **추천 정확도 20% 향상 목표**.
4. ~~**추론 래퍼** (`ml/inference/predictor.py`)~~ **완료** — 체크포인트 실시간 추론 → forecast json 폴백. `recommend_industry` 는 GNN 학습 후. MLflow Registry 대신 로컬 파일 스토어(`ml/mlruns`) 사용.
5. ~~**API 연동** (`apps/backend/app/api/v1/ai.py`)~~ **predict-vacancy 완료** — Redis 대신 인메모리 TTL 캐시(서버리스 고려). `recommend-industry` 는 여전히 `gnn-stub`.

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
