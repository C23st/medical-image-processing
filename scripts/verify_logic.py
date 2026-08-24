"""无 GL 依赖的逻辑校验: 导入全部模块 + 验证体数据/切片管道。

用法:
    D:\\Anaconda_Envs\\medimg\\python.exe scripts/verify_logic.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import vtk  # noqa: E402

# 1) 导入全部应用模块 (捕获 import / 语法错误)
import app.main_window  # noqa: E402,F401
from app.core import VolumeData  # noqa: E402
from app.core.synthetic import synthetic_ct_phantom  # noqa: E402

print("模块导入: OK")


def check_volume():
    data = synthetic_ct_phantom()
    vol = VolumeData(data, spacing=(1.0, 1.0, 1.2), modality="CT")
    assert vol.shape == (128, 128, 96), vol.shape
    assert vol.dims == (96, 128, 128), vol.dims
    lo, hi = vol.minmax()
    print(f"体数据: shape={vol.shape} 范围=[{lo:.1f}, {hi:.1f}] WW/WL={vol.window:.1f}/{vol.level:.1f}")

    img = vol.to_vtk_image()
    assert img.GetDimensions() == (96, 128, 128), img.GetDimensions()
    sp = img.GetSpacing()
    assert abs(sp[0] - 1.0) < 1e-6 and abs(sp[2] - 1.2) < 1e-6, sp
    print(f"vtkImageData: dims={img.GetDimensions()} spacing={tuple(round(s,2) for s in sp)}")

    # 2) 校验 vtkImageViewer2 切片范围 (无需渲染)
    viewer = vtk.vtkImageViewer2()
    viewer.SetInputData(img)
    for name, fn in (
        ("Axial", viewer.SetSliceOrientationToXY),
        ("Coronal", viewer.SetSliceOrientationToXZ),
        ("Sagittal", viewer.SetSliceOrientationToYZ),
    ):
        fn()
        lo2, hi2 = viewer.GetSliceMin(), viewer.GetSliceMax()
        print(f"  {name:8s} slice range=[{lo2}, {hi2}]")
        assert hi2 > lo2, (name, lo2, hi2)

    print("逻辑校验: OK")


if __name__ == "__main__":
    check_volume()
