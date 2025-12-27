# ==============================================================================
# README.md (完整版，包含图片引用)
# ==============================================================================

# Ratio Imaging Analyzer (RIA)

 ![Version](https://img.shields.io/badge/version-v1.7.5-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Python](https://img.shields.io/badge/python-3.8%2B-yellow)

 **Ratio Imaging Analyzer (RIA)** is a lightweight, user-friendly tool designed for 
 processing and analyzing dual-channel ratiometric fluorescence microscopy data. 
 It is widely used in research fields such as **calcium imaging**, **FRET biosensors**, 
 and **metabolic imaging** (e.g., NADH/NAD+, ATP).

 **RIA (比率成像分析器)** 是一款轻量级、用户友好的科研工具，专为处理双通道比率型荧光
 显微成像数据而设计。广泛应用于**钙成像**、**FRET 生物传感器**以及**代谢成像**研究中。

 ---

 ## 📸 Demo (功能演示)

 ### 1. Automated Workflow (自动化处理流程)
 Easily load Channel 1 and Channel 2 TIFF stacks. The software automatically aligns, 
 subtracts background, and generates the ratiometric heatmap instantly.
 轻松加载双通道 TIFF 序列。软件自动完成对齐、背景扣除，并即时生成比率伪彩热图。

 ![Workflow Demo](assets/figure/analysis.gif)
 *Figure 1: Demonstration of loading data, adjusting threshold parameters, and applying smart range locking. (图1：演示数据加载、阈值参数调整及智能范围锁定功能)*

 <br>

 ### 2. Interactive Analysis & Live Monitoring (交互分析与实时监测)
 Draw Regions of Interest (ROI) to extract mean ratio values. The **"Live Monitor"** # feature updates the plotting curve in real-time as you drag the player or adjust thresholds.
 绘制感兴趣区域 (ROI) 以提取平均比率值。**“实时监测”**功能允许在拖动播放进度条或调整
 阈值参数时，实时刷新并显示动态曲线。

 ![Live Plotting Demo](assets/figure/live-plot.gif)
 *Figure 2: Real-time ROI drawing, curve generation, and data interaction. (图2：实时 ROI 绘制、曲线生成及数据交互演示)*

 ---

 ## ✨ Key Features (核心功能)

 ### 1. Image Processing (图像处理)
 * **Dual-Channel Ratiometric Calculation**: Automatically computes $Ch1 / Ch2$ pixel-by-pixel.
 * **Smart Background Subtraction**: Percentile-based background estimation to remove noise.
 * **NaN-Safe Smoothing**: Custom algorithm to smooth images without edge artifacts or NaN propagation.
 * **Thresholding**: Filter out background noise based on intensity and ratio limits.

 ### 2. Visualization (可视化)
 * **Dynamic Colormaps (LUTs)**: Supports `coolwarm`, `jet`, `viridis`, and more.
 * **Smart Range Locking**: One-click auto-ranging based on global **P1 (1st percentile)** #   and **P99 (99th percentile)** to ignore hot pixels and outliers.
 * **Log Scale**: Support for logarithmic display to view wide-dynamic-range data.
 * **Transparent Background**: Option to make the background transparent for better presentation.

 ### 3. Data Analysis & Export (分析与导出)
 * **Interactive ROI**: Draw rectangular ROIs to extract mean ratio values over time.
 * **Data Export**:
     * **Save Frame**: Export current view as a TIFF image.
     * **Save Stack**: Export the fully processed (colorized) video stack.
     * **Save Raw Ratio**: Export the raw, unprocessed float32 ratio data for downstream analysis.
     * **Clipboard Support**: One-click copy of plotting data (Time vs. Ratio) to Excel/Origin.

 ### 4. User Experience (用户体验)
 * **Bilingual Interface**: Toggle between English and Chinese (中文) instantly.
 * **Responsive UI**: Smooth window resizing with layout protection.
 * **Font Scaling**: Adjustable font sizes for high-resolution screens.

 ---

 ## 🛠️ Quick Start (快速开始)

 ### Option 1: Run the Executable (Recommended)
 Simply download the latest `RatioImagingAnalyzer_v1.7.5.exe` from the 
 [Releases](https://github.com/Epivitae/RatioImagingAnalyzer/releases) page and double-click to run. 
 No installation required.

 ### Option 2: Run from Source
 If you prefer running from Python source code:

 1.  **Clone the repository:**
     ```bash
     git clone [https://github.com/Epivitae/RatioImagingAnalyzer.git](https://github.com/Epivitae/RatioImagingAnalyzer.git)
     cd RatioImagingAnalyzer
     ```

 2.  **Install dependencies:**
     ```bash
     pip install -r requirements.txt
     ```
     *(Dependencies include: `numpy`, `matplotlib`, `tifffile`, `requests`)*

 3.  **Run the application:**
     ```bash
     python src/main.py
     ```

 ---

 ## 📧 Contact

 * **Author**: Dr. Kui Wang
 * **Website**: [https://www.cns.ac.cn](https://www.cns.ac.cn)
 * **Email**: k@cns.ac.cn

 If you find this tool useful for your research, please consider giving this repository a **Star** ⭐!

 ---
 *© 2025 Dr. Kui Wang. All rights reserved.*