"""二维正交切片视图: numpy 切片 + vtkImageActor。

特点:
  - 支持标签图叠加 (半透明彩色)
  - 鼠标滚轮翻层, 左键拾取 (返回体数据坐标, 用于种子点/读数)
  - 纯函数切片逻辑独立可测
"""
from __future__ import annotations

import numpy as np
import vtk
from PySide6.QtCore import QEvent, Qt, Signal
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
    crosshair_moved = Signal(int, int, int)  # Shift+移动 (z, y, x)

    def __init__(self, orientation=AXIAL, parent=None):
        super().__init__(parent)
        self.orientation = orientation
        self._data = None
        self._spacing = (1.0, 1.0, 1.0)
        self._label = None
        self._slice = 0
        self._window = 255.0
        self._level = 127.5
        self._crosshair = None
        self._show_crosshair = False

        self.vtk_widget = QVTKRenderWindowInteractor(self)
        self.vtk_widget.setMouseTracking(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.vtk_widget)

        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.10, 0.10, 0.12)
        self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)

        self._interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
        self._style = vtk.vtkInteractorStyleImage()
        self._interactor.SetInteractorStyle(self._style)
        self._interactor.AddObserver("MouseMoveEvent", self._on_mouse_move, 1.0)
        # 滚轮翻层改用 Qt 事件过滤器拦截, 彻底避免 VTK 默认的滚轮缩放
        self.vtk_widget.installEventFilter(self)

        self.image_actor = vtk.vtkImageActor()
        self.image_actor.GetProperty().SetInterpolationTypeToNearest()
        self.image_actor.VisibilityOff()  # 无数据时不渲染, 避免空映射器报错
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

        self._cross_actor = self._create_cross_actor()
        self.renderer.AddActor(self._cross_actor)
        self._cross_actor.VisibilityOff()

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
        self.image_actor.VisibilityOn()

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
    def _on_mouse_move(self, obj, event):
        """Shift + 移动鼠标: 发射鼠标处体数据坐标 (十字联动)。"""
        if self._data is None or not self._interactor.GetShiftKey():
            return
        try:
            rc = self._mouse_to_rc()
            if rc is None:
                return
            row, col = rc
            z, y, x = volume_coords(self.orientation, self._slice, row, col)
            self.crosshair_moved.emit(int(z), int(y), int(x))
        except Exception:  # noqa: BLE001
            import traceback

            traceback.print_exc()

    def _mouse_to_rc(self):
        """当前鼠标位置 -> (row, col); 越界返回 None。"""
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
        if not (0 <= row < rows and 0 <= col < cols):
            return None
        return row, col

    def eventFilter(self, watched, event):
        """拦截 Qt 事件: 滚轮翻层、左键拾取; 彻底阻止样式左键调窗。

        左键按下在到达 VTK 前被消费, vtkInteractorStyleImage 收不到
        按下事件, 永远不会进入"调窗"状态, 左键拖动不再改变窗宽窗位。
        """
        if watched is self.vtk_widget:
            if event.type() == QEvent.Type.Wheel:
                delta = event.angleDelta().y()
                if delta != 0:
                    self._nudge_slice(1 if delta > 0 else -1)
                return True  # 消费事件, 不再传给 VTK
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
                self._pick_from_qt(event.position())
                return True  # 消费事件, 样式收不到左键按下
        return super().eventFilter(watched, event)

    # ---- 拾取 ----
    def _pick_from_qt(self, pos):
        """Qt 左键按下 -> 拾取体素 (z,y,x) 并发射 picked。"""
        if self._data is None:
            return
        try:
            x = int(pos.x())
            y_disp = int(self.vtk_widget.height() - pos.y())  # Qt y 向下 -> VTK 显示 y 向上
            self._interactor.SetEventPosition(x, y_disp)
            rc = self._mouse_to_rc()
            if rc is None:
                return
            row, col = rc
            z, y, x = volume_coords(self.orientation, self._slice, row, col)
            self.picked.emit(int(z), int(y), int(x))
        except Exception:  # noqa: BLE001
            import traceback

            traceback.print_exc()

    # ---- 十字准星 ----
    def _create_cross_actor(self):
        points = vtk.vtkPoints()
        points.SetNumberOfPoints(4)
        for i in range(4):
            points.SetPoint(i, 0.0, 0.0, 1.5)
        l1 = vtk.vtkLine()
        l1.GetPointIds().SetId(0, 0)
        l1.GetPointIds().SetId(1, 1)
        l2 = vtk.vtkLine()
        l2.GetPointIds().SetId(0, 2)
        l2.GetPointIds().SetId(1, 3)
        lines = vtk.vtkCellArray()
        lines.InsertNextCell(l1)
        lines.InsertNextCell(l2)
        poly = vtk.vtkPolyData()
        poly.SetPoints(points)
        poly.SetLines(lines)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(poly)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(1.0, 0.85, 0.0)
        actor.GetProperty().SetLineWidth(2.0)
        return actor

    def _crosshair_rc(self, z, y, x):
        """定位点 (z,y,x) 在当前视图平面上的 (col, row)。"""
        if self.orientation == self.AXIAL:
            return x, y
        if self.orientation == self.CORONAL:
            return x, z
        return y, z

    def set_crosshair(self, zyx):
        """设置/清除十字准星定位点 (z, y, x)。"""
        self._crosshair = None if zyx is None else tuple(int(v) for v in zyx)
        self._update_crosshair()

    def set_show_crosshair(self, on):
        self._show_crosshair = bool(on)
        self._update_crosshair()

    def _update_crosshair(self):
        if self._crosshair is None or not self._show_crosshair or self._data is None:
            self._cross_actor.VisibilityOff()
            self.render()
            return
        z, y, x = self._crosshair
        col, row = self._crosshair_rc(z, y, x)
        arr2d, _dims, sp = slice_array(
            self._data, self._spacing, self.orientation, self._slice
        )
        rows, cols = arr2d.shape
        wx = col * sp[0]
        wy = row * sp[1]
        w = cols * sp[0]
        h = rows * sp[1]
        points = self._cross_actor.GetMapper().GetInput().GetPoints()
        points.SetPoint(0, wx, 0.0, 1.5)
        points.SetPoint(1, wx, h, 1.5)
        points.SetPoint(2, 0.0, wy, 1.5)
        points.SetPoint(3, w, wy, 1.5)
        points.Modified()
        self._cross_actor.VisibilityOn()
        self.render()
