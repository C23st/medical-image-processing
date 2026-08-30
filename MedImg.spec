# -*- mode: python ; coding: utf-8 -*-
"""医学图像处理平台 - PyInstaller 打包配置 (onedir / windowed)。

用法: build_exe.bat 或:
  D:\Anaconda_Envs\medimg\python.exe -m PyInstaller --noconfirm --clean MedImg.spec

产物: dist\MedImg\MedImg.exe  (整个文件夹为绿色版, 可整体拷贝/压缩分发)
验证: dist\MedImg\MedImg.exe --selftest  -> 输出 SELFTEST OK
"""
from PyInstaller.utils.hooks import collect_submodules

# vtkmodules.qt.QVTKRenderWindowInteractor 虽被静态导入(app/views),
# 显式声明保证万无一失; Qt6 下它需要 PySide6.QtOpenGLWidgets(其 import 可见)。
hiddenimports = [
    "vtkmodules.qt.QVTKRenderWindowInteractor",
    "vtkmodules.util.numpy_support",
] + collect_submodules("vtkmodules.qt")

# 应用实际未使用的大型库, 排除以减小体积 (skimage.exposure/filters 不依赖它们)
excludes = [
    "matplotlib", "PIL", "SimpleITK", "IPython", "pytest", "tkinter",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtMultimedia",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtPdf",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MedImg",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,              # 发布版不弹控制台窗口
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MedImg",
)
