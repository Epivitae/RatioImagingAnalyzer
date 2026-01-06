<div align="center">
  <img src="https://raw.githubusercontent.com/Epivitae/RatioImagingAnalyzer/main/src/ria_gui/assets/app_ico.png" width="120" alt="Logo">

  <h1>Ratio Imaging Analyzer (RIA / 莉丫)</h1>

  <p>
    <a href="./README.md"><img src="https://img.shields.io/badge/README-English-blue.svg" alt="English Version"></a>
  </p>

  <p>
    <a href="https://pypi.org/project/ria-gui/"><img src="https://img.shields.io/pypi/v/ria-gui?color=blue" alt="PyPI"></a>
    <a href="https://github.com/Epivitae/RatioImagingAnalyzer/releases/latest"><img src="https://img.shields.io/github/v/release/Epivitae/RatioImagingAnalyzer?label=下载最新版&logo=github&color=2ea44f" alt="Download Latest Release"></a>
    <a href="https://joss.theoj.org/papers/@epivitae"><img src="https://joss.theoj.org/papers/please-replace-with-your-id/status.svg" alt="Status"></a>
    <a href="https://doi.org/10.5281/zenodo.18091693"><img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18091693-0099CC" alt="DOI"></a>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white" alt="Python"></a>
    <a href="LICENSE"><img src="https://img.shields.io/github/license/Epivitae/RatioImagingAnalyzer?color=yellow" alt="License"></a>
  </p>

  <p>
    <a href="https://github.com/Epivitae/RatioImagingAnalyzer/actions/workflows/test.yml"><img src="https://img.shields.io/github/actions/workflow/status/Epivitae/RatioImagingAnalyzer/test.yml?branch=main&label=tests&color=brightgreen" alt="Tests"></a>
    <a href="https://opensource.org/"><img src="https://img.shields.io/badge/Open_Source-Yes-2ea44f?logo=open-source-initiative&logoColor=white" alt="开源"></a>
    <img src="https://img.shields.io/github/repo-size/Epivitae/RatioImagingAnalyzer?color=ff69b4" alt="Size">
    <img src="https://img.shields.io/endpoint?color=blueviolet&url=https://gist.githubusercontent.com/Epivitae/65b61a32eaccf5de9624892da2ddd0d8/raw/gistfile1.txt" alt="LOC">
    <img src="https://visitor-badge.laobi.icu/badge?page_id=Epivitae.RatioImagingAnalyzer" alt="Visitors">
  </p>
</div>

---

**认识一下 RIA (我们亲切地称她为 "Li Ya / 莉丫")。**

RIA 是一个开源工具，旨在解决一个简单却令人烦恼的问题：**比率成像分析不应被束缚在显微镜的工作站上。**

比率成像（如 FRET 或色氨酸/pH/Ca²⁺ 传感器）在数据归一化方面表现出色，但分析这些数据通常需要昂贵的商业软件（如 MetaMorph 或 NIS-Elements），而这些软件往往通过加密狗（Dongle）锁定在特定的工作站上。

我们构建了 RIA，让你可以带上你的 TIFF 图像序列，去咖啡馆（或只是回到你的办公桌），在自己的笔记本电脑上运行严谨的分析——**无需编写任何代码**。

<p align="center">
  <img src="https://raw.githubusercontent.com/Epivitae/RatioImagingAnalyzer/main/src/ria_gui/assets/figure/analysis.gif" width="600" alt="RIA 界面展示">
</p>

## 💡 为什么选择 RIA?

* **分析无拘无束**：别再排队等实验室的公用电脑了。RIA 是一个独立的程序，可以在标准的 PC 上运行。
* **可重复性**：科学需要验证。RIA 允许你将整个工作区（ROI、阈值、背景设置）保存为轻量级的 **`.ria` 项目文件**。将此文件发送给合作者或审稿人，他们即可立即复现你的分析过程并验证结果。
* **严谨的算法**：计算比率不仅仅是简单的 `A / B`。生物图像存在边缘和噪声。我们实现了**归一化卷积算法（Normalized Convolution）**，正确处理 `NaN`（非数值）值。这意味着你的数据不会在细胞边界处被侵蚀或损坏。
* **零代码需求**：我们知道并非每个人都喜欢 Python。RIA 拥有完整的图形界面（GUI），支持背景扣除、阈值调整以及拖放绘制 ROI。
* **数据透明**：我们不隐藏数字。你不仅能看到可视化的图像堆栈，还能获得**原始的 float32 比率数据**和时间序列 CSV 文件。你可以直接将其导入 Prism、Origin 或 Excel。

## 📁 项目结构

```text
RatioImagingAnalyzer/
├── data/               # 示例 TIFF 文件，供您立即试用
├── paper/              # JOSS 论文提交文件
├── src/ria_gui         # 核心代码
│   ├── main.py         # 程序入口
│   ├── gui.py          # 前端逻辑
│   ├── processing.py   # 数学/算法核心
│   └── components.py   # UI 组件
├── tests/              # 自动化测试，防止 Bug
└── requirements.txt    # 依赖列表
```

## 🚀 安装与版本

RIA 提供两个版本以满足不同需求：**RIA Pro**（高级功能）和 **RIA Lite**（便携版）。

### 💎 选项 1: RIA Pro (PyPI / 源码)
**推荐人群：使用 .oir, .nd2, .czi 文件的研究人员。**

**Pro** 版本是全功能的 Python 包。它包含完整的依赖项（如 `aicsimageio`, `bioformats`），直接支持读取专业的显微镜格式。

> **⚠️ 前置条件：Java (JDK)**
> 要通过 Bio-Formats 后端读取专有格式（如 `.oir`, `.nd2`），**您的系统必须安装 Java 开发工具包 (JDK)**（推荐 OpenJDK 11 或更高版本）。

* **独家功能：** 直接支持奥林巴斯 **.oir**、尼康 **.nd2** 和蔡司 **.czi** 文件。
* **安装方法：**
    ```bash
    pip install ria-gui
    ```
    安装完成后，通过以下命令启动：
    ```bash
    ria
    ```

### ⚡ 选项 2: RIA Lite (独立可执行文件)
**推荐人群：希望无需安装 Python 即可立即使用的用户。**

**Lite** 版本是经过重构的轻量级可执行文件，针对速度和便携性进行了优化。我们显著减小了文件体积，并优化了初始化过程以实现瞬间启动。

* **适用场景：** 任何 Windows PC 上的标准 TIFF 工作流。
* **无需 Java：** 由于 Lite 版本处理标准 TIFF，因此无需外部 Java 环境。
* **主要特点：** 零配置，超快冷启动，极低的内存占用。
* **下载：** 请访问 [Releases](https://github.com/Epivitae/RatioImagingAnalyzer/releases) 页面下载最新的 `RIA_Lite_vX.X.exe`。

### 选项 3: 源码运行 (开发者)

对于想要贡献代码或修改的开发者：

1. **克隆仓库：**
   ```bash
   git clone [https://github.com/Epivitae/RatioImagingAnalyzer.git](https://github.com/Epivitae/RatioImagingAnalyzer.git)
   cd RatioImagingAnalyzer
   ```

2. **安装依赖：**
   推荐使用虚拟环境。
   ```bash
   pip install -r requirements.txt
   ```

3. **运行程序：**
   ```bash
   python src/ria_gui/main.py
   ```

## 📖 使用流程

1. **加载文件**：
   * 支持 **单通道** (强度) 和 **多通道** (比率) TIFF 堆栈。
   * **RIA Pro** 用户可以直接拖放 `.oir` / `.nd2` 文件（