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
    segment_apply = Signal(str, dict)      # (method_key, params)
    segment_clear = Signal()
    reconstruct_apply = Signal(str, dict)  # (method_key, params)
    reconstruct_clear = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_display_tab()
        self._build_enhance_tab()
        self._build_segmentation_tab()
        self._build_reconstruct_tab()

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

        self.history_label = QLabel("已应用: 无")
        self.history_label.setWordWrap(True)
        self.history_label.setStyleSheet("color: #9aa0a6;")
        layout.addWidget(self.history_label)
        layout.addStretch(1)

        self.method_combo.currentIndexChanged.connect(self._update_param_visibility)
        self.apply_btn.clicked.connect(self._emit_enhance_apply)
        self.reset_btn.clicked.connect(self.enhance_reset)
        self._update_param_visibility()

    def set_enhance_history(self, text):
        """显示已叠加的增强链 (如: 线性拉伸 → 伽马变换)。"""
        self.history_label.setText(f"已应用: {text}")

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

    # ---- 分割页 ----
    def _build_segmentation_tab(self):
        tab = QWidget()
        self.addTab(tab, "分割")
        layout = QVBoxLayout(tab)

        box = QGroupBox("分割方法")
        form = QFormLayout(box)
        self._seg_form = form
        self.seg_combo = QComboBox()
        self.seg_combo.addItem("阈值分割", "threshold")
        self.seg_combo.addItem("Otsu 自动阈值", "otsu")
        self.seg_combo.addItem("区域生长", "region_growing")
        form.addRow("方法", self.seg_combo)

        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(-2000.0, 3000.0)
        self.thresh_spin.setValue(100.0)
        self.thresh_spin.setSingleStep(10.0)
        form.addRow("阈值 (HU)", self.thresh_spin)
        self._thresh_row = form.rowCount() - 1

        self.tol_spin = QDoubleSpinBox()
        self.tol_spin.setRange(1.0, 300.0)
        self.tol_spin.setValue(30.0)
        self.tol_spin.setSingleStep(5.0)
        form.addRow("生长容差 (HU)", self.tol_spin)
        self._tol_row = form.rowCount() - 1
        layout.addWidget(box)

        hint = QLabel(
            "阈值分割: 保留强度 >= 阈值的体素\n"
            "Otsu: 自动计算全局阈值\n"
            "区域生长: 先在切片视图点击设置种子点, 再应用"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9aa0a6;")
        layout.addWidget(hint)

        self.seg_apply_btn = QPushButton("应用分割")
        self.seg_clear_btn = QPushButton("清除分割")
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.seg_apply_btn)
        btn_row.addWidget(self.seg_clear_btn)
        layout.addLayout(btn_row)
        layout.addStretch(1)

        self.seg_apply_btn.clicked.connect(self._emit_segment_apply)
        self.seg_clear_btn.clicked.connect(self.segment_clear)
        self.seg_combo.currentIndexChanged.connect(self._update_seg_param_visibility)
        self._update_seg_param_visibility()

    def _update_seg_param_visibility(self):
        """按方法显示相关参数: 阈值仅阈值分割用, 生长容差仅区域生长用。"""
        method = self.seg_combo.currentData()
        self._seg_form.setRowVisible(self._thresh_row, method == "threshold")
        self._seg_form.setRowVisible(self._tol_row, method == "region_growing")

    def _emit_segment_apply(self):
        key = self.seg_combo.currentData()
        params = {
            "threshold": self.thresh_spin.value(),
            "tol": self.tol_spin.value(),
        }
        self.segment_apply.emit(key, params)

    # ---- 三维重建页 ----
    def _build_reconstruct_tab(self):
        tab = QWidget()
        self.addTab(tab, "三维重建")
        layout = QVBoxLayout(tab)

        box = QGroupBox("重建方式")
        form = QFormLayout(box)
        self._recon_form = form
        self.recon_combo = QComboBox()
        self.recon_combo.addItem("面绘制 (Marching Cubes)", "surface")
        self.recon_combo.addItem("体绘制 (Ray Casting)", "volume")
        form.addRow("方式", self.recon_combo)

        self.thresh_recon_spin = QDoubleSpinBox()
        self.thresh_recon_spin.setRange(-2000.0, 3000.0)
        self.thresh_recon_spin.setValue(300.0)
        self.thresh_recon_spin.setSingleStep(10.0)
        form.addRow("等值面阈值 (HU)", self.thresh_recon_spin)
        self._recon_thresh_row = form.rowCount() - 1

        preset_row = QHBoxLayout()
        for label, val in (("骨", 300.0), ("软组织", 40.0), ("皮肤", -150.0), ("掩膜", 0.5)):
            b = QPushButton(label)
            b.setFixedWidth(52)
            b.clicked.connect(lambda _=False, v=val: self.thresh_recon_spin.setValue(v))
            preset_row.addWidget(b)
        form.addRow("预设", preset_row)
        self._recon_preset_row = form.rowCount() - 1

        self.opacity_spin = QDoubleSpinBox()
        self.opacity_spin.setRange(0.05, 1.0)
        self.opacity_spin.setValue(0.5)
        self.opacity_spin.setSingleStep(0.05)
        form.addRow("不透明度", self.opacity_spin)
        self._recon_opacity_row = form.rowCount() - 1
        layout.addWidget(box)

        hint = QLabel(
            "面绘制: 提取等值面, 适合骨骼/皮肤/分割掩膜\n"
            "体绘制: 光线投射, 适合软组织/血管\n"
            "预设按钮快速设阈值 (骨/软组织/皮肤/掩膜)"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9aa0a6;")
        layout.addWidget(hint)

        self.recon_apply_btn = QPushButton("应用重建")
        self.recon_clear_btn = QPushButton("清除重建")
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.recon_apply_btn)
        btn_row.addWidget(self.recon_clear_btn)
        layout.addLayout(btn_row)
        layout.addStretch(1)

        self.recon_combo.currentIndexChanged.connect(self._update_recon_param_visibility)
        self.recon_apply_btn.clicked.connect(self._emit_reconstruct_apply)
        self.recon_clear_btn.clicked.connect(self.reconstruct_clear)
        self._update_recon_param_visibility()

    def _update_recon_param_visibility(self):
        is_surface = self.recon_combo.currentData() == "surface"
        self._recon_form.setRowVisible(self._recon_thresh_row, is_surface)
        self._recon_form.setRowVisible(self._recon_preset_row, is_surface)
        self._recon_form.setRowVisible(self._recon_opacity_row, not is_surface)

    def _emit_reconstruct_apply(self):
        method = self.recon_combo.currentData()
        if method == "surface":
            params = {"threshold": self.thresh_recon_spin.value()}
        else:
            params = {"opacity": self.opacity_spin.value()}
        self.reconstruct_apply.emit(method, params)

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
