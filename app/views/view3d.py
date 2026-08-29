"""三维视图: 体数据包围盒 + 方向标记 + 面绘制/体绘制重建 (P5) + 切平面定位 (P6)。"""
from __future__ import annotations

import numpy as np
import vtk
from PySide6.QtWidgets import QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from ..widgets.view_toolbar import ViewToolbar
from .slice_view import map_window_level, to_vtk_2d


def _direction(image):
    """vtkImageData 方向矩阵 -> numpy 3x3 (列为 x/y/z 轴方向余弦)。"""
    M = np.eye(3)
    dm = image.GetDirectionMatrix()
    if dm is not None:
        for r in range(3):
            for c in range(3):
                M[r, c] = dm.GetElement(r, c)
    return M


def index_to_world(image, i, j, k):
    """体数据索引 (i,j,k) -> 世界坐标 (方向矩阵+origin+spacing)。"""
    ox, oy, oz = image.GetOrigin()
    sx, sy, sz = image.GetSpacing()
    v = np.array([i * sx, j * sy, k * sz])
    return np.array([ox, oy, oz]) + _direction(image) @ v


def compute_plane_specs(image, zyx, data):
    """计算三个正交切平面规格 (纯函数, 可无 GL 测试)。

    返回 [(slice2d, 法向轴, 切片索引, vec_a, vec_b), ...]:
      - vec_a: 平面沿"列"方向的向量 (纹理 u)
      - vec_b: 平面沿"行"方向的向量 (纹理 v)
    """
    z, y, x = zyx
    nx, ny, nz = image.GetDimensions()
    sx, sy, sz = image.GetSpacing()
    M = _direction(image)
    return [
        (data[z], 2, z, M[:, 0] * (nx * sx), M[:, 1] * (ny * sy)),   # Axial
        (data[:, y, :], 1, y, M[:, 0] * (nx * sx), M[:, 2] * (nz * sz)),  # Coronal
        (data[:, :, x], 0, x, M[:, 1] * (ny * sy), M[:, 2] * (nz * sz)),  # Sagittal
    ]


class View3DWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = None
        self.outline_actor = None
        self._surface_actor = None
        self._volume_actor = None
        self._planes = None
        self._plane_on = {"axial": False, "coronal": False, "sagittal": False}

        self.vtk_widget = QVTKRenderWindowInteractor(self)
        self.toolbar = ViewToolbar(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.toolbar)
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

    def set_standard_view(self, name):
        """按标准方位切换 3D 相机 (对应方向标记的 R/L/A/P/S/I)。"""
        # (相机位置方向, 视图向上参考)
        presets = {
            "前 (Anterior)": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            "后 (Posterior)": ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
            "右 (Right)": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
            "左 (Left)": ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
            "上 (Superior)": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
            "下 (Inferior)": ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
        }
        if name not in presets:
            return
        self._look_from(*presets[name])

    def _look_from(self, direction, up):
        """把相机放在 direction 指向的一侧, 看向可见物体包围盒中心。"""
        import math

        b = [0.0] * 6
        self.renderer.ComputeVisiblePropBounds(b)
        cx = (b[0] + b[1]) / 2
        cy = (b[2] + b[3]) / 2
        cz = (b[4] + b[5]) / 2
        half_diag = 0.5 * math.sqrt(
            (b[1] - b[0]) ** 2 + (b[3] - b[2]) ** 2 + (b[5] - b[4]) ** 2
        )
        dist = max(half_diag * 2.0, 1.0)
        dx, dy, dz = direction
        cam = self.renderer.GetActiveCamera()
        cam.SetFocalPoint(cx, cy, cz)
        cam.SetPosition(cx + dx * dist, cy + dy * dist, cz + dz * dist)
        cam.SetViewUp(*up)
        cam.OrthogonalizeViewUp()
        cam.SetClippingRange(0.01, dist * 10)
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

    # ---- 二维切片平面定位 (P6) ----
    def set_slice_planes(self, zyx, image, data, window, level):
        """显示三个正交切平面 (位置 + CT 图像纹理), 随切片索引移动。"""
        specs = compute_plane_specs(image, zyx, data)
        if self._planes is None:
            self._planes = [self._new_plane() for _ in specs]
        for (actor, plane_src), (slice2d, axis, idx, va, vb) in zip(self._planes, specs):
            self._update_plane(actor, plane_src, slice2d, image, axis, idx, va, vb, window, level)
        self.render()

    def _new_plane(self):
        plane = vtk.vtkPlaneSource()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(plane.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.SetTexture(vtk.vtkTexture())
        actor.GetProperty().SetOpacity(0.65)
        actor.GetProperty().SetAmbient(1.0)  # 纹理原样显示, 不受光照
        actor.GetProperty().SetDiffuse(0.0)
        actor.VisibilityOff()
        self.renderer.AddActor(actor)
        return (actor, plane)

    def _update_plane(self, actor, plane_src, slice2d, image, axis, idx, va, vb, window, level):
        origin = index_to_world(
            image, *[idx if a == axis else 0 for a in range(3)]
        )
        plane_src.SetOrigin(*origin)
        plane_src.SetPoint1(*(origin + va))
        plane_src.SetPoint2(*(origin + vb))
        tex_img = to_vtk_2d(map_window_level(slice2d, window, level), (1.0, 1.0))
        actor.GetTexture().SetInputData(tex_img)
        axis_name = {2: "axial", 1: "coronal", 0: "sagittal"}[axis]
        actor.SetVisibility(1 if self._plane_on.get(axis_name, False) else 0)

    def set_plane_visible(self, axis, on):
        """单独开关某个切平面 (axis: axial/coronal/sagittal)。"""
        if axis not in self._plane_on:
            return
        self._plane_on[axis] = bool(on)
        if self._planes is not None:
            idx = {"axial": 0, "coronal": 1, "sagittal": 2}[axis]
            actor, _p = self._planes[idx]
            actor.SetVisibility(1 if self._plane_on[axis] else 0)
        self.render()

    def is_plane_visible(self, axis):
        return self._plane_on.get(axis, False)

    def any_plane_visible(self):
        return any(self._plane_on.values())

    def clear_slice_planes(self):
        for a, _p in (self._planes or []):
            self.renderer.RemoveActor(a)
        self._planes = None
        self.render()
