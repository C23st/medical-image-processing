"""医学图像处理平台 - 程序入口。

运行: python main.py
"""
import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.style import apply_dark_theme


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("医学图像处理平台")
    app.setOrganizationName("MedImg")
    apply_dark_theme(app)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
