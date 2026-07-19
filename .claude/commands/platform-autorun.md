# /platform-autorun — Platform(LSTM) 13거점 학습 + 다음 단계 자동 진행 (2시간 자율 모드)

사용자가 자리를 비운 상태의 **완전 자율 실행**이다. 아래 규칙과 단계를 순서대로 수행하라.

## 자율 실행 규칙 (최우선)

- **질문 금지.** 모든 선택은 합리적 기본값으로 스스로 결정하고, 결정 근거를 커밋 메시지·로그에 남긴다. 모든 확인성 질문의 답은 'yes'로 간주한다.
- **막히면 우회.** 어떤 하위 작업이 15분 이상 막히면(외부 API 장애, 의존성 실패 등) `TODO` 주석 + docs 메모로 문서화하고 다음 작업으로 넘어간다. 전체가 멈추는 것이 최악이다.
- **단계마다 커밋·푸시.** 각 단계 완료 시 검증(빌드·pytest) 통과 확인 후 커밋하고 push 한다(main 푸시 = Vercel 자동 배포 — 기존 워크플로우와 동일).
- **시간 예산 ~2시간**: A(15분) → B(50분) → C(20분) → D(30분) → 잔여 시간에 E. 예산 초과 시 해당 단계를 최소 동작 상태로 마무리하고 다음으로.
- **파괴 금지**: 기존 gold 데이터(garosugil PoC 산출물, PoC exit 통과분)를 덮어쓰지 말 것. 신규 산출물은 새 파일/새 키로 추가.

## A. 데이터 기반 확인·수집 (분기 시계열)

1. 대상 지역 = 백엔드 `/api/v1/commercial-districts` 의 **13거점** (garosugil 포함). 시드 정의는 `apps/backend/app/services/` 에서 확인.
2. `data/collectors/seoul_trdar.py` 로 서울 상권분석서비스 시계열(추정매출·점포·개폐업 등)을 Bronze 수집(이미 있으면 최신성 확인 후 재사용). 13거점 ↔ 상권코드(TRDAR_CD) 매핑을 만들어 `data/config/` 에 기록.
3. `python -m data.pipelines.build_gold` 로 `gold/garosugil/platform_district_timeseries` 를 생성·확장. **13거점 전부가 시계열에 포함되는지 검증**하고 커버리지를 로그로 남긴다. 부동산원(R-ONE) 공실률·임대료 조인은 키(`REB_RONE_API_KEY`)가 동작하면 포함, 아니면 TODO.

## B. LSTM 학습 (13거점)

1. `ml/` 가상환경 준비: `ml/requirements.txt` 설치(torch 는 CPU 빌드로 충분). MLflow 는 로컬 파일 스토어(`ml/mlruns`)로 사용 — 서버 기동 불필요.
2. `ml/training/datasets.py`: Gold `platform_district_timeseries` 를 읽어 거점×분기 피처 텐서를 만드는 로더 작성. 피처: 공실 프록시(VAC)·추정매출·점포수·개폐업률 + 가로수길은 building_vacancy 집계 추가.
3. `ml/training/train_lstm.py`: `VacancyLSTM` 학습. **데이터가 분기 단위이므로 look_back 은 30개월 고정이 아니라 가용 분기 수에 맞춰 조정**(예: 8~12분기, 최소 학습 가능 길이 미달 거점은 전 거점 통합(pooled) 학습 + 거점 임베딩으로 대체). MAE/RMSE·방향 정확도(상승/하락) 를 MLflow 에 기록, **목표: 홀드아웃 마지막 분기 예측 정확도 70%+** (미달 시 하이퍼파라미터 1~2회만 재시도하고 결과 그대로 문서화 — 무한 튜닝 금지).
4. 13거점 각각의 다음 분기 공실 예측값을 `data/gold/platform_vacancy_forecast.json` (거점 id → {forecast, mae, rmse, trained_at}) 으로 산출.

## C. 서빙 연동

1. `ml/inference/predictor.py`: 학습 산출물(모델 or forecast json)을 로드해 `predict_vacancy(district_id)` 제공. 모델 로드 실패 시 forecast json 폴백.
2. `apps/backend/app/api/v1/ai.py` 의 `predict-vacancy` 스텁을 predictor 호출로 교체. Redis 없으면 인메모리 TTL 캐시 폴백(서버리스 환경 고려 — Vercel 에서는 forecast json 정적 서빙이 기본 경로가 되도록).
3. 검증: `cd apps/backend && pytest` + 로컬 uvicorn 기동 후 `/api/v1/ai/predict-vacancy` 13거점 응답 확인 (spaceos:verify 스킬 절차 준수).

## D. 다음 단계 — Page 예측 연동 (로드맵 순서)

1. `/api/v1/heatmap` 및 상권 대시보드 응답에 **predicted_rate(다음 분기 예측)** 속성 추가 — 소스는 B-4 의 forecast.
2. 프론트(`apps/frontend`): 13거점 대시보드/심층 화면에 예측값 표시(현재값 대비 ▲▼). `npm run build` 통과 확인.
3. 커밋·푸시 → 배포 확인(`curl https://spaceos-sandy.vercel.app/api/v1/commercial-districts` 에 예측 필드 포함 여부).

## E. 잔여 시간 시 (선택)

- GNN 골격: `gold/platform_store_graph_nodes` 기반 엣지 생성(공간 kNN) + `train_gnn.py` 골격 작성 (학습 강행 금지 — 데이터 품질 확인까지만).
- `docs/feature-platform.md` 에 실제 구현 내역·정확도 결과 반영.

## 종료 보고

마지막에 반드시: 단계별 완료 여부, 13거점 학습 메트릭 표(MAE/RMSE/정확도), 미완료 TODO 목록, 커밋 해시들을 요약 출력하라.
