# Ratio Imaging Analyzer (RIA / 莉丫)

[![Status](https://joss.theoj.org/papers/please-replace-with-your-id/status.svg)](https://joss.theoj.org/papers/please-replace-with-your-id)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**Ratio Imaging Analyzer (RIA, nickname "Li Ya/莉丫")** is a lightweight, open-source Python tool designed to make quantitative ratiometric analysis **accessible and portable**.

Ratiometric imaging is a powerful technique for visualizing dynamic biological processes (e.g., using sensors for Tryptophan, Calcium, or pH) independent of expression levels. However, data analysis often requires expensive commercial software locked to microscope workstations. **RIA empowers researchers to perform rigorous analysis on their own laptops—anywhere, anytime.**

It provides a user-friendly Graphical User Interface (GUI) to perform background subtraction, thresholding, and real-time ROI (Region of Interest) analysis without requiring any programming knowledge.

![RIA Interface](assets/figure/analysis.gif)

## ✨ Key Features

* **Universal & Portable**: Works on standard PCs as a standalone executable. Decouples data analysis from image acquisition.
* **Dual-Channel Processing**: Seamlessly loads and aligns multi-page TIFF stacks for two channels using `tifffile`.
* **NaN-safe Algorithms**: Implements custom spatial smoothing (normalized convolution) that handles `NaN` values correctly, preventing data erosion at cell edges.
* **Interactive Analysis**:
  * Real-time background subtraction and intensity thresholding.
  * "Draw-and-Drag" ROI system with instant time-course plotting.
  * Video player with adjustable playback speed.
* **Data Integrity**:
  * Exports processed image stacks (visual data).
  * Exports **raw float32 ratio data** (scientific data) for downstream statistical analysis.
  * Exports time-series traces to CSV/Excel compatible formats.

## 📁 Project Structure

```text
RatioImagingAnalyzer/
├── data/               # Example TIFF data for testing
├── paper/              # JOSS paper draft and assets
├── src/                # Source code
│   ├── main.py         # Entry point
│   ├── gui.py          # User Interface logic
│   ├── processing.py   # Core algorithms
│   └── components.py   # UI widgets
├── tests/              # Unit tests
└── requirements.txt    # Python dependencies
```

## 🚀 Installation

### Option 1: Running from Source (Recommended for Developers/Reviewers)

1. **Clone the repository:**

   git clone https://github.com/Epivitae/RatioImagingAnalyzer.git
   cd RatioImagingAnalyzer
2. **Install dependencies:**
   It is recommended to use a virtual environment.

   ```bash
   pip install -r requirements.txt
   ```
3. **Run the application:**
   The source code is located in the `src` directory:

   ```bash
   python src/main.py
   ```

### Option 2: Standalone Executable (For End Users)

Check the [Releases](https://github.com/Epivitae/RatioImagingAnalyzer/releases) page to download the latest compiled `.exe` file for Windows. No Python installation is required.

## 📖 Usage Example

To test the software, you can use the sample data provided in the `data/` directory.

1. **Launch RIA** (`python src/main.py`).
2. **Load Files**:
   * Click **📂 Ch1** and select `data/C1.tif`.
   * Click **📂 Ch2** and select `data/C2.tif`.
   * Click **🚀 Load & Analyze**.
3. **Adjust Parameters**:
   * Set **BG %** (Background Subtraction) to ~5-10%.
   * Adjust **Int. Min** (Intensity Threshold) to remove background noise.
   * *(Optional)* Enable **Log Scale** if the dynamic range is large.
4. **Analyze**:
   * Click **✏️ Draw ROI** in the "ROI & Measurement" panel.
   * Draw a rectangle on the cell of interest.
   * A curve window will pop up showing the ratio change over time.

## 🧪 Testing

This project uses `pytest` to ensure algorithm accuracy. The tests are located in the `tests/` directory.

To run the automated tests:

```bash
python -m pytest tests/
```

## 🤝 Contributing

Contributions are welcome! If you encounter any bugs or have feature requests, please check the [Issue Tracker](https://github.com/Epivitae/RatioImagingAnalyzer/issues) or submit a Pull Request.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

## 📚 References & Dependencies

This software relies on the following open-source libraries and methods:

* **Methodology**: Tao, R., Wang, K., et al. (2023). A genetically encoded ratiometric indicator for tryptophan. *Cell Discovery*, 9, 106. [DOI: 10.1038/s41421-023-00608-1](https://doi.org/10.1038/s41421-023-00608-1)
* **NumPy**: Harris, C. R., et al. (2020). Array programming with NumPy. *Nature*, 585(7825), 357–362. [DOI: 10.1038/s41586-020-2649-2](https://doi.org/10.1038/s41586-020-2649-2)
* **SciPy**: Virtanen, P., et al. (2020). SciPy 1.0: Fundamental Algorithms for Scientific Computing in Python. *Nature Methods*, 17, 261–272. [DOI: 10.1038/s41592-019-0686-2](https://doi.org/10.1038/s41592-019-0686-2)
* **Matplotlib**: Hunter, J. D. (2007). Matplotlib: A 2D graphics environment. *Computing in Science & Engineering*, 9(3), 90–95. [DOI: 10.1109/MCSE.2007.55](https://doi.org/10.1109/MCSE.2007.55)
* **Tifffile**: Gohlke, C. (2023). tifffile. PyPI. [URL](https://pypi.org/project/tifffile/)
* **Fiji (Inspiration)**: Schindelin, J., et al. (2012). Fiji: an open-source platform for biological-image analysis. *Nature Methods*, 9(7), 676–682.

## 🖊️ Citation

If you use this software in your research, please cite our software DOI or the associated JOSS paper (under review):

```bibtex
@software{ria_software,
  author = {Wang, Kui},
  title = {Ratio Imaging Analyzer (RIA)},
  year = {2025},
  url = {[https://github.com/Epivitae/RatioImagingAnalyzer](https://github.com/Epivitae/RatioImagingAnalyzer)}
}
```
