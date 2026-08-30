"""医学图像处理平台 - 程序入口。

运行: python main.py
"""
import sys

import vtk

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.style import apply_dark_theme


def _selftest():
    """打包自检: 不启动 GUI, 仅验证全部模块/依赖/DLL 能否加载。

    用法: MedImg.exe --selftest   (输出 SELFTEST OK 即依赖齐全)
    """
    import app.main_window  # noqa: F401  触发全部视图/组件模块导入
    import app.core.dicom_loader  # noqa: F401
    import app.core.enhance  # noqa: F401
    import app.core.segment  # noqa: F401
    import app.core.volume  # noqa: F401

    app = QApplication.instance() or QApplication(sys.argv)
    print("SELFTEST OK: 所有模块导入成功, Qt 初始化完成")
    return 0


def main():
    # 关闭 VTK 全局错误弹窗 (Qt+VTK 常有轻微警告, 避免弹出 vtkOutputWindow)
    vtk.vtkObject.GlobalWarningDisplayOff()

    if "--selftest" in sys.argv:
        sys.exit(_selftest())

    app = QApplication(sys.argv)
    app.setApplicationName("医学图像处理平台")
    app.setOrganizationName("MedImg")
    apply_dark_theme(app)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
