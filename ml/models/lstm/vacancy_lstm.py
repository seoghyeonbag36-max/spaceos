"""LSTM 공실/매출 예측 모델 (PyTorch 골격).

시계열 공실률·매출 데이터를 입력받아 다음 기간 값을 예측한다.
목표 정확도: Phase 1 70% → Phase 2 85% → Phase 3 90%.
"""
import torch
import torch.nn as nn


class VacancyLSTM(nn.Module):
    def __init__(self, num_features: int, hidden: int = 128, layers: int = 2, dropout: float = 0.3):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=num_features,
            hidden_size=hidden,
            num_layers=layers,
            batch_first=True,
            dropout=dropout,
        )
        self.head = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, num_features)
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :])  # 마지막 타임스텝 → 예측값


if __name__ == "__main__":
    model = VacancyLSTM(num_features=5)
    dummy = torch.randn(2, 30, 5)  # 배치2, 30개월, 피처5
    print("output shape:", model(dummy).shape)  # (2, 1)
