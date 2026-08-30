# P7 打包方案 (PyInstaller → exe + Inno Setup 安装包)

> 状态: 准备完成, 待实际构建验证。构建脚本 `build_installer.bat`, 配置 `MedImg.spec` + `installer.iss`。

## 1. 目标与产物形态

- **双产物交付**（用户已确认）：
  1. **绿色版**: `dist\MedImg\` 文件夹 + `MedImg.exe`（免安装, 拷 U 盘即用）
  2. **安装包**: `dist\MedImg-Setup.exe`（Inno Setup 向导, 可选桌面/开始菜单快捷方式, 可卸载）
- **形态决策**:
  | 方案 | 结论 | 理由 |
  |------|------|------|
  | `--onedir`（文件夹） | ✅ **采用** | 启动快（免解压）、好调试、可单独替换 exe |
  | `--onefile`（单文件） | ❌ | 每次启动把 600MB+ 解压到临时目录, 慢; 易被杀软误报 |
  | `--windowed`（无控制台） | ✅ 发布版 | 最终交付不弹黑窗; 另留 `--selftest` 供验证 |
  | `upx` 压缩 | ❌ | 未安装 UPX; 压缩 VTK DLL 易损坏 |
  | 安装包工具 | **Inno Setup 6** | 免费/成熟/中文向导; exe 安装包。MSI 需 WiX, 课程作业不必 |

## 2. 运行期依赖分析（实际会被打进 exe 的只有被 import 的）

从 `app/` 全量 import 扫描得到真实依赖:

| 库 | 用途 | 是否打包 | 说明 |
|----|------|---------|------|
| PySide6 (QtCore/QtGui/QtWidgets/**QtOpenGLWidgets**) | GUI + QVTK 桥 | ✅ | QVTKRenderWindowInteractor 在 Qt6 下需要 QtOpenGLWidgets |
| vtk (+ vtkmodules.qt / numpy_support) | 显示/重建/切平面 | ✅ | hooks-contrib 2026.6 自带全部 vtkmodules hook |
| numpy | 体数据 | ✅ | PyInstaller 6.22.2 支持 numpy 2.x |
| scipy (ndimage) | 滤波/分割 | ✅ | PyInstaller 内置 hook |
| scikit-image (exposure/filters) | CLAHE/Otsu 等 | ✅ | hook-skimage 按子模块收集 |
| opencv-python (cv2) | 双边滤波 | ✅ | hook-cv2 存在 |
| pydicom | DICOM 解析 | ✅ | hook-pydicom 存在 |
| matplotlib / Pillow / SimpleITK | requirements 里但**未被 app import** | ❌ 排除 | 在 spec 的 excludes 中明确排除, 减小体积 |

**运行时数据文件**: 无。样式为纯代码; 最近打开列表写在用户目录 `~/.medimg_recent.json`;
测试数据 `test_data/` 外置, **不打进 exe**（体积大且属于用户数据）。

## 3. 打包配置说明（MedImg.spec）

- **hiddenimports**: 显式声明 `vtkmodules.qt.QVTKRenderWindowInteractor` / `numpy_support` + `collect_submodules("vtkmodules.qt")`, 双保险
- **excludes**: matplotlib / PIL / SimpleITK / IPython / pytest / tkinter + PySide6 未用模块 (Qml/Quick/Multimedia/WebEngine/Sql/Test/Pdf)
- **console=False**: 发布版不弹控制台
- **upx=False**, **name=MedImg**（ASCII 名, 避免中文路径兼容问题; 窗口标题本身是中文, 不受影响）

## 4. 体积预估

安装体积实测 (site-packages):

| 包 | 安装体积 |
|----|---------|
| PySide6 (Essentials+Addons 合并目录) | ~632 MB |
| cv2 | ~112 MB |
| scipy | ~111 MB |
| vtkmodules | ~50 MB |
| numpy | ~28 MB |
| skimage | ~26 MB |
| pydicom | ~19 MB |
| shiboken6 | ~3 MB |

**预估 dist\MedImg 约 600~900 MB**（PySide6 hook 会按需裁掉部分 Addons; 实际以构建后 `dist` 实测为准）。
如果偏大, 后续可选瘦身（见 §8）。

## 5. 构建步骤

```
只出绿色版:   双击 build_exe.bat
绿色版+安装包: 双击 build_installer.bat   (自动: 清理 → PyInstaller → ISCC installer.iss)
  或手动: D:\Anaconda_Envs\medimg\python.exe -m PyInstaller --noconfirm --clean MedImg.spec
          "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

构建**不需要显示器/OpenGL**, 沙箱内即可完成; 产物为 `dist\MedImg\` + `dist\MedImg-Setup.exe`。
安装包脚本要点（installer.iss）: 安装目录 `{autopf}\MedImg`（可改）、中文向导、
桌面快捷方式为**可选项**（默认不勾）、卸载记录、不写应用级注册表。

## 6. 验证方案

1. **依赖自检（自动化, 可在无显示器环境跑）**: `dist\MedImg\MedImg.exe --selftest`
   - 源码 `main.py` 新增 `--selftest`: 导入全部核心模块 + 创建 QApplication, 输出 `SELFTEST OK` 退出码 0
   - 可捕获 90% 打包错误（缺 DLL / 缺模块 / hook 失败）
2. **GUI 手动验证（需在真实桌面, 由使用者执行）**: 打开 DICOM 病人 → 翻层/缩放/十字联动 → 增强(取 1~2 种) → 分割 → 三维重建 + 切平面 → 退出
3. 若 GUI 有问题再构建 `console=True` 的调试版看 Traceback

## 7. 风险与对策

| 风险 | 对策 |
|------|------|
| skimage 惰性子模块漏收集 | hook-skimage 已按子模块覆盖 exposure/filters; 自检可发现 |
| VTK DLL 收集不全 | hooks-contrib 2026.6 有全套 vtkmodules hook; 自检 + 手动 GUI 验证 |
| PySide6 6.11 较新, hook 兼容性 | hooks-contrib 2026.6 (2026 版) 已适配; 自检验证 |
| numpy 2.2.6 | PyInstaller 6.22.2 原生支持 |
| 无签名 exe 触发 SmartScreen | 属正常现象, 交付说明中注明「更多信息 → 仍要运行」 |
| `--windowed` 无控制台, 出错看不到信息 | 提供 `--selftest`; 排查时改用 console 调试版 |
| 首次启动较慢 | onedir 已最小化; 磁盘 IO 决定 |

## 8. 后续可选（本阶段不做）

- **瘦身**: 构建后按 dist 实测, 继续排除 PySide6 未用 Qt 插件/翻译文件; 或改用精简依赖
- **MSI 安装包**: 如老师要求 msi, 用 WiX 把 `dist\MedImg` 打包（Inno Setup 默认出 exe 安装包）
- **图标/版本信息**: 提供 .ico 后加进 EXE 与安装包; 版本号与产品信息写在 Inno Setup 的 version 字段（当前 1.0.0）
