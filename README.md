# 医学图像处理平台 (Medical Image Processing Platform)

一个仿 **3D Slicer** 风格的医学图像处理桌面软件，作为医学图像处理课程期末大作业开发。
技术栈：**Python 3.10 + PySide6 + VTK**。

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 📂 DICOM 打开/解读/显示 | 多序列加载、元数据解析、窗宽窗位、RAS 物理坐标 |
| 🖼 三正交切片视图 | Axial / Coronal / Sagittal + 3D 视图（四视图联动） |
| 🔍 图像增强 | 9 种方法：线性拉伸 / 对数 / 伽马 / 直方图均衡 / CLAHE / 均值 / 中值 / 高斯 / 锐化 |
| 🎯 图像分割 | 阈值分割 / Otsu 自动阈值 / 区域生长，半透明标签叠加 |
| 📊 真值对比 | 与自带 SEG 胰腺标签计算 **Dice 系数**（有真值时） |
| 🎯 十字准星联动 | **Shift + 移动鼠标** 以 3D 点为中心，其余视图实时跳层（RAS 定位） |
| 🖱 实时悬停 | 鼠标移动即显示坐标 (z,y,x) 与体素值，无需点击 |
| 🔎 视图缩放/平移 | **Ctrl + 滚轮** 缩放，**中键拖动** 平移，可重置视图 |
| 🧭 方向定位 | 十字准星定位线、绿色种子点标记 |

> 三维重建（面绘制 Marching Cubes + 体绘制 Ray Casting）为规划中功能（P5）。

## 🛠 技术栈

| 类别 | 库 |
|------|-----|
| GUI | PySide6 (Qt 6) |
| 可视化/3D | VTK 9.7 |
| DICOM | pydicom |
| 图像处理 | numpy / scipy / scikit-image |
| 医学处理 | SimpleITK |

## 📦 环境安装

```powershell
# 建议使用 conda 创建独立环境
conda create -n medimg python=3.10 -y
conda activate medimg
pip install -r requirements.txt
```

## 🚀 运行

```powershell
python main.py
```

或直接双击 `run.bat`（自动使用 medimg 环境的 Python）。

## 📖 使用说明

1. **文件 → 打开 DICOM 文件夹** → 选择一个含 DICOM 序列的目录（如 `test_data\PANCREAS_0001`）
2. 左侧数据树双击序列加载；右侧参数面板切换 显示 / 增强 / 分割 页签

**视图交互**：

| 手势 | 功能 |
|------|------|
| 滚轮 | 翻层（当前视图） |
| Ctrl + 滚轮 | 放大 / 缩小 |
| 中键拖动 | 平移 |
| 左键单击 | 设置种子点 / 拾取 |
| Shift + 移动鼠标 | 十字联动（其余视图实时跳层） |
| 鼠标悬停 | 实时显示位置 + 体素值 |
| 视图 → 重置视图 | 复位缩放 / 平移 |

**分割提示**：Dice 系数是分割结果与数据自带胰腺真值（SEG）的重合度；简单分割方法在 CT 上难以单独抠出胰腺（与邻近软组织灰度接近），Dice 偏低属正常现象。

## 📁 项目结构

```
├── main.py                  # 程序入口
├── requirements.txt         # 依赖清单
├── run.bat                  # 一键启动
├── app/
│   ├── main_window.py       # 主窗口
│   ├── style.py             # 深色主题
│   ├── core/                # 数据层 + 算法层
│   │   ├── volume.py        # 体数据封装 (spacing/origin/direction/RAS)
│   │   ├── dicom_loader.py  # DICOM 加载
│   │   ├── enhance.py       # 增强算法
│   │   └── segment.py       # 分割算法 + Dice
│   ├── views/               # 切片视图 / 3D 视图 / 四视图
│   └── widgets/             # 数据树 / 参数面板 / 信息区
├── docs/
│   ├── development_plan.md  # 开发方案
│   └── manual_test.md       # 手动测试指南
└── scripts/                 # 测试 / 诊断脚本
```

## ⚠️ 测试数据

- `test_data/`（NIH Pancreas-CT 风格样例，约 250MB）**未随仓库分发**
- 如需复现演示效果，请自行准备 DICOM 数据（任一 CT/MR 序列目录即可，也可从公开数据集获取）

## 🔧 其他

- **打包 exe**：规划中（PyInstaller，见开发方案文档）
- **手动测试指南**：`docs/manual_test.md`
- 本项目为课程期末作业，仅供学习交流。
