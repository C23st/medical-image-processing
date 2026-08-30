# 深度学习（U-Net）胰腺分割改进可行性调研

> 调研时间：P7 打包完成之后 | 状态：纯调研，未写代码、未下载数据
> 背景：现有分割（阈值/Otsu/区域生长）在胰腺上分离困难，考虑用深度学习（U-Net 系）改进。
> 数值均为文献/官方页面量级，不确定处已标注理由。

## 摘要（决策速览）

| 问题 | 结论 |
|------|------|
| 数据够不够 | 够。NIH Pancreas-CT 82 例（与现有 test_data 同源同格式）；MSD Task07 281 训练 + 139 测试（NIfTI，需加 loader） |
| 别人做到多少 | nnU-Net（MSD Task07）Dice ≈ 0.78–0.80；经典 2D U-Net ≈ 0.68–0.84 视预处理/结构；传统方法明显更低 |
| 本机 CPU 能不能训 | 能跑通但很慢（每 epoch 约 1–2 小时，全流程数天）；建议 Colab 免费 T4 |
| 要不要自己训 | 不必需。nnU-Net（Zenodo）、MONAI、TotalSegmentator 都有现成胰腺模型 |
| 集成方式 | torch.onnx 导出 → onnxruntime CPU 推理；PyInstaller 自带 hook，无需 --collect-all；体积 +100~220 MB |
| 总投入产出比 | 求稳路径 2–3 天、亮点路径 1–2 周；对期末作业而言"集成现成模型"性价比最高 |

## 1. 数据获取

### 1.1 NIH Pancreas-CT（TCIA，82 例）✅ 与现有测试数据同源

- **内容**：82 例门静脉期腹部增强 CT + 放射科专家手工标注的胰腺掩膜，胰腺分割文献最常用公开集之一。
- **入口**：[TCIA 集合页 PANCREAS-CT](https://www.cancerimagingarchive.net/collection/pancreas-ct/)（另有 [stage 镜像页](https://stage.cancerimagingarchive.net/collection/pancreas-ct/)）。
- **下载方式**：
  1. 网页勾选序列 → 生成 `.tcia` manifest → NBIA Data Retriever 批量拉取（[TCIA Wiki: Creating Manifest Files](https://wiki.cancerimagingarchive.net/display/NBIA/Creating+Manifest+Files)）
  2. TCIA REST API（`https://services.cancerimagingarchive.net/nbia-api/`，getImage/getSOPInstanceUIDs 等）
  3. tcia-rest-client（Python，[TCIA-REST-API-Client](https://github.com/KathiraveluLab/TCIA-REST-API-Client)）
  4. 社区索引：[Awesome-Medical-Dataset Pancreas-CT 条目](https://github.com/lxmwust/Awesome-Medical-Dataset/blob/main/resources/Pancreas-CT.md)
- **规模**：82 例 × 512×512×约 200–300 层（DICOM 16-bit），总量数十 GB 量级。建议只下载门静脉期序列 + 标注。
- **许可**：该集合为 **CC BY 3.0**（以集合页 Data License 字段为准）。需注册 TCIA 账号并同意 [数据使用政策](https://wiki.cancerimagingarchive.net/plugins/viewsource/viewpagesrc.action?pageId=101941450)，禁止再分发原始图像，学术使用需署名。

### 1.2 MSD Task07 Pancreas（281 训练 + 139 测试）

- **内容**：281 训练（含标注）+ 139 测试（无公开标注）。
- **获取**：[medicaldecathlon.com](http://medicaldecathlon.com/) 官方下载；社区镜像 [kaiko-ai 说明页](https://kaiko-ai.github.io/eva/main/datasets/msd_task7_pancreas/)、[HuggingFace 镜像](https://huggingface.co/datasets/MedOtter/msd-pancreas)。
- **格式**：NIfTI（.nii.gz），MSD 已统一预处理（约 1 mm 各向同性）。
- **许可**：**CC BY-SA 4.0**。若公开基于其训练的模型需相同许可 + 署名；私有/作业内部使用不受限。

### 1.3 与现有 loader 的兼容性

| 数据 | 现有 loader（pydicom DICOM + 多帧 SEG） | 结论 |
|------|----------------------------------------|------|
| NIH Pancreas-CT（DICOM + 掩膜） | ✅ 可直接读；SEG 掩膜可直接当真值 | **可直接用于训练数据准备和验收评估** |
| MSD Task07（NIfTI） | ❌ 不支持 NIfTI | 需加 nibabel/SimpleITK 读取（SimpleITK 已在 requirements、当前未用，成本低） |

**关键点**：训练管线在 app 之外（独立预处理脚本），格式影响小；现有 2 例 test_data 与 NIH 官方集同源，训练好的模型可直接用现有 2 例做演示/验收。

## 2. 文献基线效果

| 方法 | 数据集 | 胰腺 Dice | 来源 |
|------|--------|----------|------|
| 2D CNN（DeepOrgan，Roth 2015） | NIH Pancreas-CT | ≈ **0.68**（4 折均值） | [arXiv:1506.06448](http://arxiv.org/pdf/1506.06448v1) |
| 现代 2D U-Net 变体（自监督预训练 + 注意力集成） | 公开胰腺集 | **0.78–0.81** | [ScienceDirect 2026](https://www.sciencedirect.com/science/article/pii/S1746809426005227) |
| 3D U-Net / 级联结构 | NIH / 多中心 | ≈ 0.80–0.85 量级 | [胰腺分割 DL 系统综述](https://www.springerprofessional.de/en/deep-learning-for-pancreas-segmentation-on-computed-tomography-a/50945314) |
| **nnU-Net**（自配置，MSD Task07） | MSD Task07 | **≈ 0.78–0.80** | [nnU-Net 论文](https://pubmed.ncbi.nlm.nih.gov/?cmd=Search&doptcmdl=Citation&defaultField=Title%20Word&term=nnU-Net%3A%20a%20self-configuring%20method%20for%20deep%20learning-based%20biomedical%20image%20segmentation) / [MSD 排行榜](http://medicaldecathlon.com/results/index.html) / [issue #634](https://github.com/MIC-DKFZ/nnUNet/issues/634) |
| TotalSegmentator（nnU-Net，104 类多器官） | 自家 1204 例 CT | 胰腺较难器官，约 0.8–0.9 区间 | [Radiology: AI 2023](https://pubmed.ncbi.nlm.nih.gov/37795137/) |

**与传统方法对比**：区域生长/图割在胰腺上通常 Dice < 0.7，与 DL 差距约 **0.1–0.2**。现有区域生长在 test_data 上的实测 Dice 可作为对照组，"DL vs 传统"正是答辩好素材。

## 3. 训练可行性

### 3.1 本机 CPU 训练量级估算（不推荐）

- 82 例 × 200–300 层 ≈ **1.6–2.5 万张 2D 切片**（MSD 281 例 ≈ 7–9 万张）。
- 512×512 2D U-Net（base 32–64 通道），8 核 CPU 约 **1–3 s/step**（batch 8）。
- 每 epoch ≈ 2500 step ≈ **0.7–2 小时**；30 epoch ≈ **1–3 天连续 CPU 训练**，不现实。
- 显存/内存：2D batch 8 fp32 激活量 4–8 GB；CPU 方案瓶颈是算力不是内存（16–32 GB 内存够）。
- **建议**：Google Colab 免费 T4（15 GB 显存）——每 epoch 分钟级，全流程数小时；本机 CPU 只跑推理。

### 3.2 预处理要点（对 Dice 影响最大）

1. HU 窗位归一化：clamp 到胰腺窗（如 [-100, 300]）→ min-max 到 [0,1] 或 z-score。
2. ROI 裁剪：按掩膜质心裁剪 256/384 区域（或身体连通域去背景），降算力 + 聚焦胰腺；推理用滑窗或先粗定位。
3. 数据增强：随机翻转、旋转 ±15°、弹性形变、强度抖动/对比度扰动。82 例小数据下增强是关键。

### 3.3 损失函数

- 首选 **Dice loss**（胰腺占体素约 1%，CE 被背景淹没）；
- 次选 CE + Dice 混合（0.5/0.5），收敛更稳；focal 通常不必。

## 4. 预训练模型可用性

| 来源 | 是否含胰腺 | 形态 | 备注 |
|------|-----------|------|------|
| **nnU-Net 预训练（MSD 全任务）** | ✅ Task07 | 官方权重，Zenodo 托管 | [DOI 10.5281/zenodo.3734294](https://explore.openaire.eu/search/other?pid=10.5281%2Fzenodo.3734294) |
| **MONAI Model Zoo** | ✅ `pancreas_ct_dints_segmentation` | DiNTS 权重 + 推理配置 | [HuggingFace 模型卡](https://huggingface.co/monai-test/pancreas_ct_dints_segmentation) / [inference.yaml](https://github.com/ericspod/model-zoo/blob/dev/models/pancreas_ct_dints_segmentation/configs/inference.yaml) |
| **HuggingFace 社区** | ✅ 多个 | nnU-Net / 腹部多器官 | [monai-test 胰腺模型](https://huggingface.co/monai-test/pancreas_ct_dints_segmentation)、[AbdomenAtlas/MedFormerPanTS](https://huggingface.co/api/resolve-cache/models/AbdomenAtlas/MedFormerPanTS/b854c8248af1e21f729dc2dfd489bd400472cf65/README.md) |
| **TotalSegmentator** | ✅ 104 类含胰腺 | nnU-Net 系，可单器官 | [论文](https://pubmed.ncbi.nlm.nih.gov/37795137/) / [源码](https://github.com/wasserth/TotalSegmentator) / [权重](https://huggingface.co/totalseg/TotalSegmentator)。**推理依赖 torch，体积大（+1 GB），不建议打进 exe** |

## 5. 集成方案与打包影响

### 5.1 ONNX 导出

`torch.onnx.export(model, (1,1,512,512) NCHW float32, opset=13~17)`；U-Net 全是标准算子，导出无障碍（[PyTorch ONNX 文档](https://pytorch.org/docs/stable/onnx.html)）。

### 5.2 onnxruntime + PyInstaller ✅ 现成 hook

- onnxruntime CPU wheel 约 **55–90 MB**（[PyPI](https://pypi.org/project/onnxruntime/1.17.1/)）。
- hooks-contrib [PR #817](https://github.com/pyinstaller/pyinstaller-hooks-contrib/pull/817) 起内置 `hook-onnxruntime.py`，自动收集 `onnxruntime/capi` 动态库与 provider 插件。**本机 hooks-contrib 2026.6 已实测存在该 hook**（`collect_dynamic_libs("onnxruntime")`），无需 `--collect-all`。

### 5.3 推理耗时（量级）

- 512×512 单层 fp32 CPU：小型 2D U-Net（8M–30M 参数）约 **0.1–0.5 s/层**；int8 量化再快 2–3×。
- **240 层全卷 ≈ 1–3 分钟**，加前后处理总计 **2–4 分钟/卷**——适合"点按钮→出结果"批处理式 AI 分割。

### 5.4 对 650 MB dist 的体积增量

| 项 | 大小 |
|----|------|
| ONNX 模型（fp32，选小 U-Net） | 30–50 MB |
| onnxruntime（CPU） | 60–90 MB |
| **合计增量** | **约 +100–220 MB（+15%~35%）** |

### 5.5 ONNX 方案 vs 内置 torch CPU 运行时

| 维度 | ONNX + onnxruntime | 内置 torch（CPU） |
|------|--------------------|-------------------|
| 体积增量 | +100–220 MB | +800 MB ~ 1 GB+ |
| 打包复杂度 | 现成 hook，无脑 | 大量 hidden-import/collect，启动变慢 |
| 推理速度 | 接近（略优） | 相当 |
| 结论 | **✅ 推荐** | 除非同时要训练能力，否则不值得 |

## 6. 风险与建议

### 6.1 数据许可合规
- NIH Pancreas-CT：CC BY 3.0，TCIA 政策禁止再分发原始图像——作业内使用/演示无碍，不要上传原始数据到公开仓库。
- MSD Task07：CC BY-SA 4.0——公开基于其训练的模型需相同许可 + 署名；私有使用不受限。
- test_data 本身 git-ignored，合规风险低。

### 6.2 训练效果不确定性
- 82 例从零训 2D U-Net，现实预期 **Dice 0.70–0.80**（不保证）；nnU-Net 的 0.78–0.84 需大配置搜索 + 3D 全分辨率训练，超出作业量级。
- 用现成预训练（nnU-Net/MONAI/TotalSegmentator）Dice 稳定 0.8+，**效果确定性强**。

### 6.3 工作量与投入产出比
- 求稳路径（集成现成模型）：2–3 天。
- 亮点路径（自训 + 部署）：1–2 周全职，且效果有风险。
- **对期末作业：除非老师明确要求"自研 DL"，否则"工程集成 + 严谨评估"性价比远高于"从零训练"。**

### 6.4 答辩亮点建议
1. 传统 vs DL 对比表：自家区域生长实测 vs 模型 Dice；
2. ONNX 轻量集成：CPU 推理、体积增量可控，体现工程能力；
3. 评估严谨性：Dice/精确率/召回率、与 SEG 真值对齐、2 例 test_data 演示；
4. 消融/超参（若自训）：有无裁剪、有无增强、Dice vs CE+Dice；
5. 切平面联动：AI 分割结果叠加三视图 + 3D 切平面，与现有功能闭环。

## 7. 推荐路径

**🛡 求稳（推荐）——集成现成模型，不自己训练**
1. 下载 nnU-Net MSD 预训练（[Zenodo 10.5281/zenodo.3734294](https://explore.openaire.eu/search/other?pid=10.5281%2Fzenodo.3734294)）或 [MONAI pancreas 模型](https://huggingface.co/monai-test/pancreas_ct_dints_segmentation)；
2. 转 ONNX（1×1×512×512，opset 13+）→ 集成 onnxruntime（现成 hook）；
3. 用现有 2 例 test_data 评估 Dice 并与区域生长对比；
4. 分割页新增"AI 分割"按钮，复用现有叠加/切平面显示。
**成本 2–3 天，效果确定（Dice ≈ 0.78–0.84），风险最低。**

**🌟 亮点（学有余力 / 老师点名要自研）——Colab 免费 T4 自训 2D U-Net**
1. 数据：MSD Task07（NIfTI 一步到位）或 NIH DICOM（SEG 真值转换）；
2. 预处理：HU 窗位归一化 + ROI 裁剪 + 增强；损失 Dice loss；
3. 训练 50–80 epoch（数小时）→ 验证集 Dice 达标 → ONNX 导出；
4. 集成 + 打包（同求稳路径 3、4 步）。
**成本 1–2 周，效果有不确定性，但答辩上限高。**

**⚖ 折中：TotalSegmentator** 一键出结果（Dice 最高、零训练），但不打进 exe（torch 运行时 +1 GB 不划算）；可作"业界 SOTA 对照"在答辩中引用，不集成。
