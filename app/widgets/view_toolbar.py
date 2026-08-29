"""视图左上角图标工具栏: 小图标按钮 + 悬停 tooltip。"""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QToolButton, QWidget


class ViewToolbar(QWidget):
    """一行紧凑的图标按钮, 用于叠加在视图顶部 (按钮左对齐)。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(1)
        self._layout = layout
        self._layout.addStretch(1)  # 占位, 使按钮靠左

    def add_action(self, action):
        """把 QAction 加入工具栏 (图标/文字 + tooltip), 返回 QToolButton。"""
        btn = QToolButton(self)
        btn.setDefaultAction(action)
        btn.setAutoRaise(True)
        self._layout.insertWidget(self._layout.count() - 1, btn)
        return btn
