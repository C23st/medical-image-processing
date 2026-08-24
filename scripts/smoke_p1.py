"""P1 冒烟测试: 实例化主窗口, 渲染并截图。

需在带显示器的桌面会话运行 (VTK 需要 OpenGL 上下文):
    D:\\Anaconda_Envs\\medimg\\python.exe scripts/smoke_p1.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.main_window import MainWindow  # noqa: E402


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1400, 900)
    win.show()

    app.processEvents()
    win.four_view.render_all()
    app.processEvents()

    pix = win.grab()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "p1_screenshot.png")
    pix.save(out)
    print(f"screenshot: {out} ({pix.width()}x{pix.height()})")

    # 校验切片视图状态
    for view in win.four_view.slice_views():
        lo, hi = view.slice_range()
        print(f"{view.label}: slice={view.get_slice()} range=[{lo},{hi}]")
    print("SMOKE OK")


if __name__ == "__main__":
    main()
