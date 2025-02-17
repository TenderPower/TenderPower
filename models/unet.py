from typing import List, Optional, Union
import numpy
import torch
import torch.nn as nn
from segmentation_models_pytorch.unet.model import Unet, CenterBlock, DecoderBlock


class Unet(Unet):
    def __init__(self,
                 encoder_name: str = "resnet34",
                 encoder_depth: int = 5,
                 encoder_weights: Optional[str] = "imagenet",
                 decoder_use_batchnorm: bool = True,
                 decoder_channels: List[int] = (256, 128, 64, 32, 16),
                 decoder_attention_type: Optional[str] = None,
                 in_channels: int = 3,
                 classes: int = 1,
                 activation: Optional[Union[str, callable]] = None,
                 aux_params: Optional[dict] = None,
                 num_coam_layers: Optional[int] = 0,
                 return_decoder_features=False,
                 disable_segmentation_head=False,
                 fix_dim=False,
                 half_dim=False,
                 ):
        super().__init__(encoder_name, encoder_depth, encoder_weights, decoder_use_batchnorm, decoder_channels,
                         decoder_attention_type, in_channels, classes, activation, aux_params, num_coam_layers,
                         return_decoder_features, disable_segmentation_head)

        self.decoder = UnetDecoder(
            encoder_channels=self.encoder.out_channels,
            decoder_channels=decoder_channels,
            n_blocks=encoder_depth,
            use_batchnorm=decoder_use_batchnorm,
            center=True if encoder_name.startswith("vgg") else False,
            attention_type=decoder_attention_type,
            num_coam_layers=num_coam_layers,
            return_features=return_decoder_features,
            fix_dim=fix_dim,
            half_dim=half_dim,
        )


class UnetDecoder(nn.Module):
    def __init__(
            self,
            encoder_channels,
            decoder_channels,
            n_blocks=5,
            use_batchnorm=True,
            attention_type=None,
            center=False,
            num_coam_layers=0,
            return_features=False,
            fix_dim=False,
            half_dim=False,
    ):
        super().__init__()

        if n_blocks != len(decoder_channels):
            raise ValueError(
                "Model depth is {}, but you provide `decoder_channels` for {} blocks.".format(
                    n_blocks, len(decoder_channels)
                )
            )

        self.return_features = return_features

        encoder_channels = encoder_channels[1:]  # remove first skip with same spatial resolution
        encoder_channels = encoder_channels[::-1]  # reverse channels to start from head of encoder
        head_channels = encoder_channels[0]
        if half_dim:
            head_channels = head_channels // 2
        if fix_dim:
            a = 0
            b = 1
        else:
            a = 1
            b = 2

        in_channels = [(1 + a) * head_channels] + list(decoder_channels[:-1])
        skip_channels = list(encoder_channels[1:]) + [0]
        for i in range(0, num_coam_layers - 1):  # i的范围在[0,num_coam_layers-1)
            if half_dim:
                skip_channels[i] = skip_channels[i] // 2
            else:
                skip_channels[i] *= b
        out_channels = decoder_channels

        if center:
            self.center = CenterBlock(head_channels, head_channels, use_batchnorm=use_batchnorm)
        else:
            # 这个网络层的设计是用于占位的; 就是放到最后一层后面显得没有那么空虚，
            # 因为前面的层后面都有个激活函数，就最后一层后面啥都没有所以放个Identity占位
            self.center = nn.Identity()

        # combine decoder keyword arguments
        kwargs = dict(use_batchnorm=use_batchnorm, attention_type=attention_type)
        blocks = [
            DecoderBlock(in_ch, skip_ch, out_ch, **kwargs)
            for in_ch, skip_ch, out_ch in zip(in_channels, skip_channels, out_channels)
        ]
        # 这个DecoderBlock跑的通
        self.blocks = nn.ModuleList(blocks)

    def forward(self, *features):
        features = features[1:]  # remove first skip with same spatial resolution
        features = features[::-1]  # reverse channels to start from head of encoder
        head = features[0]
        skips = features[1:]

        x = self.center(head)

        decoded_features = []
        for i, decoder_block in enumerate(self.blocks):
            skip = skips[i] if i < len(skips) else None
            x = decoder_block(x, skip)
            decoded_features.append(x)

        if self.return_features:
            return x, decoded_features

        return x
