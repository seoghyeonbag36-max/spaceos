---
description: ML 모델(LSTM/GNN) 개발·학습 작업
---

SpaceOS AI 모델 작업을 수행한다. 대상: $ARGUMENTS

규칙:
1. 모델 정의는 `ml/models/{lstm,gnn}/`, 학습 스크립트는 `ml/training/`.
2. 실험·하이퍼파라미터·메트릭은 MLflow로 추적.
3. 공실 예측(LSTM) 목표 정확도 70%+(Phase1). 업종 추천(GNN) 정확도 20% 향상 목표.
4. 서빙은 `ml/inference/` 래퍼를 통해 backend `/api/v1/ai/*`와 연동.
5. 거점 데이터 순서: 라페스타 → 성수동 → 용봉동.
