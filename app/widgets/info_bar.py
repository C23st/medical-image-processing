"""底部信息区: 病人信息 / 切片 / 体素值 / 窗宽窗位。"""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel


class InfoBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.lbl_patient = self._add(layout, "病人: -")
        self.lbl_modality = self._add(layout, "模态: -")
        self.lbl_size = self._add(layout, "尺寸: -")
        self.lbl_slice = self._add(layout, "切片: -")
        self.lbl_value = self._add(layout, "体素值: -")
        self.lbl_wwl = self._add(layout, "WW/WL: -")
        layout.addStretch(1)

    @staticmethod
    def _add(layout, text):
        label = QLabel(text)
        label.setMinimumWidth(90)
        layout.addWidget(label)
        return label

    def set_patient(self, volume):
        p = volume.patient
        self.lbl_patient.setText(f"病人: {p.get('name', 'Synthetic')} ({p.get('id', '-')})")
        self.lbl_modality.setText(f"模态: {volume.modality}")
        z, y, x = volume.shape
        self.lbl_size.setText(f"尺寸: {x}x{y}x{z}")

    def set_slice(self, text):
        self.lbl_slice.setText(f"切片: {text}")

    def set_value(self, text):
        self.lbl_value.setText(f"体素值: {text}")

    def set_wwl(self, window, level):
        self.lbl_wwl.setText(f"WW/WL: {window:.0f}/{level:.0f}")
