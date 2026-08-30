"""寻找区域生长的合适演示目标 (无 GUI, 纯逻辑)。

背景: 胰腺 HU 与周围软组织重叠, 区域生长 Dice 上限约 0.10。
本脚本实测 肾脏 / 骨骼 两个高对比目标, 找演示效果好且不溢出的组合。

用法: python scripts/diag_rg_target.py [dicom文件夹]
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
from scipy import ndimage  # noqa: E402

from app.core import segment  # noqa: E402
from app.core.dicom_loader import load_dicom_series  # noqa: E402


def find_kidney_seed(data):
    """启发式找肾脏种子: 中腹部偏后 (row>130) 的增强软组织连通域。

    返回 (seed, 层范围) 或 (None, None)。
    """
    z, y, x = data.shape
    mid_slices = []
    for zi in range(z // 4, z * 3 // 4):
        sl = data[zi]
        m = (sl[130:, :] >= 80) & (sl[130:, :] <= 180)
        lab, n = ndimage.label(m, structure=np.ones((3, 3)))
        if n == 0:
            continue
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        mx = int(sizes.max()) if n else 0
        if 2500 <= mx <= 25000:  # 肾脏横截面面积量级
            mid_slices.append(zi)
    if not mid_slices:
        return None, None
    # 取连续层段
    runs, cur = [], [mid_slices[0]]
    for a, b in zip(mid_slices, mid_slices[1:]):
        if b - a <= 3:
            cur.append(b)
        else:
            runs.append(cur)
            cur = [b]
    runs.append(cur)
    runs.sort(key=len, reverse=True)
    zr = runs[0]
    zi = zr[len(zr) // 2]
    sl = data[zi]
    m = (sl[130:, :] >= 80) & (sl[130:, :] <= 180)
    lab, n = ndimage.label(m, structure=np.ones((3, 3)))
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    ci = int(np.argmax(sizes)) + 1
    ys, xs = np.nonzero(lab == ci)
    return (zi, int(ys.min()) + 130 + (ys.max() - ys.min()) // 2, int(xs.mean())), (zr[0], zr[-1])


def find_bone_seed(data, target_hu=700):
    """找脊柱皮质骨种子: 中腹部层 身体中心附近 HU 最接近 target_hu 的体素。"""
    z, y, x = data.shape
    zi = z // 2
    sl = data[zi]
    roi = sl[y // 4 : y * 3 // 4, x // 4 : x * 3 // 4]
    diff = np.abs(roi - target_hu)
    iy, ix = np.unravel_index(int(np.argmin(diff)), diff.shape)
    return (zi, y // 4 + int(iy), x // 4 + int(ix))


def report(name, data, seed, tol, gt=None):
    m = segment.region_growing(data, seed, tol)
    nz, ny, nx = m.shape
    bz = np.argwhere(m.any(axis=(1, 2)))
    by = np.argwhere(m.any(axis=(0, 2)))
    bx = np.argwhere(m.any(axis=(0, 1)))
    bbox = (
        (bz.min(), bz.max()), (by.min(), by.max()), (bx.min(), bx.max())
    ) if len(bz) else None
    hu = data[m]
    d = segment.dice(m, gt) if gt is not None else float("nan")
    print(f"  [{name}] seed={seed} HU={float(data[seed]):.0f} tol={tol:>4} | "
          f"mask={int(m.sum()):>8} ({int(m.sum())/1e6:.2f}M) | "
          f"HU范围={hu.min():.0f}~{hu.max():.0f} | bbox z{bbox[0]} y{bbox[1]} x{bbox[2]} | Dice={d:.3f}")


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join("test_data", "PANCREAS_0001")
    vols = load_dicom_series(folder)
    ct = next(v for v in vols if v.modality == "CT")
    data = ct.data
    z, y, x = data.shape
    print(f"{os.path.basename(folder)} CT: {data.shape}")

    seg = next((v for v in vols if v.modality == "SEG"), None)
    gt = segment.match_seg_to_ct(seg, ct) if seg is not None else None

    # ---- 肾脏 ----
    kseed, krange = find_kidney_seed(data)
    print(f"\n[肾脏] 种子={kseed} (肾脏 z 范围 {krange}):")
    if kseed:
        for tol in (10, 20, 30, 50):
            report("肾", data, kseed, tol)

    # ---- 骨骼 ----
    bseed = find_bone_seed(data)
    print(f"\n[骨骼] 脊柱皮质种子={bseed} HU={float(data[bseed]):.0f}:")
    for tol in (250, 350, 450):
        report("骨", data, bseed, tol)

    # ---- 肾脏 - 更小容差试探 ----
    kseed2, _ = find_kidney_seed(data)
    if kseed2:
        print(f"\n[肾脏小容差] 种子={kseed2} HU={float(data[kseed2]):.0f}:")
        for tol in (5, 8):
            report("肾", data, kseed2, tol)

    # ---- 脾脏 (备用候选) ----
    # 脾: 左后上腹的增强软组织, 大且相对孤立 (外侧是脂肪)
    print(f"\n[脾脏] 种子 = 左侧增强软组织连通域质心:")
    for tol in (15, 25, 40):
        s = find_spleen_seed(data)
        if s:
            report("脾", data, s, tol)


def find_spleen_seed(data):
    """启发式找脾脏种子: 左上腹 (z 前 40%, 左侧 x<1/3) 大块增强软组织。"""
    z, y, x = data.shape
    best = None
    best_n = 0
    for zi in range(z // 8, z * 2 // 5):
        sl = data[zi]
        m = (sl[:, : x // 3] >= 80) & (sl[:, : x // 3] <= 180)
        lab, n = ndimage.label(m, structure=np.ones((3, 3)))
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        if n and sizes.max() > best_n:
            best_n = int(sizes.max())
            best = (zi, sizes)
            best_lab, best_m = lab, m
    if best is None or best_n < 3000:
        return None
    ci = int(np.argmax(best[1])) + 1
    ys, xs = np.nonzero(best_lab == ci)
    return (best[0], int(ys.mean()), int(xs.mean()))


if __name__ == "__main__":
    main()
