"""用于开发调试的合成体数据 (不依赖真实 DICOM)。"""
from __future__ import annotations

import numpy as np


def synthetic_ct_phantom(shape=(128, 128, 96)):
    """生成一个类头部 CT 体模。

    组成:
      - 高亮颅骨环 (骨)
      - 脑实质 (软组织)
      - 两个低密度脑室
      - 一个高亮病灶 (供后续分割演示)
      - 轻微高斯噪声
    """
    data = np.zeros(shape, dtype=np.float32)
    z, y, x = np.indices(shape).astype(np.float32)

    cz = (shape[0] - 1) / 2.0
    cy = (shape[1] - 1) / 2.0
    cx = (shape[2] - 1) / 2.0

    nz = (z - cz) / (shape[0] / 2.0)
    ny = (y - cy) / (shape[1] / 2.0)
    nx = (x - cx) / (shape[2] / 2.0)

    r = np.sqrt(nz * nz + ny * ny + nx * nx)

    # 颅骨环
    data[(r > 0.80) & (r <= 1.00)] = 1000.0
    # 脑实质
    data[r <= 0.80] = 40.0

    # 脑室 (左右两个低密度区域)
    for sign in (-1, 1):
        rv = np.sqrt(
            ((ny - sign * 0.25) / 0.12) ** 2
            + (nz / 0.25) ** 2
            + ((nx - sign * 0.15) / 0.10) ** 2
        )
        data[rv <= 1.0] = 5.0

    # 高亮病灶 (右前侧)
    rt = np.sqrt(
        ((ny - 0.05) / 0.10) ** 2
        + ((nz - 0.10) / 0.08) ** 2
        + ((nx - 0.40) / 0.10) ** 2
    )
    data[rt <= 1.0] = 120.0

    # 轻微噪声
    rng = np.random.default_rng(0)
    data += rng.normal(0.0, 2.0, shape).astype(np.float32)
    return data
