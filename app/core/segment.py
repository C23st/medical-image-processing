"""图像分割算法层: 阈值 / Otsu / 区域生长 + 与真值对比 (Dice)。"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from skimage import filters


def threshold(data, low, high=None):
    """阈值分割: 保留 low <= v (可选 <= high) 的体素。"""
    mask = data >= low
    if high is not None:
        mask &= data <= high
    return mask


def otsu_threshold(data):
    """Otsu 自动阈值 (对全卷计算)。"""
    return float(filters.threshold_otsu(data))


def otsu(data):
    """Otsu 分割, 返回 (mask, 阈值)。"""
    t = otsu_threshold(data)
    return data >= t, t


def region_growing(data, seed, tol):
    """区域生长: 种子点灰度差 <= tol 的连通域 (6 邻域)。

    返回与 data 同形状的 bool mask。
    """
    z, y, x = int(seed[0]), int(seed[1]), int(seed[2])
    seed_val = float(data[z, y, x])
    mask = np.abs(data - seed_val) <= tol
    labeled, _n = ndimage.label(mask, structure=np.ones((3, 3, 3), dtype=np.uint8))
    return labeled == labeled[z, y, x]


def dice(a, b):
    """Dice 相似系数。"""
    a = np.asarray(a, dtype=bool)
    b = np.asarray(b, dtype=bool)
    inter = np.logical_and(a, b).sum()
    total = a.sum() + b.sum()
    if total == 0:
        return 1.0
    return 2.0 * inter / total


def match_seg_to_ct(seg_vol, ct_vol):
    """将多帧 SEG 标签按切片位置映射到 CT 网格。

    两个体数据需带 slice_positions (n,3) 的 ImagePositionPatient 列表。
    返回与 CT 同形状的 bool mask。
    """
    shape = ct_vol.shape
    mask = np.zeros(shape, dtype=bool)
    ct_pos = np.asarray(getattr(ct_vol, "slice_positions", None), dtype=float)
    seg_pos = np.asarray(getattr(seg_vol, "slice_positions", None), dtype=float)
    if ct_pos is None or seg_pos is None or ct_pos.ndim != 2 or seg_pos.ndim != 2:
        return mask

    axis = ct_pos[-1] - ct_pos[0]
    norm = np.linalg.norm(axis)
    if norm <= 0:
        return mask
    axis = axis / norm

    ct_proj = ct_pos @ axis
    seg_proj = seg_pos @ axis
    for k, p in enumerate(seg_proj):
        idx = int(np.argmin(np.abs(ct_proj - p)))
        if 0 <= idx < mask.shape[0]:
            mask[idx] = seg_vol.data[k] > 0
    return mask
