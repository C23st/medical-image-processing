"""新增强方法耗时基准 (512x512 单层 -> 估算 240 层全卷)。"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from app.core import enhance  # noqa: E402

rng = np.random.default_rng(0)
img = (rng.normal(0, 60, (512, 512)) + np.linspace(-100, 100, 512)[None, :]).astype(np.float32)

cases = [
    ("fft 低通", "fft", {"kind": "lowpass", "cutoff": 0.1}),
    ("fft 高通", "fft", {"kind": "highpass", "cutoff": 0.1}),
    ("双边滤波", "bilateral", {"sigma_space": 9, "sigma_color": 75}),
    ("同态滤波", "homomorphic", {"gamma_low": 0.4, "gamma_high": 1.5, "cutoff": 0.1}),
]
for name, key, args in cases:
    t = time.time()
    out = enhance.apply(img[None], key, args)
    dt = time.time() - t
    print(f"{name}: {dt*1000:.0f} ms/层 -> 240 层约 {dt*240:.0f} s")
