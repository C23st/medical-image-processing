"""应用外观: Fusion 风格 + 深色主题。"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette


def apply_dark_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()

    window = QColor(43, 46, 54)
    base = QColor(30, 32, 38)
    alt_base = QColor(50, 53, 61)
    text = QColor(220, 222, 226)
    disabled = QColor(120, 122, 128)
    highlight = QColor(42, 130, 218)

    palette.setColor(QPalette.Window, window)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, base)
    palette.setColor(QPalette.AlternateBase, alt_base)
    palette.setColor(QPalette.ToolTipBase, base)
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Button, window)
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.BrightText, QColor(255, 255, 255))
    palette.setColor(QPalette.Highlight, highlight)
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.Disabled, QPalette.Text, disabled)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled)

    app.setPalette(palette)
