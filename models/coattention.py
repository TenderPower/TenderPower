import torch
import torch.nn as nn
from einops import rearrange
import models.homo as homo


class CoAttentionModule(nn.Module):
    def __init__(self, input_channels=2048, hidden_channels=256, attention_type="coam"):
        super().__init__()
        if attention_type == "coam":
            self.attention_layer = CoAttentionLayer(input_channels, hidden_channels)
        elif attention_type == "noam":
            self.attention_layer = NoAttentionLayer()
        elif attention_type == 'homo':
            self.attention_layer = MyLayer()
        else:
            raise NotImplementedError(f"Unknown attention {attention_type}")

    def forward(self, left_features, right_features, h, h_inv):

        weighted_r = self.attention_layer(left_features, right_features, h)
        weighted_l = self.attention_layer(right_features, left_features, h_inv)
        # 将两个feature进行拼接
        left_attended_features = rearrange(
            [left_features, weighted_l], "two b c h w -> b (two c) h w"
        )
        right_attended_features = rearrange(
            [right_features, weighted_r], "two b c h w -> b (two c) h w"
        )
        # 将两个feature进行合并操作（加 or ×）
        # left_attended_features = left_features + weighted_l
        # right_attended_features = right_features + weighted_r
        # left_attended_features = left_features * weighted_l
        # right_attended_features = right_features * weighted_r
        return left_attended_features, right_attended_features


class CoAttentionLayer(nn.Module):
    def __init__(self, input_channels=2048, hidden_channels=256):
        super().__init__()
        self.reference_dimensionality_reduction = nn.Conv2d(
            input_channels, hidden_channels, kernel_size=1, stride=1, padding=0, bias=True
        )
        self.query_dimensionality_reduction = nn.Conv2d(
            input_channels, hidden_channels, kernel_size=1, stride=1, padding=0, bias=True
        )

    def forward(self, query_features, reference_features):
        Q = self.query_dimensionality_reduction(query_features)
        K = self.reference_dimensionality_reduction(reference_features)
        V = rearrange(reference_features, "b c h w -> b c (h w)")
        attention_map = torch.einsum("bcij,bckl->bijkl", Q, K)
        attention_map = rearrange(attention_map, "b h1 w1 h2 w2 -> b h1 w1 (h2 w2)")
        attention_map = nn.Softmax(dim=3)(attention_map)
        attended_features = torch.einsum("bijp,bcp->bcij", attention_map, V)
        return attended_features


class NoAttentionLayer(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, query_features, reference_features):
        return reference_features


class MyLayer(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, feature1, feature2, h):
        feature1_ = homo.alignfea(feature1, h)
        correlation = feature1_ - feature2
        return correlation
