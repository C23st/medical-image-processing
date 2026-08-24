"""三维视图 (P1: 体数据边界框 + 方向标记; P5: 面绘制/体绘制; P6: 切平面)。"""
from __future__ import annotations

import vtk
from PySide6.QtWidgets import QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor


class View3DWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = None
        self.outline_actor = None

        self.vtk_widget = QVTKRenderWindowInteractor(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.vtk_widget)

        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.12, 0.12, 0.14)
        self.renderer.SetBackground2(0.22, 0.22, 0.26)
        self.renderer.SetGradientBackground(True)
        self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)

        self._interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
        self._interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())

        # 角标
        self.corner = vtk.vtkCornerAnnotation()
        self.corner.SetLinearFontScaleFactor(2)
        self.corner.SetMaximumFontSize(18)
        self.corner.SetText(2, "3D")
        self.renderer.AddViewProp(self.corner)

        # 方向标记 (左下角坐标轴, 随相机旋转)
        axes_actor = vtk.vtkAxesActor()
        self.orientation_marker = vtk.vtkOrientationMarkerWidget()
        self.orientation_marker.SetOrientationMarker(axes_actor)
        self.orientation_marker.SetInteractor(self._interactor)
        self.orientation_marker.SetViewport(0.0, 0.0, 0.22, 0.22)
        self.orientation_marker.SetEnabled(1)

    # ---- 数据与显示 ----
    def set_image(self, image):
        self._image = image
        if self.outline_actor is not None:
            self.renderer.RemoveActor(self.outline_actor)

        outline = vtk.vtkOutlineSource()
        outline.SetBounds(image.GetBounds())
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(outline.GetOutputPort())
        self.outline_actor = vtk.vtkActor()
        self.outline_actor.SetMapper(mapper)
        self.outline_actor.GetProperty().SetColor(0.35, 0.62, 0.92)
        self.outline_actor.GetProperty().SetLineWidth(1.5)
        self.renderer.AddActor(self.outline_actor)
        self.renderer.ResetCamera()

    def render(self):
        self.vtk_widget.GetRenderWindow().Render()
