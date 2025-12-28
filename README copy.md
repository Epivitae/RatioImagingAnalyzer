# 🔬 Ratio Imaging Analyzer

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**🌍 [English](#english-description) | 🇨🇳 [中文说明](#中文说明)**

---

## 📖 English Description

**Ratio Imaging Analyzer** is a lightweight, professional desktop application for **ratiometric fluorescence imaging analysis** (e.g., *Fura-2, GCaMP/RFP, or other dual-channel indicators*).
Built with **Python (Tkinter + Matplotlib)**, it provides a responsive interface for researchers to **visualize, process, and quantify imaging data in real-time**.

---

### ✨ Key Features

| Category                             | Features                                                                                                                                               |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 🧪**Dual-Channel Processing**  | Load two TIFF stacks (Channel 1 & Channel 2) → calculate ratio image ($C1 / C2$).                                                                   |
| ⚙️**Real-time Adjustment**   | • Background subtraction (percentile-based)`<br>`• Smart thresholding (Intensity/Ratio)`<br>`• Smoothing filters `<br>`• Logarithmic scaling |
| 🎯**Interactive ROI Analysis** | • Draw & drag ROIs `<br>`• Instant curve updates `<br>`• Multi-unit time axis (s / m / h)`<br>`• Export ROI data to clipboard                |
| 💾**Data Export**              | • Save single frame as `.tif<br>`• Batch export entire stack as multi-page `.tif`                                                                |
| 🖥️**User Experience**        | • Bilingual interface (EN/中文)`<br>`• Native Matplotlib toolbar `<br>`• Custom colormaps & NaN background colors                               |

---

### 🛠️ Installation & Requirements

Ensure **Python 3.8+** is installed. Required libraries:

```bash
pip install numpy matplotlib scipy tifffile
```

### 🚀 How to Run

Clone this repository or download the source code, then run:

bash

```
python ImageRatio.py
```

*(Replace *`ImageRatio.py`* with your actual filename if different)*

### 📦 Build Executable (.exe)

To create a standalone `.exe` for Windows users (no Python required):

bash

```
pyinstaller --noconsole --onefile --hidden-import=tifffile ImageRatio.py
```

⚠️  **Important** : Always include `--hidden-import=tifffile`, otherwise TIFF files may fail to load.

`<a name="chinese"></a>`

## 📖 中文说明

**ImageRatio** 是一款专为  **比率荧光成像分析** （如  *Fura-2, GCaMP/RFP 等双通道指示剂* ）设计的轻量级桌面软件。
基于 **Python (Tkinter + Matplotlib)** 开发，科研人员无需编写代码即可  **实时处理、可视化和定量分析成像数据** 。

### ✨ 主要功能

| 分类                       | 功能                                                                               |
| -------------------------- | ---------------------------------------------------------------------------------- |
| 🧪**双通道处理**     | 加载两个TIFF序列（通道1&通道2），自动计算比率图像(C1/C2)。                         |
| ⚙️**实时参数调节** | •背景扣除（百分位数法）``•智能阈值（强度/比率）``•平滑处理``•对数变换          |
| 🎯**交互式ROI分析**  | •绘制与拖动ROI ``•曲线实时更新``•多时间单位（秒/分/时）``•一键复制数据到剪贴板 |
| 💾**数据保存**       | •保存单帧为 `<span>.tif</span>`•批量保存为多页 `<span>.tif</span>`           |
| 🖥️**用户体验**     | •中英双语界面 ``•内置Matplotlib工具栏``•自定义伪彩与背景颜色                    |

### 🛠️ 安装与依赖

请确保已安装  **Python 3.8+** ，并安装以下库：

```
pip install numpy matplotlib scipy tifffile
```

### 🚀 如何运行

克隆仓库或下载源代码后，在终端运行：

```
python ImageRatio.py
```

*(请将 *`ImageRatio.py`* 替换为实际脚本文件名)*

### 📦 打包为 Exe 可执行文件

使用 **pyinstaller** 或 **auto-py-to-exe** 打包：

```
pyinstaller --noconsole --onefile --hidden-import=tifffile ImageRatio.py
```

⚠️  **注意** ：必须添加 `--hidden-import=tifffile` 参数，否则程序可能无法正确加载 TIFF 文件。

## 📜 Copyright & Contact

* © Dr. Kui Wang
* 🌐 Website: www.cns.ac.cn
* ✉️ Email: **k@cns.ac.cn**
* 📄 License: MIT License