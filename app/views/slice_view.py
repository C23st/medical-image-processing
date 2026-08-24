"""二维正交切片视图: numpy 切片 + vtkImageActor。

特点:
  - 支持标签图叠加 (半透明彩色)
  - 鼠标滚轮翻层, 左键拾取 (返回体数据坐标, 用于种子点/读数)
  - 纯函数切片逻辑独立可测
"""
from __future__ import annotations

import numpy as np
import vtk
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.util import numpy_support

AXIAL = 0
CORONAL = 1
SAGITTAL = 2


# ---- 纯函数 (无界面, 可独立测试) ----
def map_window_level(arr2d, window, level):
    """窗宽窗位映射 -> uint8。"""
    lo = level - window / 2.0
    hi = level + window / 2.0
    if hi - lo < 1e-6:
        hi = lo + 1e-6
    out = np.clip((arr2d.astype(np.float32) - lo) / (hi - lo), 0.0, 1.0)
    return (out * 255.0 + 0.5).astype(np.uint8)


def slice_array(data, spacing, orientation, idx):
    """取指定方向切片。

    返回 (arr2d, (cols, rows), (sx, sy))。
    data: (z, y, x); spacing: (sx, sy, sz)。
    """
    z, y, x = data.shape
    sx, sy, sz = spacing
    if orientation == AXIAL:
        return data[idx], (x, y), (sx, sy)
    if orientation == CORONAL:
        return data[:, idx, :], (x, z), (sx, sz)
    return data[:, :, idx], (y, z), (sy, sz)


def volume_coords(orientation, slice_idx, row, col):
    """(row, col) 二维坐标 -> 体数据坐标 (z, y, x)。"""
    if orientation == AXIAL:
        return (slice_idx, row, col)
    if orientation == CORONAL:
        return (row, slice_idx, col)
    return (row, col, slice_idx)


def label_to_rgba(lb2d, color=(255, 64, 64), alpha=200):
    """标签切片 -> RGBA (半透明红色)。"""
    rows, cols = lb2d.shape
    rgba = np.zeros((rows, cols, 4), dtype=np.uint8)
    m = lb2d > 0
    if m.any():
        rgba[m, 0] = color[0]
        rgba[m, 1] = color[1]
        rgba[m, 2] = color[2]
        rgba[m, 3] = alpha
    return rgba


def to_vtk_2d(arr2d, sp, ncomp=1):
    """二维数组 -> vtkImageData。"""
    rows, cols = arr2d.shape[0], arr2d.shape[1]
    flat = np.ascontiguousarray(arr2d).reshape(-1, ncomp) if ncomp > 1 else np.ascontiguousarray(arr2d).reshape(-1)
    varr = numpy_support.numpy_to_vtk(flat, deep=True, array_type=vtk.VTK_UNSIGNED_CHAR)
    img = vtk.vtkImageData()
    img.SetDimensions(cols, rows, 1)
    img.SetSpacing(sp[0], sp[1], 1.0)
    img.GetPointData().SetScalars(varr)
    return img


class SliceViewWidget(QWidget):
    AXIAL = AXIAL
    CORONAL = CORONAL
    SAGITTAL = SAGITTAL
    _LABELS = {AXIAL: "Axial", CORONAL: "Coronal", SAGITTAL: "Sagittal"}

    slice_changed = Signal(int)        # 当前切片索引
    picked = Signal(int, int, int)     # 拾取体素 (z, y, x)

    def __init__(self, orientation=AXIAL, parent=None):
        super().__init__(parent)
        self.orientation = orientation
        self._data = None
        self._spacing = (1.0, 1.0, 1.0)
        self._label = None
        self._slice = 0
        self._window = 255.0
        self._level = 127.5

        self.vtk_widget = QVTKRenderWindowInteractor(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.vtk_widget)

        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.10, 0.10, 0.12)
        self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)

        self._interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
        self._style = vtk.vtkInteractorStyleImage()
        self._interactor.SetInteractorStyle(self._style)
        # 自定义交互: 左键拾取种子点, 滚轮翻层。
        # 观察者优先级(1.0)高于默认样式(0.0), 返回 "AbortFlagOn" 阻止默认行为。
        self._interactor.AddObserver("LeftButtonPressEvent", self._on_left_press, 1.0)
        self._interactor.AddObserver("MouseWheelForwardEvent", self._on_wheel_forward, 1.0)
        self._interactor.AddObserver("MouseWheelBackwardEvent", self._on_wheel_backward, 1.0)

        self.image_actor = vtk.vtkImageActor()
        self.image_actor.GetProperty().SetInterpolationTypeToNearest()
        self.renderer.AddActor(self.image_actor)

        self.label_actor = vtk.vtkImageActor()
        self.label_actor.GetProperty().SetInterpolationTypeToNearest()
        self.label_actor.VisibilityOff()
        self.renderer.AddActor(self.label_actor)

        self.corner = vtk.vtkCornerAnnotation()
        self.corner.SetLinearFontScaleFactor(2)
        self.corner.SetMaximumFontSize(18)
        self.corner.SetText(2, self.label)
        self.renderer.AddViewProp(self.corner)

    # ---- 属性 ----
    @property
    def label(self):
        return self._LABELS[self.orientation]

    # ---- 数据 ----
    def set_volume_data(self, data, spacing):
        self._data = np.ascontiguousarray(data, dtype=np.float32)
        self._spacing = tuple(float(s) for s in spacing)
        self._label = None
        lo, hi = self.slice_range()
        self._slice = (lo + hi) // 2
        self._render()
        self.renderer.ResetCamera()

    def set_labelmap(self, label):
        if label is None:
            self._label = None
        else:
            lb = np.asarray(label)
            if lb.shape != self._data.shape:
                raise ValueError(
                    f"标签图尺寸 {lb.shape} 与体数据 {self._data.shape} 不一致"
                )
            self._label = lb
        self._render()

    def slice_range(self):
        z, y, x = self._data.shape
        if self.orientation == self.AXIAL:
            return 0, z - 1
        if self.orientation == self.CORONAL:
            return 0, y - 1
        return 0, x - 1

    def get_slice(self):
        return self._slice

    def set_slice(self, idx):
        lo, hi = self.slice_range()
        self._slice = int(max(lo, min(hi, idx)))
        self._render()
        self.slice_changed.emit(self._slice)

    def _nudge_slice(self, delta):
        self.set_slice(self._slice + delta)

    def set_window_level(self, window, level):
        self._window = float(window)
        self._level = float(level)
        self._render()

    # ---- 渲染 ----
    def _render(self):
        if self._data is None:
            return
        arr2d, _dims, sp = slice_array(
            self._data, self._spacing, self.orientation, self._slice
        )
        gray = map_window_level(arr2d, self._window, self._level)
        self.image_actor.SetInputData(to_vtk_2d(gray, sp))

        if self._label is not None:
            lb2d, _dims2, sp2 = slice_array(
                self._label, self._spacing, self.orientation, self._slice
            )
            rgba = label_to_rgba(lb2d)
            self.label_actor.SetInputData(to_vtk_2d(rgba, sp2, ncomp=4))
            self.label_actor.VisibilityOn()
        else:
            self.label_actor.VisibilityOff()

        _, hi = self.slice_range()
        self.corner.SetText(2, f"{self.label}  slice {self._slice}/{hi}")
        self.render()

    def render(self):
        self.vtk_widget.GetRenderWindow().Render()

    # ---- 交互 ----
    def _on_left_press(self, obj, event):
        self._pick_seed()
        return "AbortFlagOn"

    def _on_wheel_forward(self, obj, event):
        self._nudge_slice(1)
        return "AbortFlagOn"

    def _on_wheel_backward(self, obj, event):
        self._nudge_slice(-1)
        return "AbortFlagOn"

    # ---- 拾取 ----
    def _pick_seed(self):
        if self._data is None:
            return
        try:
            xd, yd = self._interactor.GetEventPosition()
            self.renderer.SetDisplayPoint(xd, yd, 0.0)
            self.renderer.DisplayToWorld()
            wx, wy, _wz, _w = self.renderer.GetWorldPoint()

            arr2d, _dims, sp = slice_array(
                self._data, self._spacing, self.orientation, self._slice
            )
            rows, cols = arr2d.shape
            col = int(round(wx / sp[0]))
            row = int(round(wy / sp[1]))
            row = max(0, min(rows - 1, row))
            col = max(0, min(cols - 1, col))
            z, y, x = volume_coords(self.orientation, self._slice, row, col)
            self.picked.emit(int(z), int(y), int(x))
        except Exception:  # noqa: BLE001
            import traceback

            traceback.print_exc()
