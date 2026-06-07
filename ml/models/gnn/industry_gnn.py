"""GNN 업종 추천 모델 (PyTorch Geometric 골격).

노드: 점포/업종 클러스터. 엣지: 공간 근접성·고객 공유·리뷰 유사성.
상권 내 업종 시너지/잠식 효과를 학습하여 공실에 최적 업종을 추천한다.
목표: 기존 대비 추천 정확도 20% 향상.

설치: pip install torch torch_geometric
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from torch_geometric.nn import GCNConv
except ImportError:  # 골격 단계에서는 미설치 허용
    GCNConv = None


class IndustryGNN(nn.Module):
    def __init__(self, num_node_features: int, num_classes: int, hidden: int = 128):
        super().__init__()
        if GCNConv is None:
            raise ImportError("torch_geometric 가 필요합니다: pip install torch_geometric")
        self.conv1 = GCNConv(num_node_features, hidden)
        self.conv2 = GCNConv(hidden, num_classes)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.conv1(x, edge_index))
        x = F.dropout(x, training=self.training)
        x = self.conv2(x, edge_index)
        return F.log_softmax(x, dim=1)
