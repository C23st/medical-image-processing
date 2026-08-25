"""体数据封装: numpy 数组 + 空间信息, 并提供到 VTK 的转换。"""
from __future__ import annotations

import numpy as np
import vtk
from vtkmodules.util import numpy_support


class VolumeData:
    """封装一个三维体数据及其空间信息 (spacing / origin / direction)。"""

    def __init__(
        self,
        data: np.ndarray,
        spacing=(1.0, 1.0, 1.0),
        origin=(0.0, 0.0, 0.0),
        direction=None,
        modality="CT",
        patient=None,
        window=None,
        level=None,
        series_description="",
        slice_positions=None,
    ):
        self.data = np.asarray(data)
        self.spacing = tuple(float(v) for v in spacing)
        self.origin = tuple(float(v) for v in origin)
        self.direction = direction
        self.modality = modality
        self.patient = patient or {}
        self.series_description = series_description
        self.slice_positions = slice_positions

        if window is None or level is None:
            window, level = self._default_window_level()
        self.window = float(window)
        self.level = float(level)

    # ---- 基础信息 ----
    @property
    def shape(self):
        """numpy 形状 (z, y, x)。"""
        return self.data.shape

    @property
    def dims(self):
        """VTK 维度 (x, y, z) = (列, 行, 层)。"""
        z, y, x = self.data.shape
        return (x, y, z)

    def minmax(self):
        return float(self.data.min()), float(self.data.max())

    def index_to_ras(self, z, y, x):
        """体数据索引 (z, y, x) -> 患者物理坐标 (RAS, mm)。

        依据 spacing / origin / direction (方向余弦矩阵, 列为 x/y/z 轴方向)。
        """
        ijk = np.array([x, y, z], dtype=float) * np.array(self.spacing, dtype=float)
        if self.direction is not None:
            ijk = np.asarray(self.direction, dtype=float) @ ijk
        ras = ijk + np.asarray(self.origin, dtype=float)
        return (float(ras[0]), float(ras[1]), float(ras[2]))

    def _default_window_level(self):
        lo, hi = self.minmax()
        return (hi - lo, (hi + lo) / 2.0)

    # ---- VTK 转换 ----
    def to_vtk_image(self, apply_direction=False) -> "vtk.vtkImageData":
        """转换为 vtkImageData (float32), 保留 spacing/origin。

        numpy 数组形状 (z, y, x) 的 C 序展平顺序恰好与 VTK 点序 (x 最快)
        一致, 因此可直接按顺序填充标量。
        apply_direction=True 时才写入方向矩阵 (供三维重建等使用)。
        """
        arr = np.ascontiguousarray(self.data.astype(np.float32))
        flat = arr.ravel(order="C")
        vtk_arr = numpy_support.numpy_to_vtk(
            num_array=flat, deep=True, array_type=vtk.VTK_FLOAT
        )

        image = vtk.vtkImageData()
        image.SetDimensions(*self.dims)
        image.SetSpacing(*self.spacing)
        image.SetOrigin(*self.origin)
        image.GetPointData().SetScalars(vtk_arr)

        if apply_direction and self.direction is not None:
            mat = vtk.vtkMatrix3x3()
            d = np.asarray(self.direction, dtype=float).ravel()
            for i in range(3):
                for j in range(3):
                    mat.SetElement(i, j, d[i * 3 + j])
            image.SetDirectionMatrix(mat)
        return image
