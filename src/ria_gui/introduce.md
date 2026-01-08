RatioImagingAnalyzer
├── build-lite.py
├── build-macOS.py
├── CITATION.cff
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── data
│   ├── C1.tif
│   ├── C2.tif
│   └── Composite.tif
├── LICENSE
├── MANIFEST.in
├── paper
│   ├── images
│   │   ├── figure1.png
│   │   └── figure2.png
│   ├── paper.bib
│   └── paper.md
├── pypi-git.py
├── pyproject.toml
├── README.md
├── README_zh.md
├── requirements.txt
├── ria.py
├── RIA_1.8.3_Lite.exe
├── src
│   ├── ria_gui
│   │   ├── assets
│   │   │   ├── app.icns
│   │   │   ├── app_256x256.ico
│   │   │   ├── app_ico.png
│   │   │   ├── figure
│   │   │   │   ├── analysis.gif
│   │   │   │   └── live-plot.gif
│   │   │   └── ratiofish.ico
│   │   ├── components.py
│   │   ├── constants.py
│   │   ├── gui.py
│   │   ├── gui_components.py
│   │   ├── introduce.md
│   │   ├── io_utils.py
│   │   ├── main.py
│   │   ├── model.py
│   │   ├── plot_window.py
│   │   ├── processing.py
│   │   ├── _version.py
│   │   ├── __init__.py
│   │   └── __pycache__
│   │       ├── components.cpython-310.pyc
│   │       ├── components.cpython-312.pyc
│   │       ├── constants.cpython-310.pyc
│   │       ├── constants.cpython-312.pyc
│   │       ├── gui.cpython-310.pyc
│   │       ├── gui.cpython-312.pyc
│   │       ├── gui.cpython-38.pyc
│   │       ├── gui_components.cpython-310.pyc
│   │       ├── gui_components.cpython-312.pyc
│   │       ├── io_utils.cpython-310.pyc
│   │       ├── io_utils.cpython-312.pyc
│   │       ├── lazy_array.cpython-312.pyc
│   │       ├── main.cpython-310.pyc
│   │       ├── main.cpython-312.pyc
│   │       ├── model.cpython-310.pyc
│   │       ├── model.cpython-312.pyc
│   │       ├── plot_window.cpython-310.pyc
│   │       ├── plot_window.cpython-312.pyc
│   │       ├── processing.cpython-310.pyc
│   │       ├── processing.cpython-312.pyc
│   │       ├── _version.cpython-310.pyc
│   │       ├── _version.cpython-312.pyc
│   │       ├── __init__.cpython-310.pyc
│   │       └── __init__.cpython-312.pyc
│   └── __pycache__
│       ├── components.cpython-312.pyc
│       ├── constants.cpython-312.pyc
│       ├── gui.cpython-312.pyc
│       ├── gui_components.cpython-312.pyc
│       ├── io_utils.cpython-312.pyc
│       ├── main.cpython-312.pyc
│       ├── processing.cpython-312.pyc
│       ├── _version.cpython-312.pyc
│       └── __init__.cpython-312.pyc
└── tests
    ├── auto_drive.py
    ├── conftest.py
    ├── test_io.py
    ├── test_model.py
    ├── test_processing.py
    └── __init__.py



# 项目深度分析：RIA (Ratio Imaging Analyzer)

这是一个基于 Python 开发的专业级生物医学图像分析软件，专为解决**比率荧光成像 (Ratiometric Imaging)** 的分析需求（如钙成像、FRET 实验）而设计。

---

## 1. 核心实现方法 (Technical Implementation)

该项目采用了经典的 **MVC (Model-View-Controller)** 架构思想进行解耦设计，确保了代码的可维护性和扩展性。

### 技术栈与核心库
* **GUI 框架**: 使用 **Tkinter** (Python 标准库) 构建桌面应用。
    * 使用了 `ttk` 主题控件实现了现代化的 UI。
    * 实现了 Light/Dark 主题切换机制 (`gui.py`)。
* **数据内核**: 使用 **NumPy** 进行高效的多维矩阵运算 (T, Z, C, Y, X)，这是图像处理的基础。
* **图像 I/O**:
    * `tifffile`: 处理标准 TIFF 和 ImageJ Hyperstack。
    * `aicsimageio` (基于 Bio-Formats): **关键亮点**，直接支持显微镜厂商原始格式（Olympus `.oir`, Nikon `.nd2`, Zeiss `.czi`, Leica `.lif`），无需格式转换。
* **核心算法**:
    * **OpenCV (`cv2`)**: 实现 **ECC (Enhanced Correlation Coefficient)** 算法，用于图像序列的自动配准（防抖）。
    * 图像平滑与去噪算法。
* **可视化引擎**:
    * **Matplotlib**: 深度嵌入到 Tkinter 中。
    * 实现了实时伪彩热图 (Heatmap)、Kymograph (时空图) 以及交互式的 ROI 数据曲线绘制。

### 架构模块
* **Model (`model.py`)**: 后端逻辑核心。负责管理数据状态、执行 I/O 操作、计算背景扣除和比率矩阵。
* **View (`gui.py`, `plot_window.py`)**: 前端界面。负责布局、文件加载、播放器控制及弹窗显示。
* **Components (`gui_components.py`)**: 复杂组件封装。包含 `RoiManager`（ROI 交互管理）和 `PlotManager`（绘图画布管理）。
* **Processing (`processing.py`)**: 纯算法层。包含运动校正、比率计算公式 `(Ch1-BG)/(Ch2-BG)` 及 Kymograph 提取逻辑。

---

## 2. 核心功能 (Key Functions)

RIA 整合了从数据导入到最终图表导出的完整工作流，主要功能如下：

### A. 强大的数据预处理
* **多格式直读**: 支持 .oir, .nd2 等原始显微镜数据，不仅限于 TIFF。
* **Z-Stack 投影**: 自动识别 3D 数据，提供最大密度投影 (MIP) 和平均投影 (AIP)，将 3D 数据压扁为 2D 时间序列。
* **运动校正 (Motion Correction)**: 针对活体成像中样本抖动问题，内置一键自动配准功能，极大提高了数据质量。

### B. 专业计算与可视化
* **智能背景扣除**: 支持全局百分比扣除和 **ROI 背景扣除**（用户绘制背景区域，软件动态计算扣除值）。
* **比率计算 (Ratio Calculation)**: 双通道荧光比值计算，内置 NaN 处理和阈值过滤，生成 $\Delta R / R_0$ 数据。
* **高级图表**:
    * **伪彩显示**: 支持多种 LUT (Jet, Viridis 等) 实时渲染。
    * **Kymograph**: 支持沿线绘制时空图，用于分析轴突运输或血流速度。
    * **双轴曲线**: 同时显示比率值和原始强度值，帮助排除运动伪影。

### C. 交互与工程管理
* **ROI 管理**: 支持矩形、圆形、多边形、线条等多种 ROI 绘制、修改和保存。
* **工程文件 (.ria)**: 支持保存完整的分析状态（包括 ROI、阈值、配准矩阵等）为 JSON 格式，方便实验复盘。

---

## 3. 项目意义与价值 (Significance)

这是一个成熟度极高的“科研工具软件”，具有显著的实用价值：

1.  **替代昂贵商业软件**: 提供了类似 cellSens 或 NIS-Elements 的核心分析功能，但完全免费且开源。
2.  **专注于“活体动态分析”**: 整合了 **导入 -> 配准 -> 背景扣除 -> 比率计算 -> ROI 量化** 的标准工作流，特别是集成了运动校正，直击活体成像（如斑马鱼、小鼠）的痛点。
3.  **用户体验优秀**: 具备暗色模式（适合显微镜室环境）、多线程加载（防卡顿）、快捷键操作等细节，是一款真正为实验人员设计的软件。
