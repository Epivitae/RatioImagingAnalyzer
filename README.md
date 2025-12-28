# Ratio Imaging Analyzer (RIA)

[![Status](https://joss.theoj.org/papers/please-replace-with-your-id/status.svg)](https://joss.theoj.org/papers/please-replace-with-your-id)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**Ratio Imaging Analyzer (RIA)** is a lightweight, open-source Python tool designed for the visualization and quantification of ratiometric fluorescence imaging data (e.g., Calcium imaging with Fura-2, Indo-1, or genetically encoded sensors like GCaMP/R-GECO, cpYFP).

It provides a user-friendly Graphical User Interface (GUI) to perform background subtraction, thresholding, and real-time ROI (Region of Interest) analysis without requiring any programming knowledge.

![RIA Interface](paper/images/figure1.png)

## ✨ Key Features

* **Dual-Channel Processing**: Seamlessly loads and aligns multi-page TIFF stacks for two channels.
* **NaN-safe Algorithms**: Implements custom spatial smoothing that handles `NaN` values correctly, preventing data erosion at cell edges.
* **Interactive Analysis**:
    * Real-time background subtraction and intensity thresholding.
    * "Draw-and-Drag" ROI system with instant time-course plotting.
    * Video player with adjustable playback speed.
* **Data Integrity**:
    * Exports processed image stacks (visual data).
    * Exports **raw float32 ratio data** (scientific data) for downstream statistical analysis.
    * Exports time-series traces to CSV/Excel compatible formats.
* **Standalone Capable**: Can be frozen into an executable (`.exe`) for portability on lab computers.

## 📁 Project Structure

```text
RatioImagingAnalyzer/
├── data/               # Example TIFF data for testing
├── paper/              # JOSS paper draft and assets
├── src/                # Source code
│   ├── main.py         # Entry point
│   ├── gui.py          # User Interface logic
│   └── processing.py   # Core algorithms
├── tests/              # Unit tests
└── requirements.txt    # Python dependencies
```

## 🚀 Installation

### Option 1: Running from Source (Recommended for Developers/Reviewers)

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/YourUsername/RatioImagingAnalyzer.git](https://github.com/YourUsername/RatioImagingAnalyzer.git)
    cd RatioImagingAnalyzer
    ```

2.  **Install dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the application:**
    Since the source code is located in the `src` directory, run:
    ```bash
    python src/main.py
    ```

### Option 2: Standalone Executable (For End Users)

Check the [Releases](https://github.com/YourUsername/RatioImagingAnalyzer/releases) page to download the latest compiled `.exe` file for Windows. No Python installation is required.

## 📖 Usage Example

To test the software, you can use the sample data provided in the `data/` directory.

1.  **Launch RIA** (`python src/main.py`).
2.  **Load Files**:
    * Click **📂 Ch1** and select `data/C1.tif`.
    * Click **📂 Ch2** and select `data/C2.tif`.
    * Click **🚀 Load & Analyze**.
3.  **Adjust Parameters**:
    * Set **BG %** (Background Subtraction) to ~5-10%.
    * Adjust **Int. Min** (Intensity Threshold) to remove background noise.
    * *(Optional)* Enable **Log Scale** if the dynamic range is large.
4.  **Analyze**:
    * Click **✏️ Draw ROI** in the "ROI & Measurement" panel.
    * Draw a rectangle on the cell of interest.
    * A curve window will pop up showing the ratio change over time.

## 🧪 Testing

This project uses `pytest` to ensure algorithm accuracy. The tests are located in the `tests/` directory.

To run the automated tests:
```bash
pytest tests/
```

*Note: The tests cover background calculation logic, ratio computation stability, and verification of the NaN-safe smoothing algorithm.*

## 🤝 Contributing

Contributions are welcome! If you encounter any bugs or have feature requests, please check the [Issue Tracker](https://github.com/YourUsername/RatioImagingAnalyzer/issues) or submit a Pull Request.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

## 🖊️ Citation

If you use this software in your research, please cite our software DOI or the associated JOSS paper (under review):

```bibtex
@software{ria_software,
  author = {Wang, Kui},
  title = {Ratio Imaging Analyzer (RIA)},
  year = {2025},
  url = {[https://github.com/YourUsername/RatioImagingAnalyzer](https://github.com/YourUsername/RatioImagingAnalyzer)}
}
```