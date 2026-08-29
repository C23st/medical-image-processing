"""四视图布局: Axial / Coronal / Sagittal + 3D。"""
from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QWidget

from .slice_view import SliceViewWidget
from .view3d import View3DWidget


class FourViewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.axial = SliceViewWidget(SliceViewWidget.AXIAL)
        self.coronal = SliceViewWidget(SliceViewWidget.CORONAL)
        self.sagittal = SliceViewWidget(SliceViewWidget.SAGITTAL)
        self.view3d = View3DWidget()

        layout.addWidget(self.axial, 0, 0)
        layout.addWidget(self.coronal, 0, 1)
        layout.addWidget(self.sagittal, 1, 0)
        layout.addWidget(self.view3d, 1, 1)

    def slice_views(self):
        return (self.axial, self.coronal, self.sagittal)

    def set_volume(self, volume, image=None):
        for view in self.slice_views():
            view.set_volume_data(volume.data, volume.spacing)
        # 复用外部传入的 vtk 图像, 避免重复拷贝 (降低内存)
        if image is None:
            image = volume.to_vtk_image(apply_direction=True)
        self.view3d.set_image(image)

    def set_labelmap(self, mask):
        for view in self.slice_views():
            view.set_labelmap(mask)

    def render_all(self):
        for view in (self.axial, self.coronal, self.sagittal, self.view3d):
            view.render()

    def reset_all(self):
        """重置所有视图的相机 (缩放/平移复位)。"""
        for view in (self.axial, self.coronal, self.sagittal, self.view3d):
            view.reset_view()
