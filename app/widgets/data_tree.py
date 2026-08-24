"""左侧数据树: 病人-序列 层级展示, 双击序列切换到对应体数据。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem


class DataTreeWidget(QTreeWidget):
    series_selected = Signal(int)  # 对应 volumes 列表中的下标

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["数据", "信息"])
        self.setAlternatingRowColors(True)
        self.itemDoubleClicked.connect(self._on_double_click)

    def populate(self, volumes):
        self.clear()
        by_patient = {}
        for i, vol in enumerate(volumes):
            pid = vol.patient.get("id", "Unknown")
            by_patient.setdefault(pid, []).append((i, vol))

        for pid, items in by_patient.items():
            name = items[0][1].patient.get("name", pid)
            p_item = QTreeWidgetItem([f"病人: {name}", pid])

            for i, vol in items:
                desc = vol.series_description or vol.modality
                s_item = QTreeWidgetItem(
                    [f"序列 {vol.patient.get('series_number', '?')}: {desc}", vol.modality]
                )
                s_item.setData(0, Qt.UserRole, i)

                z, y, x = vol.shape
                sx, sy, sz = vol.spacing
                s_item.addChild(QTreeWidgetItem(["尺寸 (z,y,x)", f"{z} x {y} x {x}"]))
                s_item.addChild(QTreeWidgetItem(["间距 (x,y,z)", f"{sx:.2f} x {sy:.2f} x {sz:.2f}"]))
                s_item.addChild(QTreeWidgetItem(["WW/WL", f"{vol.window:.0f}/{vol.level:.0f}"]))
                p_item.addChild(s_item)

            self.addTopLevelItem(p_item)
        self.expandAll()

    def _on_double_click(self, item, column):
        idx = item.data(0, Qt.UserRole)
        if idx is not None:
            self.series_selected.emit(int(idx))
