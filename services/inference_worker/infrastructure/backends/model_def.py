"""The PyTorch model — a small, self-contained CNN classifier.

Defined in-code (no downloaded weights) so the platform runs offline. Capacity
scales with ``width``/``depth`` from the :class:`ModelSpec`, giving v1/v2/v3
genuinely different latency. Torch is imported lazily so this module is only
loaded when a torch backend is actually selected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # keep torch out of the import graph unless really used
    import torch.nn as nn


def build_module(*, width: int, depth: int, num_classes: int) -> nn.Module:
    import torch.nn as nn

    class _Block(nn.Module):
        def __init__(self, c_in: int, c_out: int) -> None:
            super().__init__()
            self.conv = nn.Conv2d(c_in, c_out, 3, stride=2, padding=1)
            self.bn = nn.BatchNorm2d(c_out)
            self.act = nn.ReLU(inplace=True)

        def forward(self, x):  # type: ignore[no-untyped-def]
            return self.act(self.bn(self.conv(x)))

    class SmallResNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            chans = [3] + [width * (2**i) for i in range(depth)]
            self.stem = nn.Sequential(
                *[_Block(chans[i], chans[i + 1]) for i in range(depth)]
            )
            self.pool = nn.AdaptiveAvgPool2d(1)
            self.head = nn.Linear(chans[-1], num_classes)

        def forward(self, x):  # type: ignore[no-untyped-def]
            x = self.stem(x)
            x = self.pool(x).flatten(1)
            return self.head(x)

    return SmallResNet()
