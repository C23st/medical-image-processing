"""P6 切平面几何测试 (无 GL): 索引->世界坐标 / 平面向量 / 切片尺寸。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from app.core.dicom_loader import load_dicom_series  # noqa: E402
from app.views.view3d import compute_plane_specs, index_to_world  # noqa: E402

TEST_DATA = os.path.join(ROOT, "test_data")


def main():
    volumes = load_dicom_series(TEST_DATA)
    ct = next(v for v in volumes if v.modality == "CT" and v.patient["id"] == "PANCREAS_0001")
    image = ct.to_vtk_image(apply_direction=True)
    assert image.GetDirectionMatrix() is not None

    nx, ny, nz = image.GetDimensions()
    sx, sy, sz = image.GetSpacing()
    z, y, x = 100, 200, 300
    print(f"dims=({nx},{ny},{nz}) spacing=({sx:.3f},{sy:.3f},{sz:.3f})")

    specs = compute_plane_specs(image, (z, y, x), ct.data)
    axial, coronal, sagittal = specs

    # 轴向: 切片形状 (ny, nx), 平面原点 = origin + M@(0,0,z*sz)
    assert axial[0].shape == (ny, nx), axial[0].shape
    wo = index_to_world(image, 0, 0, z)
    assert abs(wo[2] - (-z * sz)) < 1e-6, wo  # 方向 diag(1,-1,-1): z 翻转
    print(f"轴向平面: 原点 z={wo[2]:.1f} (期望 {-z*sz:.1f}), 向量A={np.round(axial[3],1)}, 向量B={np.round(axial[4],1)}")
    assert np.allclose(axial[3], np.array([nx * sx, 0, 0])), axial[3]
    assert np.allclose(axial[4], np.array([0, -ny * sy, 0])), axial[4]

    # 冠状: 切片形状 (nz, nx)
    assert coronal[0].shape == (nz, nx), coronal[0].shape
    wo = index_to_world(image, 0, y, 0)
    assert abs(wo[1] - (-y * sy)) < 1e-6, wo
    print(f"冠状平面: 原点 y={wo[1]:.1f} (期望 {-y*sy:.1f})")

    # 矢状: 切片形状 (nz, ny)
    assert sagittal[0].shape == (nz, ny), sagittal[0].shape
    wo = index_to_world(image, x, 0, 0)
    assert abs(wo[0] - (x * sx)) < 1e-6, wo
    print(f"矢状平面: 原点 x={wo[0]:.1f} (期望 {x*sx:.1f})")

    print("\n切平面几何: OK")


if __name__ == "__main__":
    main()
