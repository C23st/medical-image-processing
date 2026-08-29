"""切平面纹理合成测试 (无 GL): 灰度 + 分割叠加混合。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
from vtkmodules.util import numpy_support  # noqa: E402

from app.views.view3d import plane_texture  # noqa: E402


def main():
    arr = np.full((4, 4), 100.0, dtype=np.float32)
    lb = np.zeros((4, 4), dtype=bool)
    lb[1, 1] = True

    # 无分割: 纯灰度
    img = plane_texture(arr, None, 255.0, 127.5)
    back = numpy_support.vtk_to_numpy(img.GetPointData().GetScalars()).reshape(4, 4, 3)
    assert np.all(back == 100), back
    print("无分割: 纯灰度 OK")

    # 有分割: 标签处为红色混合, 其余仍灰度
    img2 = plane_texture(arr, lb, 255.0, 127.5)
    back2 = numpy_support.vtk_to_numpy(img2.GetPointData().GetScalars()).reshape(4, 4, 3)
    exp_r = int(100 * 0.4 + 255 * 0.6)
    exp_g = int(100 * 0.4 + 64 * 0.6)
    assert tuple(back2[1, 1]) == (exp_r, exp_g, exp_g), back2[1, 1]
    assert tuple(back2[0, 0]) == (100, 100, 100), back2[0, 0]
    print(f"有分割: 标签处={tuple(back2[1,1])} (期望红 {exp_r},{exp_g},{exp_g}), 其余灰度 OK")

    print("\n切平面纹理合成: OK")


if __name__ == "__main__":
    main()
