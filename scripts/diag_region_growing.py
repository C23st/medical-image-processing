"""诊断: 区域生长 Dice 上不去是算法问题还是种子问题 (无 GUI, 纯逻辑)。

用法: python scripts/diag_region_growing.py [dicom文件夹]
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from app.core import segment  # noqa: E402
from app.core.dicom_loader import load_dicom_series  # noqa: E402


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join("test_data", "PANCREAS_0001")
    vols = load_dicom_series(folder)
    ct = next(v for v in vols if v.modality == "CT")
    seg = next(v for v in vols if v.modality == "SEG")
    gt = segment.match_seg_to_ct(seg, ct)
    n_gt = int(gt.sum())
    print(f"CT: {ct.data.shape} | SEG帧: {seg.data.shape} | 真值体素数: {n_gt} ({n_gt/ct.data.size*100:.2f}%)")

    in_gt = np.argwhere(gt)

    # ---- 实验1: 完美种子(真值内部点) × 各容差: 当前算法天花板 ----
    seed = tuple(in_gt[len(in_gt) // 2])
    seed_hu = float(ct.data[seed])
    print(f"\n[实验1] 完美种子(真值内部) seed={seed} HU={seed_hu:.1f}, 遍历容差:")
    print(f"{'tol':>5} {'mask体素':>9} {'Dice':>7}")
    for tol in (5, 10, 15, 20, 30, 50, 75, 100, 150):
        m = segment.region_growing(ct.data, seed, tol)
        print(f"{tol:>5} {int(m.sum()):>9} {segment.dice(m, gt):>7.4f}")

    # ---- 实验2: 固定容差20, 换 5 个真值内部种子: 种子敏感性 ----
    print(f"\n[实验2] tol=20, 真值内部 5 个不同种子:")
    rng = np.random.default_rng(0)
    idxs = rng.choice(len(in_gt), size=5, replace=False)
    for i in idxs:
        s = tuple(in_gt[i])
        m = segment.region_growing(ct.data, s, 20.0)
        print(f"  seed={s} HU={float(ct.data[s]):6.1f} -> mask={int(m.sum()):>8} Dice={segment.dice(m, gt):.4f}")

    # ---- 实验3: 容差20, 真值质心种子, 但先只统计种子所在那一层(2D) ----
    print(f"\n[实验3] tol=20 三维生长 vs 仅种子层二维生长:")
    m3d = segment.region_growing(ct.data, seed, 20.0)
    z0 = seed[0]
    m2d = np.zeros_like(m3d)
    m2d[z0] = m3d[z0]
    print(f"  3D: mask={int(m3d.sum()):>8} Dice={segment.dice(m3d, gt):.4f}")
    print(f"  仅种子层: mask={int(m2d.sum()):>8} Dice={segment.dice(m2d, gt):.4f}")

    # ---- 实验4: 自适应均值洪泛(经典区域生长) 对比 ----
    print(f"\n[实验4] 经典洪泛(自适应均值, 26邻域) 对比:")
    for tol in (15, 30, 60):
        m = _flood_grow(ct.data, seed, tol)
        print(f"  tol={tol:>3}: mask={int(m.sum()):>8} Dice={segment.dice(m, gt):.4f}")

    # ---- 实验5: 软组织预掩膜 + 洪泛 (推荐改进) ----
    print(f"\n[实验5] 软组织预掩膜[-50,300] + 洪泛(固定种子带/自适应均值):")
    for name, fn in (("固定种子带", _flood_grow2), ("自适应均值", _flood_grow3)):
        for tol in (10, 20, 30, 50):
            m = fn(ct.data, seed, tol)
            print(f"  {name} tol={tol:>3}: mask={int(m.sum()):>8} Dice={segment.dice(m, gt):.4f}")

    # ---- 实验6: 更窄的软组织窗 [20,200] ----
    print(f"\n[实验6] 窄窗[20,200] + 洪泛(固定种子带):")
    for tol in (10, 20, 30):
        m = _flood_grow2(ct.data, seed, tol, soft=(20.0, 200.0))
        print(f"  tol={tol:>3}: mask={int(m.sum()):>8} Dice={segment.dice(m, gt):.4f}")


def _flood_grow(data, seed, tol):
    """经典洪泛区域生长: 邻域与当前区域均值差 <= tol 则并入 (26 邻域)。"""
    z, y, x = int(seed[0]), int(seed[1]), int(seed[2])
    shape = data.shape
    mask = np.zeros(shape, dtype=bool)
    stack = [(z, y, x)]
    mask[z, y, x] = True
    vals = [float(data[z, y, x])]
    s = 0.0
    while stack:
        p = stack.pop()
        vp = float(data[p])
        mean = s / len(vals)
        # 与当前均值差过大且与种子差过大则不再扩张 (简单自适应)
        if abs(vp - mean) > tol and abs(vp - vals[0]) > tol:
            continue
        s += vp
        vals.append(vp)
        for dz in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dz == dy == dx == 0:
                        continue
                    q = (p[0] + dz, p[1] + dy, p[2] + dx)
                    if 0 <= q[0] < shape[0] and 0 <= q[1] < shape[1] and 0 <= q[2] < shape[2]:
                        if not mask[q]:
                            mask[q] = True
                            stack.append(q)
    return mask


def _flood_grow2(data, seed, tol, soft=(-50.0, 300.0)):
    """预掩膜 + 洪泛: 只在软组织窗内生长; 并入条件 = 与种子值差 <= tol (26邻域)。"""
    z, y, x = int(seed[0]), int(seed[1]), int(seed[2])
    shape = data.shape
    pre = (data >= soft[0]) & (data <= soft[1])
    seed_val = float(data[z, y, x])
    mask = np.zeros(shape, dtype=bool)
    if not pre[z, y, x]:
        return mask
    stack = [(z, y, x)]
    mask[z, y, x] = True
    while stack:
        p = stack.pop()
        for dz in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dz == dy == dx == 0:
                        continue
                    q = (p[0] + dz, p[1] + dy, p[2] + dx)
                    if (
                        0 <= q[0] < shape[0]
                        and 0 <= q[1] < shape[1]
                        and 0 <= q[2] < shape[2]
                        and not mask[q]
                        and pre[q]
                        and abs(float(data[q]) - seed_val) <= tol
                    ):
                        mask[q] = True
                        stack.append(q)
    return mask


def _flood_grow3(data, seed, tol, soft=(-50.0, 300.0)):
    """预掩膜 + 洪泛(自适应): 并入条件 = 与区域均值差 <= tol (26邻域)。"""
    z, y, x = int(seed[0]), int(seed[1]), int(seed[2])
    shape = data.shape
    pre = (data >= soft[0]) & (data <= soft[1])
    mask = np.zeros(shape, dtype=bool)
    if not pre[z, y, x]:
        return mask
    stack = [(z, y, x)]
    mask[z, y, x] = True
    s = float(data[z, y, x])
    n = 1
    while stack:
        p = stack.pop()
        mean = s / n
        for dz in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dz == dy == dx == 0:
                        continue
                    q = (p[0] + dz, p[1] + dy, p[2] + dx)
                    if (
                        0 <= q[0] < shape[0]
                        and 0 <= q[1] < shape[1]
                        and 0 <= q[2] < shape[2]
                        and not mask[q]
                        and pre[q]
                        and abs(float(data[q]) - mean) <= tol
                    ):
                        mask[q] = True
                        stack.append(q)
                        s += float(data[q])
                        n += 1
    return mask


if __name__ == "__main__":
    main()
