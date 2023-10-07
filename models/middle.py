import torch
import torch.nn as nn
from models.coattention import MyLayer
from einops import rearrange
import models.CCL_pytorch as ccl

class PostModule(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer = CCLayer()
        self.homolayer = HomoLayer()

    def forward(self, left_features, right_features, left2right_features, right2left_features):
        # weighted_r_f应用到左边 -- 思路一
        # weighted_r_f = self.layer(left_features, right2left_features)
        # weighted_l_f = self.layer(right_features, left2right_features)
        # 使用的是原图片得到的probability -- 思路二_1
        weighted_r_f = self.layer(left_features, right_features)
        weighted_l_f = self.layer(right_features, left_features)
        # homo
        weighted_r_h = self.homolayer(right_features, left2right_features)
        weighted_l_h = self.homolayer(left_features, right2left_features)
        # 将homo和flow拼接--使用乘法-- 思路二_2
        # weighted_r = torch.mul(weighted_r_h, weighted_l_f)
        # weighted_l = torch.mul(weighted_l_h, weighted_r_f)
        # 将得到的probability应用到原特征上，然后将其与homo进行拼接--思路三（用到了思路二_1)
        left_features_ = torch.mul(left_features, weighted_r_f)
        right_features_ = torch.mul(right_features, weighted_l_f)
        # 思路三拼接 -- 看结果还行
        left_attended_features = torch.cat((left_features_, weighted_l_h), 1)
        right_attended_features = torch.cat((right_features_, weighted_r_h), 1)
        # 将两个feature进行拼接
        # left_attended_features = torch.cat((left_features, weighted_l), 1)
        # right_attended_features = torch.cat((right_features, weighted_r), 1)

        return left_attended_features, right_attended_features


class FuseMoudle(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer = MyLayer()
        self.homolayer = HomoLayer()

    def forward(self, left_features, right_features, left2right_features, right2left_features, weighted_r, weighted_l):
        # 向上采样 上一层的权重
        up = nn.Upsample(scale_factor=2, mode='bilinear')
        weighted_r_ = up(weighted_r)
        weighted_l_ = up(weighted_l)
        # 这一层的权重
        weighted_r = self.layer(left_features, right2left_features)
        weighted_l = self.layer(right_features, left2right_features)
        # 上一层和这一层进行融合(flow)
        weighted_r_f = torch.cat((weighted_r, weighted_r_), 1)
        weighted_l_f = torch.cat((weighted_l, weighted_l_), 1)
        # (homo)
        weighted_r_h = self.homolayer(right_features, left2right_features)
        weighted_l_h = self.homolayer(left_features, right2left_features)
        # 合并
        weighted_r = torch.cat((weighted_r_h, weighted_l_f), 1)
        weighted_l = torch.cat((weighted_l_h, weighted_r_f), 1)

        left_attended_features = torch.cat((left_features, weighted_l), 1)
        right_attended_features = torch.cat((right_features, weighted_r), 1)

        return left_attended_features, right_attended_features, weighted_r_f, weighted_l_f


class MiddleModule(nn.Module):
    def __init__(self):
        super().__init__()
        self.homolayer = HomoLayer()

    def forward(self, left_features, right_features, left2right_features, right2left_features, weighted_r, weighted_l):
        # 向上采样
        up = nn.Upsample(scale_factor=2, mode='bilinear')
        weighted_r_f = up(weighted_r)
        weighted_l_f = up(weighted_l)
        # homo
        weighted_r_h = self.homolayer(right_features, left2right_features)
        weighted_l_h = self.homolayer(left_features, right2left_features)
        # 合并
        weighted_r = torch.cat((weighted_r_h, weighted_l_f), 1)
        weighted_l = torch.cat((weighted_l_h, weighted_r_f), 1)

        left_attended_features = torch.cat((left_features, weighted_l), 1)
        right_attended_features = torch.cat((right_features, weighted_r), 1)

        return left_attended_features, right_attended_features, weighted_r, weighted_l


class FrontModule(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer = HomoLayer()

    def forward(self, left_features, right_features, left2right_features, right2left_features):
        weighted_r = self.layer(right_features, left2right_features)
        weighted_l = self.layer(left_features, right2left_features)
        left_attended_features = rearrange(
            [left_features, weighted_l], "two b c h w -> b (two c) h w"
        )
        right_attended_features = rearrange(
            [right_features, weighted_r], "two b c h w -> b (two c) h w"
        )
        return left_attended_features, right_attended_features


class HomoLayer(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, feature1, feature2):
        correlation = feature1 - feature2
        return correlation



class CCLayer(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, query_features, reference_features):
        c_probability = ccl.CCL(query_features, reference_features)
        return c_probability
