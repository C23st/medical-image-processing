"""P4 分割模块测试 (无 GL): 算法 + SEG 真值映射 + 纯函数切片逻辑。

用法:
    D:\\Anaconda_Envs\\medimg\\python.exe scripts/test_segment.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from app.core import segment  # noqa: E402
from app.core.dicom_loader import load_dicom_series  # noqa: E402
from app.views.slice_view import (  # noqa: E402
    map_window_level,
    slice_array,
    to_vtk_2d,
    volume_coords,
)

TEST_DATA = os.path.join(ROOT, "test_data")


def test_pure_functions():
    print("== 切片纯函数 ==")
    data = np.arange(2 * 3 * 4, dtype=np.float32).reshape(2, 3, 4)  # (z,y,x)
    sp = (1.0, 2.0, 3.0)
    arr, dims, sp2 = slice_array(data, sp, 0, 1)   # Axial z=1 -> (y,x)=(3,4)
    assert arr.shape == (3, 4) and dims == (4, 3), (arr.shape, dims)
    arr, dims, sp2 = slice_array(data, sp, 1, 1)   # Coronal y=1 -> (z,x)=(2,4)
    assert arr.shape == (2, 4) and dims == (4, 2)
    arr, dims, sp2 = slice_array(data, sp, 2, 2)   # Sagittal x=2 -> (z,y)=(2,3)
    assert arr.shape == (2, 3) and dims == (3, 2)
    assert volume_coords(0, 1, 2, 3) == (1, 2, 3)
    assert volume_coords(1, 1, 2, 3) == (2, 1, 3)
    assert volume_coords(2, 1, 2, 3) == (2, 3, 1)

    gray = map_window_level(data.astype(np.float32), 4.0, 4.0)
    assert gray.dtype == np.uint8 and gray.shape == data.shape
    img = to_vtk_2d(gray[0], (1.0, 1.0))
    assert img.GetDimensions() == (4, 3, 1)
    print("  切片/窗宽窗位/vtk 转换: OK")


def test_segmentation():
    print("\n== 分割算法 (真实 CT) ==")
    volumes = load_dicom_series(TEST_DATA)
    ct = next(v for v in volumes if v.modality == "CT" and v.patient["id"] == "PANCREAS_0001")
    seg_vol = next(v for v in volumes if v.modality == "SEG" and v.patient["id"] == "PANCREAS_0001")

    assert ct.slice_positions is not None and ct.slice_positions.shape == (240, 3)
    assert seg_vol.slice_positions is not None and seg_vol.slice_positions.shape == (71, 3)
    print(f"  slice_positions: CT={ct.slice_positions.shape} SEG={seg_vol.slice_positions.shape} OK")

    # 阈值
    m1 = segment.threshold(ct.data, 200.0)
    assert m1.shape == ct.shape and m1.sum() > 0
    print(f"  阈值(>=200HU): {m1.sum()} 体素")

    # Otsu
    m2, t = segment.otsu(ct.data)
    assert m2.shape == ct.shape and ct.data.min() <= t <= ct.data.max()
    print(f"  Otsu: 阈值={t:.1f} HU, {m2.sum()} 体素")

    # 真值映射 + Dice
    gt = segment.match_seg_to_ct(seg_vol, ct)
    assert gt.shape == ct.shape and gt.sum() > 0
    d = segment.dice(m1, gt)
    assert 0.0 <= d <= 1.0
    print(f"  真值映射: {gt.sum()} 体素; 阈值结果 vs 真值 Dice={d:.3f}")

    # 区域生长 (子卷, 种子取自真值)
    zs = np.where(gt.any(axis=(1, 2)))[0]
    z0 = int(zs[len(zs) // 2])
    sub = ct.data[z0:z0 + 40]
    gt_sub = gt[z0:z0 + 40]
    seed = tuple(int(v) for v in np.argwhere(gt_sub)[len(np.argwhere(gt_sub)) // 2])
    m3 = segment.region_growing(sub, seed, tol=40.0)
    assert m3.shape == sub.shape and m3.sum() > 0
    print(f"  区域生长: 种子={seed} 区域={m3.sum()} 体素; Dice={segment.dice(m3, gt_sub):.3f}")


if __name__ == "__main__":
    test_pure_functions()
    test_segmentation()
    print("\n分割测试: OK")
