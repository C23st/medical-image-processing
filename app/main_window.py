"""主窗口: 菜单栏 / 工具栏 / 四视图 / 数据树 / 参数面板 / 信息区。"""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QToolButton,
)

from .core import VolumeData, enhance, segment
from .core.dicom_loader import load_dicom_series
from .core.synthetic import synthetic_ct_phantom
from .views.four_view import FourViewWidget
from .widgets.data_tree import DataTreeWidget
from .widgets.info_bar import InfoBar
from .widgets.params_panel import ParamsPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("医学图像处理平台")
        self.resize(1400, 900)
        self._volume = None
        self._base_volume = None
        self._mask = None
        self._seed = None
        self.volumes = []
        self._crosshair = None
        self._show_crosshair = False
        self._crosshair_action = None
        self._show_planes = False
        self._planes_action = None
        self._vtk_image = None

        self._build_central()
        self._build_docks()
        self._build_menus()
        self._build_toolbar()
        self._build_statusbar()

        self._load_synthetic()

    # ---- UI 构建 ----
    def _build_central(self):
        self.four_view = FourViewWidget()
        self.setCentralWidget(self.four_view)
        for view in self.four_view.slice_views():
            view.slice_changed.connect(partial(self._on_slice_changed, view))
            view.picked.connect(self._on_picked)
            view.crosshair_moved.connect(partial(self._on_crosshair_moved, view))
            view.hovered.connect(self._on_hovered)

    def _build_docks(self):
        self.tree = DataTreeWidget()
        dock_left = QDockWidget("数据", self)
        dock_left.setWidget(self.tree)
        dock_left.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock_left)

        self.params = ParamsPanel()
        dock_right = QDockWidget("参数", self)
        dock_right.setWidget(self.params)
        self.addDockWidget(Qt.RightDockWidgetArea, dock_right)

        self.info = InfoBar()
        dock_bottom = QDockWidget("信息", self)
        dock_bottom.setWidget(self.info)
        dock_bottom.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        )
        self.addDockWidget(Qt.BottomDockWidgetArea, dock_bottom)

        self.params.window_changed.connect(self._on_window_level)
        self.tree.series_selected.connect(self._on_series_selected)
        self.params.enhance_apply.connect(self._on_enhance_apply)
        self.params.enhance_reset.connect(self._on_enhance_reset)
        self.params.segment_apply.connect(self._on_segment_apply)
        self.params.segment_clear.connect(self._on_segment_clear)
        self.params.reconstruct_apply.connect(self._on_reconstruct_apply)
        self.params.reconstruct_clear.connect(self._on_reconstruct_clear)

    def _build_menus(self):
        menubar = self.menuBar()
        self._build_view3d_actions()

        # 文件
        m_file = menubar.addMenu("文件(&F)")
        act_open = QAction("打开 DICOM 文件夹...", self)
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self._on_open)
        act_exit = QAction("退出", self)
        act_exit.setShortcut(QKeySequence.Quit)
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_open)
        m_file.addSeparator()
        m_file.addAction(act_exit)

        # 视图
        m_view = menubar.addMenu("视图(&V)")
        act_reset = QAction("重置视图", self)
        act_reset.triggered.connect(self._on_reset_view)
        m_view.addAction(act_reset)
        self._crosshair_action = QAction("十字准星", self)
        self._crosshair_action.setCheckable(True)
        self._crosshair_action.setChecked(False)
        self._crosshair_action.toggled.connect(self._on_toggle_crosshair)
        m_view.addAction(self._crosshair_action)
        self._planes_action = QAction("切片平面 (3D)", self)
        self._planes_action.setCheckable(True)
        self._planes_action.setChecked(False)
        self._planes_action.toggled.connect(self._on_toggle_slice_planes)
        m_view.addAction(self._planes_action)

        m_view3d = m_view.addMenu("3D 视角")
        for act in self._view3d_actions.values():
            m_view3d.addAction(act)

        # 功能占位菜单
        self._placeholder_menu(menubar, "分割(&S)")
        self._placeholder_menu(menubar, "增强(&E)")
        self._placeholder_menu(menubar, "三维重建(&R)")

        # 帮助
        m_help = menubar.addMenu("帮助(&H)")
        act_about = QAction("关于", self)
        act_about.triggered.connect(self._on_about)
        m_help.addAction(act_about)

    def _placeholder_menu(self, menubar, title):
        menu = menubar.addMenu(title)
        act = QAction("(待实现)", self)
        act.setEnabled(False)
        menu.addAction(act)

    def _build_view3d_actions(self):
        """创建 3D 视角相关动作 (复位 + 6 个标准方位)。"""
        self._view3d_actions = {}
        self._view3d_actions["复位视角"] = QAction("复位视角", self)
        self._view3d_actions["复位视角"].triggered.connect(self._on_reset_3d)
        for name in (
            "前 (Anterior)", "后 (Posterior)", "右 (Right)",
            "左 (Left)", "上 (Superior)", "下 (Inferior)",
        ):
            act = QAction(name, self)
            act.triggered.connect(lambda _=False, n=name: self._on_std_3d(n))
            self._view3d_actions[name] = act

    def _on_reset_3d(self):
        self.four_view.view3d.reset_view()
        self.statusBar().showMessage("3D 视角已复位", 2000)

    def _on_std_3d(self, name):
        self.four_view.view3d.set_standard_view(name)
        self.statusBar().showMessage(f"3D 视角: {name}", 2000)

    def _build_toolbar(self):
        tb = self.addToolBar("主工具栏")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        def add(text, slot=None, enabled=True):
            act = QAction(text, self)
            act.setEnabled(enabled)
            if slot is not None:
                act.triggered.connect(slot)
            tb.addAction(act)
            return act

        add("打开", self._on_open)
        tb.addSeparator()
        tb.addAction(self._crosshair_action)
        tb.addAction(self._planes_action)
        tb.addSeparator()
        view_btn = QToolButton()
        view_btn.setText("3D 视角")
        view_btn.setPopupMode(QToolButton.InstantPopup)
        view_menu = QMenu(view_btn)
        for act in self._view3d_actions.values():
            view_menu.addAction(act)
        view_btn.setMenu(view_menu)
        tb.addWidget(view_btn)
        tb.addSeparator()
        add("窗宽窗位", None, False)
        add("缩放", None, False)
        add("分割", None, False)
        add("增强", None, False)
        add("重建", None, False)

    def _build_statusbar(self):
        self.statusBar().showMessage("就绪 | 已加载合成体数据")

    # ---- 数据加载 ----
    def _load_synthetic(self):
        data = synthetic_ct_phantom()
        volume = VolumeData(
            data,
            spacing=(1.0, 1.0, 1.2),
            modality="CT",
            patient={"name": "Synthetic Phantom", "id": "SYN-0001"},
            series_description="Synthetic Phantom",
        )
        self.load_volumes([volume])

    def load_volumes(self, volumes):
        if not volumes:
            return
        self.volumes = volumes
        self.tree.populate(volumes)
        self._activate_volume(volumes[0])

    def set_volume(self, volume):
        self._volume = volume
        self._vtk_image = volume.to_vtk_image(apply_direction=True)
        self.four_view.set_volume(volume)
        self.info.set_patient(volume)
        self.params.set_window_level(volume.window, volume.level)
        self._on_window_level(volume.window, volume.level)
        self._update_info_slices()
        self._update_3d_planes()
        self.four_view.render_all()

    def _update_info_slices(self):
        parts = []
        for view in self.four_view.slice_views():
            _, hi = view.slice_range()
            parts.append(f"{view.label}: {view.get_slice()}/{hi}")
        self.info.set_slice(" | ".join(parts))

    # ---- 切片变化 ----
    def _on_slice_changed(self, view, new_index):
        self._update_info_slices()
        self._update_3d_planes()

    # ---- 3D 切平面 ----
    def _update_3d_planes(self):
        """按当前三视图切片索引更新 3D 切平面 (开关开启时)。"""
        if self._volume is None or self._show_planes is False:
            return
        z = self.four_view.axial.get_slice()
        y = self.four_view.coronal.get_slice()
        x = self.four_view.sagittal.get_slice()
        self.four_view.view3d.set_slice_planes(
            (z, y, x), self._vtk_image, self._volume.data,
            self._volume.window, self._volume.level,
        )

    def _on_toggle_slice_planes(self, checked):
        self._show_planes = bool(checked)
        self.four_view.view3d.show_slice_planes(self._show_planes)
        if checked:
            self._update_3d_planes()
        self.statusBar().showMessage(
            "3D 切平面已开启" if checked else "3D 切平面已关闭", 2000
        )

    # ---- 十字准星联动 ----
    def _on_crosshair_moved(self, view, z, y, x):
        """Shift+移动: 以鼠标处 3D 点为中心, 其余两视图实时跳层。"""
        if self._base_volume is None:
            return
        self._crosshair = (z, y, x)
        axial, coronal, sagittal = self.four_view.slice_views()
        if view is axial:
            coronal.set_slice(y)
            sagittal.set_slice(x)
        elif view is coronal:
            axial.set_slice(z)
            sagittal.set_slice(x)
        else:  # sagittal
            axial.set_slice(z)
            coronal.set_slice(y)

        for v in self.four_view.slice_views():
            v.set_crosshair((z, y, x))
        self.statusBar().showMessage(self._crosshair_status(z, y, x), 3000)

    def _on_toggle_crosshair(self, checked):
        self._show_crosshair = bool(checked)
        for v in self.four_view.slice_views():
            v.set_show_crosshair(self._show_crosshair)
        if not checked:
            self._crosshair = None
        self.statusBar().showMessage(
            "十字准星已开启 (Shift+移动鼠标联动)" if checked else "十字准星已关闭", 2000
        )

    def _crosshair_status(self, z, y, x):
        vol = self._base_volume
        if vol is None:
            return f"定位点 z={z} y={y} x={x}"
        try:
            r, a, s = vol.index_to_ras(z, y, x)
            return f"定位点 z={z} y={y} x={x} | RAS=({r:.1f}, {a:.1f}, {s:.1f}) mm"
        except Exception:  # noqa: BLE001
            return f"定位点 z={z} y={y} x={x}"

    # ---- 槽 ----
    def _on_open(self):
        directory = QFileDialog.getExistingDirectory(
            self, "选择 DICOM 序列文件夹", ""
        )
        if not directory:
            return
        volumes = load_dicom_series(directory)
        if not volumes:
            QMessageBox.warning(self, "打开 DICOM", "未在该目录找到含图像数据的 DICOM 序列。")
            return
        self.load_volumes(volumes)
        self.statusBar().showMessage(f"已加载 {len(volumes)} 个序列: {directory}", 5000)

    def _on_series_selected(self, index):
        if 0 <= index < len(self.volumes):
            self._activate_volume(self.volumes[index])
            self.statusBar().showMessage(
                f"当前序列: {self.volumes[index].series_description or self.volumes[index].modality}",
                3000,
            )

    def _activate_volume(self, volume):
        """切换当前序列 (重置增强基准与分割结果)。"""
        self._base_volume = volume
        self._mask = None
        self._seed = None
        self._crosshair = None
        self.four_view.set_labelmap(None)
        self.four_view.view3d.clear_slice_planes()
        for v in self.four_view.slice_views():
            v.set_crosshair(None)
        self.set_volume(volume)

    def _on_enhance_apply(self, method, params):
        if self._base_volume is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage("增强处理中...")
        try:
            data = enhance.apply(self._base_volume.data, method, params)
        except Exception as e:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "增强", f"处理失败: {e}")
            return

        base = self._base_volume
        label = enhance.METHODS[method][0]
        if enhance.preserves_range(method):
            # 滤波类: 保持原始窗宽窗位 (HU 语义不变)
            window, level = base.window, base.level
        else:
            # 归一化类: 自动按新数据范围 (通常变为 255/128)
            window, level = None, None
        volume = VolumeData(
            data,
            spacing=base.spacing,
            origin=base.origin,
            modality=base.modality,
            patient=base.patient,
            window=window,
            level=level,
            series_description=f"{base.series_description} [{label}]",
        )
        self.set_volume(volume)
        if self._mask is not None:
            self.four_view.set_labelmap(self._mask)
        QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"增强完成: {label}", 5000)

    def _on_enhance_reset(self):
        if self._base_volume is not None:
            self.set_volume(self._base_volume)
            self.statusBar().showMessage("已恢复原图", 3000)

    # ---- 分割 ----
    def _on_segment_apply(self, method, params):
        if self._base_volume is None:
            return
        data = self._base_volume.data
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage("分割处理中...")
        extra = ""
        try:
            if method == "threshold":
                mask = segment.threshold(data, params.get("threshold", 100.0))
            elif method == "otsu":
                mask, t = segment.otsu(data)
                extra = f" (Otsu 阈值 {t:.1f} HU)"
            elif method == "region_growing":
                if self._seed is None:
                    QApplication.restoreOverrideCursor()
                    QMessageBox.information(
                        self, "区域生长", "请先在切片视图上点击, 设置种子点后再应用。"
                    )
                    return
                mask = segment.region_growing(
                    data, self._seed, params.get("tol", 30.0)
                )
            else:
                QApplication.restoreOverrideCursor()
                return
        except Exception as e:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "分割", f"分割失败: {e}")
            return

        self._mask = mask
        self.four_view.set_labelmap(mask)
        dice_txt = self._compute_dice(mask)
        QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"分割完成{extra}{dice_txt}", 5000)

    def _on_segment_clear(self):
        self._mask = None
        self.four_view.set_labelmap(None)
        self.statusBar().showMessage("已清除分割结果", 3000)

    # ---- 三维重建 ----
    def _on_reconstruct_apply(self, method, params):
        if self._volume is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage("三维重建处理中...")
        try:
            image = self._volume.to_vtk_image(apply_direction=True)
            if method == "surface":
                threshold = params.get("threshold", 300.0)
                self.four_view.view3d.set_surface(image, threshold)
                label = f"面绘制 阈值 {threshold:.0f}"
            else:
                opacity = params.get("opacity", 0.5)
                self.four_view.view3d.set_volume_render(image, opacity)
                label = f"体绘制 不透明度 {opacity:.2f}"
        except Exception as e:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "三维重建", f"重建失败: {e}")
            return
        QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"重建完成: {label}", 5000)

    def _on_reconstruct_clear(self):
        self.four_view.view3d.clear_reconstruction()
        self.statusBar().showMessage("已清除三维重建", 3000)

    def _on_picked(self, z, y, x):
        self._seed = (z, y, x)
        if self._base_volume is not None:
            val = float(self._base_volume.data[z, y, x])
            self.info.set_value(f"{val:.1f}")
        self.statusBar().showMessage(f"拾取点: 层{z}, y={y}, x={x}", 3000)

    def _on_hovered(self, z, y, x):
        """实时显示鼠标位置与体素值 (无需点击)。"""
        if self._base_volume is None:
            return
        val = float(self._base_volume.data[z, y, x])
        self.info.set_hover(z, y, x, val)

    def _compute_dice(self, mask):
        """与同病人 SEG 真值计算 Dice (有则返回提示文本)。"""
        if self._base_volume is None:
            return ""
        pid = self._base_volume.patient.get("id")
        seg_vol = next(
            (
                v
                for v in self.volumes
                if v.modality == "SEG" and v.patient.get("id") == pid
            ),
            None,
        )
        if seg_vol is None:
            return ""
        try:
            gt = segment.match_seg_to_ct(seg_vol, self._base_volume)
            d = segment.dice(mask, gt)
        except Exception:  # noqa: BLE001
            return ""
        return f" | 与胰腺真值 Dice={d:.3f}"

    def _on_reset_view(self):
        self.four_view.reset_all()
        self.statusBar().showMessage("视图已重置", 3000)

    def _on_window_level(self, window, level):
        for view in self.four_view.slice_views():
            view.set_window_level(window, level)
            view.render()
        self.info.set_wwl(window, level)

    def _on_about(self):
        QMessageBox.about(
            self,
            "关于",
            "医学图像处理平台 v0.2\n"
            "期末大作业\n"
            "功能: DICOM 打开/解读/显示 + 增强 + 分割 + 三维重建\n"
            "技术栈: PySide6 + VTK",
        )
