"""右侧参数面板: 显示 / 增强 / 分割 / 三维重建 分页。"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import enhance


class ParamsPanel(QTabWidget):
    """参数分页面板。"""

    window_changed = Signal(float, float)  # (window, level)
    enhance_apply = Signal(str, dict)      # (method_key, params)
    enhance_reset = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_display_tab()
        self._build_enhance_tab()
        self._build_placeholder_tab("分割", "阈值分割 / 区域生长 / Otsu\n(将在 P4 阶段实现)")
        self._build_placeholder_tab("三维重建", "面绘制 (Marching Cubes) + 体绘制\n(将在 P5 阶段实现)")

    # ---- 显示页 ----
    def _build_display_tab(self):
        tab = QWidget()
        self.addTab(tab, "显示")
        layout = QVBoxLayout(tab)

        box = QGroupBox("窗宽窗位 (WW/WL)")
        form = QFormLayout(box)
        self.ww_spin = QDoubleSpinBox()
        self.ww_spin.setRange(1.0, 100000.0)
        self.ww_spin.setValue(400.0)
        self.ww_spin.setSingleStep(10.0)
        self.wl_spin = QDoubleSpinBox()
        self.wl_spin.setRange(-100000.0, 100000.0)
        self.wl_spin.setValue(40.0)
        self.wl_spin.setSingleStep(10.0)
        self.ww_spin.valueChanged.connect(self._emit_window_level)
        self.wl_spin.valueChanged.connect(self._emit_window_level)
        form.addRow("窗宽 WW", self.ww_spin)
        form.addRow("窗位 WL", self.wl_spin)
        layout.addWidget(box)
        layout.addStretch(1)

    def _emit_window_level(self):
        self.window_changed.emit(self.ww_spin.value(), self.wl_spin.value())

    def set_window_level(self, window, level):
        self.ww_spin.blockSignals(True)
        self.wl_spin.blockSignals(True)
        self.ww_spin.setValue(window)
        self.wl_spin.setValue(level)
        self.ww_spin.blockSignals(False)
        self.wl_spin.blockSignals(False)

    # ---- 增强页 ----
    def _build_enhance_tab(self):
        tab = QWidget()
        self.addTab(tab, "增强")
        layout = QVBoxLayout(tab)

        box = QGroupBox("图像增强")
        form = QFormLayout(box)
        self._enhance_form = form

        self.method_combo = QComboBox()
        for key, (label, _func, _defaults) in enhance.METHODS.items():
            self.method_combo.addItem(label, key)
        form.addRow("方法", self.method_combo)

        self.gamma_spin = QDoubleSpinBox()
        self.gamma_spin.setRange(0.1, 5.0)
        self.gamma_spin.setValue(1.0)
        self.gamma_spin.setSingleStep(0.1)
        self.clip_spin = QDoubleSpinBox()
        self.clip_spin.setRange(0.005, 0.2)
        self.clip_spin.setValue(0.02)
        self.clip_spin.setSingleStep(0.005)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(3, 15)
        self.size_spin.setSingleStep(2)
        self.size_spin.setValue(3)
        self.sigma_spin = QDoubleSpinBox()
        self.sigma_spin.setRange(0.1, 10.0)
        self.sigma_spin.setValue(1.0)
        self.sigma_spin.setSingleStep(0.1)
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.1, 5.0)
        self.amount_spin.setValue(1.0)
        self.amount_spin.setSingleStep(0.1)

        self._param_rows = {
            "gamma": self._add_row(form, "γ (gamma)", self.gamma_spin),
            "clip": self._add_row(form, "clip_limit", self.clip_spin),
            "size": self._add_row(form, "核大小", self.size_spin),
            "sigma": self._add_row(form, "σ (sigma)", self.sigma_spin),
            "amount": self._add_row(form, "锐化量", self.amount_spin),
        }
        layout.addWidget(box)

        self.apply_btn = QPushButton("应用增强")
        self.reset_btn = QPushButton("恢复原图")
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.reset_btn)
        layout.addLayout(btn_row)
        layout.addStretch(1)

        self.method_combo.currentIndexChanged.connect(self._update_param_visibility)
        self.apply_btn.clicked.connect(self._emit_enhance_apply)
        self.reset_btn.clicked.connect(self.enhance_reset)
        self._update_param_visibility()

    def _add_row(self, form, label, widget):
        form.addRow(label, widget)
        return form.rowCount() - 1

    # 每个方法需要显示的参数行
    _VISIBLE = {
        "gamma": {"gamma"},
        "clahe": {"clip"},
        "mean": {"size"},
        "median": {"size"},
        "gaussian": {"sigma"},
        "sharpen": {"amount"},
    }

    def _update_param_visibility(self):
        key = self.method_combo.currentData()
        visible = self._VISIBLE.get(key, set())
        for name, row in self._param_rows.items():
            self._enhance_form.setRowVisible(row, name in visible)

    def _emit_enhance_apply(self):
        key = self.method_combo.currentData()
        params = {}
        if key == "gamma":
            params["gamma"] = self.gamma_spin.value()
        elif key == "clahe":
            params["clip_limit"] = self.clip_spin.value()
        elif key in ("mean", "median"):
            params["size"] = int(self.size_spin.value())
        elif key == "gaussian":
            params["sigma"] = self.sigma_spin.value()
        elif key == "sharpen":
            params["amount"] = self.amount_spin.value()
        self.enhance_apply.emit(key, params)

    # ---- 占位页 ----
    def _build_placeholder_tab(self, title, text):
        tab = QWidget()
        self.addTab(tab, title)
        layout = QVBoxLayout(tab)
        box = QGroupBox(f"{title}参数")
        box_layout = QVBoxLayout(box)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color: #9aa0a6;")
        box_layout.addWidget(label)
        layout.addWidget(box)
        layout.addStretch(1)
