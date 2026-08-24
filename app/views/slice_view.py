"""二维正交切片视图 (Axial / Coronal / Sagittal), 基于 vtkImageViewer2。"""
from __future__ import annotations

import vtk
from PySide6.QtWidgets import QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor


class SliceViewWidget(QWidget):
    """单一切片视图, 支持三种正交方向, 提供切片/窗宽窗位控制。"""

    AXIAL = 0
    CORONAL = 1
    SAGITTAL = 2
    _LABELS = {AXIAL: "Axial", CORONAL: "Coronal", SAGITTAL: "Sagittal"}

    def __init__(self, orientation=AXIAL, parent=None):
        super().__init__(parent)
        self.orientation = orientation
        self._image = None

        self.vtk_widget = QVTKRenderWindowInteractor(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.vtk_widget)

        # vtkImageViewer2: 先 SetupInteractor, 再绑定到 Qt 的渲染窗口
        self.viewer = vtk.vtkImageViewer2()
        self._apply_orientation()
        self._interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
        self.viewer.SetupInteractor(self._interactor)
        self.viewer.SetRenderWindow(self.vtk_widget.GetRenderWindow())

        self.renderer = self.viewer.GetRenderer()
        self.renderer.SetBackground(0.10, 0.10, 0.12)

        self.corner = vtk.vtkCornerAnnotation()
        self.corner.SetLinearFontScaleFactor(2)
        self.corner.SetMaximumFontSize(18)
        self.corner.SetText(2, self.label)
        self.renderer.AddViewProp(self.corner)

    # ---- 属性 ----
    @property
    def label(self):
        return self._LABELS[self.orientation]

    def _apply_orientation(self):
        if self.orientation == self.AXIAL:
            self.viewer.SetSliceOrientationToXY()
        elif self.orientation == self.CORONAL:
            self.viewer.SetSliceOrientationToXZ()
        else:
            self.viewer.SetSliceOrientationToYZ()

    # ---- 数据与显示 ----
    def set_image(self, image):
        self._image = image
        self.viewer.SetInputData(image)
        lo, hi = self.slice_range()
        self.viewer.SetSlice((lo + hi) // 2)
        self.renderer.ResetCamera()
        self._update_caption()

    def slice_range(self):
        return self.viewer.GetSliceMin(), self.viewer.GetSliceMax()

    def set_slice(self, idx):
        lo, hi = self.slice_range()
        self.viewer.SetSlice(int(max(lo, min(hi, idx))))
        self._update_caption()

    def get_slice(self):
        return self.viewer.GetSlice()

    def set_window_level(self, window, level):
        self.viewer.SetColorWindow(window)
        self.viewer.SetColorLevel(level)

    def _update_caption(self):
        _, hi = self.slice_range()
        self.corner.SetText(
            2, f"{self.label}  slice {self.viewer.GetSlice()}/{hi}"
        )

    def render(self):
        self.vtk_widget.GetRenderWindow().Render()
