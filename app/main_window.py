"""主窗口: 菜单栏 / 工具栏 / 四视图 / 数据树 / 参数面板 / 信息区。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMessageBox,
)

from .core import VolumeData, enhance
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
        self.volumes = []

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

    def _build_menus(self):
        menubar = self.menuBar()

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
        image = volume.to_vtk_image()

        self.four_view.set_image(image)
        self.info.set_patient(volume)
        self.params.set_window_level(volume.window, volume.level)
        self._on_window_level(volume.window, volume.level)
        self._update_info_slices()
        self.four_view.render_all()

    def _update_info_slices(self):
        parts = []
        for view in self.four_view.slice_views():
            _, hi = view.slice_range()
            parts.append(f"{view.label}: {view.get_slice()}/{hi}")
        self.info.set_slice(" | ".join(parts))

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
        """切换当前序列 (同时重置增强基准为原图)。"""
        self._base_volume = volume
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
        volume = VolumeData(
            data,
            spacing=base.spacing,
            origin=base.origin,
            modality=base.modality,
            patient=base.patient,
            series_description=f"{base.series_description} [{label}]",
        )
        self.set_volume(volume)
        QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"增强完成: {label}", 5000)

    def _on_enhance_reset(self):
        if self._base_volume is not None:
            self.set_volume(self._base_volume)
            self.statusBar().showMessage("已恢复原图", 3000)

    def _on_reset_view(self):
        self.four_view.render_all()
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
