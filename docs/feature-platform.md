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

**GNN 업종 추천 — 학습 완료·서빙 가동(2026-07-24).** 점포 그래프를 가로수길 209노드 → **27거점 23,250노드 + 엣지 89,709**(spatial_knn 73,774 + same_building 6,450 + same_chain 9,485)로 확장. 카카오 로컬 45건 상한을 `total_count` 재귀 격자 분할로 돌파해 실측 전수에 가깝게 수집(23,250건, 이전 45건-상한 노출은 5,646건 = 4.1배 확대). 수집기 세션 재사용+12스레드 병렬로 3.6분(순차 2시간+ 대비). 엣지 빌더는 cKDTree 로 교체(n² 거리행렬은 2만 노드에서 메모리 초과). same_chain 엣지가 150m 캡으로 거점별 단절돼 있던 그래프를 이어 연결 성분 27→22, 최대 성분 99%.
- 태스크: 노드 업종 대분류(category_group 7종: 음식점/카페/편의점/병원/약국/숙박/문화시설) 분류. 업종을 가리고 입지(거점 내 상대좌표·건물 규모·주변 밀집도·거점 원핫)만으로 맞혀 공실 유닛 추천에 전용.
- **성능(홀드아웃 층화 60/20/20): Top-1 62.2% / Top-3 91.1% (KPI Top-3 70% 달성) · macro-F1 0.179.** 단, 거점 사전분포 기준선이 Top-1 60.1%/Top-3 89.4% 라 **lift 는 +3.4%에 그친다** — 대분류 업종은 대부분 '어느 거점이냐'로 결정되고 그래프가 얹는 정보가 작다. 그래도 GNN 은 거점 평균이 못 주는 **자리별 점수**(공실 유닛 단위)를 주므로 제품 가치는 사전분포와 별개. 엣지 ablation: spatial_knn 단독 90.8% → +건물 90.9% → +체인(all) 91.1%, 다양화의 한계 기여는 대분류에선 작다.
- 라벨을 category 2단계(30클래스)로 내리면 lift +22%로 커지나 Top-3 57%로 KPI 미달 — 세분 업종일수록 그래프 정보가 더 필요하지만 절대 정확도는 낮다.
- **리뷰 유사도 엣지는 데이터 부재로 불가.** 네이버 블로그 검색 API 가 본문이 아닌 ~150자 스니펫만 주어 27거점 8,554건 중 점포명 2개 이상 동시 언급이 15건(0.2%)뿐. 점포 단위 리뷰 원문(플레이스 리뷰)은 공식 API 부재 — 소스가 바뀌기 전엔 재시도 무의미.
- 산출: `ml/artifacts/industry_gnn.pt` + `data/gold/platform_industry_recommend.json`(23,250노드 Top-3, ~4.8MB) + `ml/mlruns`. 서빙: `apps/backend/app/services/industry_recommend.py`(좌표→최근접 노드 400m, 없으면 거점 평균) → `/api/v1/ai/recommend-industry`(스텁 교체 완료). json 은 .gitignore/.vercelignore 예외로 배포 포함.

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
3. ~~**GNN 학습** (`ml/training/train_gnn.py`)~~ **완료** — 23,250노드·7 대분류 노드 분류, Top-3 91.1%(KPI 달성). 엣지를 동일건물·체인으로 다양화(리뷰 유사도는 데이터 부재로 불가). 대분류 태스크는 거점 사전분포 대비 lift 가 +3.4%로 작다는 게 확인됨(§0 참조) — 세분 라벨·감성 피처로 lift 개선은 후속.
4. ~~**추론 래퍼** (`ml/inference/predictor.py`)~~ **완료** — 체크포인트 실시간 추론 → forecast json 폴백. GNN 서빙은 별도 `services/industry_recommend.py`(json 직접 로드). MLflow Registry 대신 로컬 파일 스토어(`ml/mlruns`) 사용.
5. ~~**API 연동** (`apps/backend/app/api/v1/ai.py`)~~ **완료** — Redis 대신 인메모리 TTL 캐시(서버리스 고려). `predict-vacancy`·`recommend-industry` 모두 스텁 교체 완료(추천 json 부재 시 `gnn-stub` 폴백).

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
