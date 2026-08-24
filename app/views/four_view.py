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

    def set_image(self, image):
        self.axial.set_image(image)
        self.coronal.set_image(image)
        self.sagittal.set_image(image)
        self.view3d.set_image(image)

    def render_all(self):
        for view in (self.axial, self.coronal, self.sagittal, self.view3d):
            view.render()
