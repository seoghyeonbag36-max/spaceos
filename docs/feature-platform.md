# Platform — 상권 AI 추천 엔진

> PPPP: **Place → Platform**. 각 상권을 데이터·AI가 작동하는 하나의 플랫폼으로 전환. 공실 예측(LSTM)과 업종 추천(GNN)이 핵심.

## 0. 구현 현황 (2026-07-22, 27거점 Phase 2 확장 반영)

**LSTM 공실 예측 — v2 가동 중.** **27거점** pooled 학습으로 **홀드아웃 방향 정확도 74.1% (20/27, 목표 70% 달성)**, MAE 0.803 / RMSE 1.085 (vac_proxy 원단위) — 13거점 시절(84.6% / 0.901)보다 방향정확도는 내려갔지만 MAE·RMSE 는 개선. 거점이 늘며 홀드아웃 표본도 13→27 로 커져 지표가 더 보수적이다.

- 데이터: 서울 상권분석서비스(trdar) 분기 시계열 + **R-ONE 실측 조인** → `gold/platform13/platform_district_timeseries` (27거점 × 21분기 = 567행, 2021Q1~2026Q1, 13열). **학습에 쓰는 8개 피처 열은 결측 0**(R-ONE 3열 포함). 결측은 미사용 열에만 존재 — selng_amt 179·flpop 135·ix_* 250 (log_selng 은 fillna(0) 로 흡수)
- R-ONE 조인(완료): 공실률 소규모/중대형(`vac_small`/`vac_mid`)·임대료(`rent_small`), 27거점 ↔ R-ONE 상권 매핑은 `data/config/rone_districts.py` (뚝섬·이태원·잠실/송파·영등포역·동교연남 공유 매핑, 2024Q3 표본개편 유의). 수집기 `data/collectors/rone_rent.py`. **신규 거점 추가 시 이 매핑을 빠뜨리면 해당 거점 R-ONE 열이 전 분기 NaN → pooled LSTM 이 전 거점 NaN 으로 붕괴한다**
- 길단위 유동인구(`flpop`)도 수집·조인 완료 (`seoul_trdar --platform13-flpop`)
- 타깃: `vac_proxy = (폐업률 − 개업률) − 점포수 증감률(%)` 유지, R-ONE 실측은 **피처**.
  실험 기록(2026-07-19, mlruns): ① 타깃을 vac_small(실측)로 교체 → 방향정확도 46.2% 실패
  (표본개편 점프·소표본 0% 노이즈) ② log_flpop 피처 추가 → MAE 0.901→1.018 악화. 둘 다 보류.
- 학습: 거점 원핫 pooled. **27거점 best = look_back 10분기 / hidden 64 / 1층** (13~19거점 시절의 look_back 8 그리드는 27거점에서 전부 66.7% 로 묶여 미달 → look_back 10·12, hidden 96 을 그리드에 추가). 홀드아웃 = 거점별 마지막 분기. 방향 오답 7곳: apgujeong-rodeo, gwangjang, hongdae, jamsil, konkuk, sinchon, songridan
- 다분기 예측: 1~4분기 재귀 예측(`horizons`) — API `horizon_months`(1~12, 분기 올림 환산)로 선택. h2+ 는 외생 피처 persistence 근사라 불확실성 증가(검증 지표는 h1 기준)
- 실측 앵커: garosugil 응답에 `ground_anchor`(PoC 지상검증 39.1%, 가두 앵커 41.6%, 571동) 부착 — 프록시 스케일과 실제 공실률의 간극 참조용
- 추가 피처 실험: 상권변화지표(ix_opr_mt/ix_cls_mt)는 방향정확도 84.6→76.9% 악화로 기각(gold 컬럼은 유지). 소득소비-상권(OA-21278)은 **서비스 종료**(2026-06)로 수집 불가
- 분기 갱신 운영: `python -m data.pipelines.refresh_platform` — 수집→Gold(platform13 한정)→엣지→재학습 원커맨드 (배포는 git push). 새 분기 추가 시 `platform_districts.QUARTERS` 갱신 필요
- 산출: `ml/artifacts/vacancy_lstm.pt` + `data/gold/platform_vacancy_forecast.json`(2026Q2 예측) + `ml/mlruns`
- 서빙: Vercel 서버리스에 torch 를 싣지 않으므로 **forecast json 정적 서빙이 기본 경로** — `apps/backend/app/services/vacancy_forecast.py` (인메모리 TTL 5분, json은 .gitignore/.vercelignore 예외로 배포 포함)
- 노출: `/api/v1/ai/predict-vacancy`(스텁 교체 완료) + 대시보드·히트맵 응답의 `predicted_rate/delta/direction` + 프론트 27거점 카드·심층·범례 ▲▼ 배지

**GNN 업종 추천 — 그래프 27거점 확장 완료, 학습은 보류.** 점포 그래프를 가로수길 209노드 → **27거점 5,646노드 + 공간 kNN 엣지 17,582**(k=5, ≤150m, 평균 35.1m, 고립 15)로 확장 — `kakao_local --platform13` + `build_store_graph_edges --platform13` → `gold/platform13/`. 리뷰 유사도 엣지 원천으로 27거점 블로그 8,554건도 수집(`naver_blog --platform13`). `train_gnn.py` 품질 리포트: 업종 대분류 27종 중 희소(10노드 미만) 9종 — 표본 블로커는 크게 완화됐고, **잔여 블로커는 엣지 다양화(고객 공유·리뷰 유사도 계산)뿐.** 45건 상한에 걸린 카테고리(음식점·카페 등)는 격자 분할 수집 TODO.

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

1. ~~**데이터 로더** (`ml/training/datasets.py`)~~ **완료** — Gold `platform13/platform_district_timeseries`(분기) 기반. R-ONE 공실률·임대료 + 유동인구 조인 완료(§0). 잔여: 실측 공실률 타깃 전환(노이즈 처리 후)·감성 피처.
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
