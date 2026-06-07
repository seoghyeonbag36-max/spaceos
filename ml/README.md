# SpaceOS ML

AI 모델 학습/추론. PyTorch + PyTorch Geometric + MLflow.

- `models/lstm/` — 공실·매출 시계열 예측 (LSTM)
- `models/gnn/` — 업종 추천 (GNN, PyTorch Geometric)
- `training/` — 학습 스크립트, MLflow 실험 관리
- `inference/` — 백엔드 서빙용 추론 래퍼
- `notebooks/` — 탐색적 분석(EDA)

```bash
cd ml && pip install -r requirements.txt
python models/lstm/vacancy_lstm.py   # 골격 동작 확인
```
