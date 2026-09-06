# AGENTS.md — ml (LSTM 공실예측 · GNN 업종추천)

루트 [AGENTS.md](../AGENTS.md) 를 먼저 읽는다. 이 문서는 이 디렉터리에만 더 얹는 규칙이다.

## 구조

```
models/lstm/   공실 시계열 모델 정의
models/gnn/    업종 추천 모델 정의
training/      train_lstm.py · train_gnn.py · datasets.py
inference/     predictor.py — 서빙 래퍼
artifacts/     학습 산출물          mlruns/  MLflow 추적
```

입력은 **Gold 만** 읽는다. Bronze/Silver 를 직접 열지 않는다.

## 학습 실행

```bash
# 스레드 1개 · UTF-8 필수. 체크포인트 재개는 내장돼 있다
OMP_NUM_THREADS=1 PYTHONIOENCODING=utf-8 python -u -m ml.training.train_gnn --epochs 600 --patience 80
```

`OMP_NUM_THREADS=1` 을 빼면 이 환경에서 OpenBLAS 가 메모리를 물고 트레이스백 없이 죽는다.
`PYTHONIOENCODING=utf-8` 을 빼고 로그를 파일로 리다이렉트하면 cp949 로 UnicodeEncodeError 가 난다.

## 서빙 산출물 교체는 판단 영역이다

학습이 지표를 올렸다고 서빙 모델을 갈아끼우지 않는다. **실험은 `--no-save` 로 돌리고
결과를 보고한다.** 서빙본은 `gold/platform_vacancy_forecast.json` ·
`gold/platform_industry_recommend.json` 으로 나가고, 교체 여부는 별개 판단이다.

## 지표 해석은 넘어오지 않는다

`off-prior Top-3` 같은 관측 지표의 해석, 게이트의 승격·폐기, 기준선 선택은 루트 §4 의
판단 영역이다. 이 저장소는 **낡은 기준선에 새 결과를 댄 적이 있다**(08-19 값 37.63% 를
08-24 리팩터 이후 런에 그대로 대서 부호가 뒤집혔다). 대조군을 같은 코드로 함께 돌리지 않은
비교는 결론으로 쓰지 않는다.

## 실험 기록

MLflow 로 추적하고, 수치 결론은 `reports/*.json` 에 실측표로 남긴다.
문서에 숫자만 적고 근거 파일을 안 남기면 다음 사람이 그 숫자를 재현할 수 없다.
