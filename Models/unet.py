import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

class DoubleConv(nn.Module):
    """(convolution => LeakyReLU) * 2"""

    def __init__(self, in_channels, out_channels, mid_channels=None):
        super().__init__()
        if not mid_channels:
            mid_channels = out_channels
        self.double_conv = nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(mid_channels),
            nn.LeakyReLU(inplace=True),
            nn.Conv2d(mid_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.LeakyReLU(inplace=True)
        )

    def forward(self, x):

        return self.double_conv(x)
    
class Down(nn.Module):
    """Downscaling with maxpool then double conv"""

    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.maxpool_conv = nn.Sequential(
            nn.MaxPool2d(2),
            DoubleConv(in_channels, out_channels)
        )

    def forward(self, x):
        return self.maxpool_conv(x)


class Up(nn.Module):
    """Upscaling then double conv"""

    def __init__(self, in_channels, out_channels, bilinear=True):
        super().__init__()

        # if bilinear, use the normal convolutions to reduce the number of channels
        if bilinear:
            self.up = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
            self.conv = DoubleConv(in_channels, out_channels, in_channels // 2)
        else:
            self.up = nn.ConvTranspose2d(in_channels, in_channels // 2, kernel_size=2, stride=2)
            self.conv = DoubleConv(in_channels, out_channels)

    def forward(self, x1, x2):
        x1 = self.up(x1)
        # input is CHW
        diffY = x2.size()[2] - x1.size()[2]
        diffX = x2.size()[3] - x1.size()[3] 

        x1 = F.pad(x1, [diffX // 2, diffX - diffX // 2,
                        diffY // 2, diffY - diffY // 2])
        # if you have padding issues, see
        # https://github.com/HaiyongJiang/U-Net-Pytorch-Unstructured-Buggy/commit/0e854509c2cea854e247a9c615f175f76fbb2e3a
        # https://github.com/xiaopeng-liao/Pytorch-UNet/commit/8ebac70e633bac59fc22bb5195e513d5832fb3bd
        x = torch.cat([x2, x1], dim=1)
        return self.conv(x)


class OutConv(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(OutConv, self).__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=1)

    def forward(self, x):
        return torch.sigmoid(self.conv(x))
    
class UNet(nn.Module):
    def __init__(self, n_channels_in, n_channels_out, bilinear=False, scale = 1):

        super(UNet, self).__init__()
        self.n_channels_in = n_channels_in
        self.n_channels_out = n_channels_out
        self.bilinear = bilinear
        self.scale = scale

        self.inc = (DoubleConv(n_channels_in, 64 // self.scale))
        self.down1 = (Down(64 // self.scale, 128 // self.scale))
        self.down2 = (Down(128 // self.scale, 256 // self.scale))
        self.down3 = (Down(256 // self.scale, 512 // self.scale))
        factor = 2 if bilinear else 1
        self.down4 = (Down(512 // self.scale, 1024 // factor // self.scale))
        self.up1 = (Up(1024// self.scale, 512 // factor // self.scale, bilinear))
        self.up2 = (Up(512// self.scale, 256 // factor // self.scale, bilinear))
        self.up3 = (Up(256// self.scale, 128 // factor// self.scale, bilinear))
        self.up4 = (Up(128// self.scale, 64 // self.scale, bilinear))
        self.outc = (OutConv(64 // self.scale, n_channels_out))

    def forward(self, x):
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x4 = self.down3(x3)
        x5 = self.down4(x4)
        x = self.up1(x5, x4)
        x = self.up2(x, x3)
        x = self.up3(x, x2)
        x = self.up4(x, x1)
        logits = self.outc(x)
        return logits
    
    def compute_loss(self, x_gt, x_predicted, mask = None):

        # Compute the loss

        if mask is not None:
            # Compute the loss only on the masked area
            loss = F.mse_loss(x_predicted * mask, x_gt * mask, reduction='sum') / mask.sum()
        else:
            loss = F.mse_loss(x_predicted, x_gt)

        return loss

if __name__ == "__main__":

    import matplotlib.pyplot as plt

    model = UNet(2, 1)

    input_tensor = torch.randn(1, 2, 60, 59)

    output_tensor = model(input_tensor)

    print(output_tensor.shape)
    print(input_tensor.shape)

    fig, ax = plt.subplots(1, 2)

    ax[0].set_title("Input")
    ax[0].imshow(input_tensor[0, 0, :, :].detach().numpy())
    ax[1].set_title("Output")
    ax[1].imshow(output_tensor[0, 0, :, :].detach().numpy())
    plt.show()

    