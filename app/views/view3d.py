"""三维视图: 体数据包围盒 + 方向标记 + 面绘制/体绘制重建 (P5)。"""
from __future__ import annotations

import vtk
from PySide6.QtWidgets import QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor


class View3DWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = None
        self.outline_actor = None
        self._surface_actor = None
        self._volume_actor = None

        self.vtk_widget = QVTKRenderWindowInteractor(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.vtk_widget)

        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.12, 0.12, 0.14)
        self.renderer.SetBackground2(0.22, 0.22, 0.26)
        self.renderer.SetGradientBackground(True)
        self.renderer.GetActiveCamera().SetViewUp(0, 0, 1)  # Z 轴向上 (医学惯例)
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

    def reset_view(self):
        self.renderer.ResetCamera()
        self.render()

    def render(self):
        self.vtk_widget.GetRenderWindow().Render()

    # ---- 三维重建 ----
    def set_surface(self, image, threshold, color=(0.95, 0.90, 0.80)):
        """面绘制: Marching Cubes 提取等值面。"""
        self.clear_reconstruction()
        self._image = image

        mc = vtk.vtkFlyingEdges3D()
        mc.SetInputData(image)
        mc.SetValue(0, float(threshold))
        mc.ComputeNormalsOn()

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(mc.GetOutputPort())
        mapper.ScalarVisibilityOff()

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*color)
        actor.GetProperty().SetSpecular(0.35)
        actor.GetProperty().SetSpecularPower(20)
        self._surface_actor = actor
        self.renderer.AddActor(actor)
        self.renderer.ResetCamera()
        self.render()

    def set_volume_render(self, image, opacity=0.5):
        """体绘制: 光线投射 (vtkSmartVolumeMapper 自动选 GPU/CPU)。"""
        self.clear_reconstruction()
        self._image = image

        lo, hi = image.GetScalarRange()
        mid = (lo + hi) / 2.0

        ctf = vtk.vtkColorTransferFunction()
        ctf.AddRGBPoint(lo, 0.0, 0.0, 0.0)
        ctf.AddRGBPoint(mid, 0.78, 0.55, 0.42)
        ctf.AddRGBPoint(hi, 1.0, 1.0, 1.0)

        otf = vtk.vtkPiecewiseFunction()
        o = float(opacity)
        otf.AddPoint(lo, 0.0)
        otf.AddPoint(lo + (hi - lo) * 0.40, o * 0.08)
        otf.AddPoint(lo + (hi - lo) * 0.80, o * 0.65)
        otf.AddPoint(hi, o)

        prop = vtk.vtkVolumeProperty()
        prop.SetColor(ctf)
        prop.SetScalarOpacity(otf)
        prop.ShadeOn()
        prop.SetAmbient(0.3)
        prop.SetDiffuse(0.6)
        prop.SetSpecular(0.3)

        mapper = vtk.vtkSmartVolumeMapper()
        mapper.SetInputData(image)

        volume = vtk.vtkVolume()
        volume.SetMapper(mapper)
        volume.SetProperty(prop)
        self._volume_actor = volume
        self.renderer.AddVolume(volume)
        self.renderer.ResetCamera()
        self.render()

    def clear_reconstruction(self):
        """清除重建结果 (面绘制/体绘制)。"""
        if self._surface_actor is not None:
            self.renderer.RemoveActor(self._surface_actor)
            self._surface_actor = None
        if self._volume_actor is not None:
            self.renderer.RemoveVolume(self._volume_actor)
            self._volume_actor = None
        self.render()

    def has_reconstruction(self):
        return self._surface_actor is not None or self._volume_actor is not None
