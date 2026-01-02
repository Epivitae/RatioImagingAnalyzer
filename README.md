<div align="center">
  <img src="[https://raw.githubusercontent.com/Epivitae/RatioImagingAnalyzer/main/src/ria_gui/assets/app_ico.png](https://raw.githubusercontent.com/Epivitae/RatioImagingAnalyzer/main/src/ria_gui/assets/app_ico.png)" width="120" alt="Logo">

  <h1>Ratio Imaging Analyzer (RIA / 莉丫)</h1>

  <p>
    <a href="[https://pypi.org/project/ria-gui/](https://pypi.org/project/ria-gui/)"><img src="[https://img.shields.io/pypi/v/ria-gui?color=blue](https://img.shields.io/pypi/v/ria-gui?color=blue)" alt="PyPI"></a>
    <a href="[https://joss.theoj.org/papers/@epivitae](https://joss.theoj.org/papers/@epivitae)"><img src="[https://joss.theoj.org/papers/please-replace-with-your-id/status.svg](https://joss.theoj.org/papers/please-replace-with-your-id/status.svg)" alt="Status"></a>
    <a href="[https://doi.org/10.5281/zenodo.18091693](https://doi.org/10.5281/zenodo.18091693)"><img src="[https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18091693-0099CC](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18091693-0099CC)" alt="DOI"></a>
    <a href="[https://www.python.org/downloads/](https://www.python.org/downloads/)"><img src="[https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)" alt="Python"></a>
    <a href="LICENSE"><img src="[https://img.shields.io/github/license/Epivitae/RatioImagingAnalyzer?color=yellow](https://img.shields.io/github/license/Epivitae/RatioImagingAnalyzer?color=yellow)" alt="License"></a>
  </p>

  <p>
    <a href="[https://github.com/Epivitae/RatioImagingAnalyzer/actions/workflows/test.yml](https://github.com/Epivitae/RatioImagingAnalyzer/actions/workflows/test.yml)"><img src="[https://img.shields.io/github/actions/workflow/status/Epivitae/RatioImagingAnalyzer/test.yml?branch=main&label=tests&color=brightgreen](https://img.shields.io/github/actions/workflow/status/Epivitae/RatioImagingAnalyzer/test.yml?branch=main&label=tests&color=brightgreen)" alt="Tests"></a>
    <a href="[https://opensource.org/](https://opensource.org/)"><img src="[https://img.shields.io/badge/Open_Source-Yes-2ea44f?logo=open-source-initiative&logoColor=white](https://img.shields.io/badge/Open_Source-Yes-2ea44f?logo=open-source-initiative&logoColor=white)" alt="Open Source"></a>
    <img src="[https://img.shields.io/github/repo-size/Epivitae/RatioImagingAnalyzer?color=ff69b4](https://img.shields.io/github/repo-size/Epivitae/RatioImagingAnalyzer?color=ff69b4)" alt="Size">
    <img src="[https://img.shields.io/endpoint?color=blueviolet&url=https://gist.githubusercontent.com/Epivitae/65b61a32eaccf5de9624892da2ddd0d8/raw/gistfile1.txt](https://img.shields.io/endpoint?color=blueviolet&url=https://gist.githubusercontent.com/Epivitae/65b61a32eaccf5de9624892da2ddd0d8/raw/gistfile1.txt)" alt="LOC">
    <img src="[https://visitor-badge.laobi.icu/badge?page_id=Epivitae.RatioImagingAnalyzer](https://visitor-badge.laobi.icu/badge?page_id=Epivitae.RatioImagingAnalyzer)" alt="Visitors">
  </p>
</div>

---

**Meet RIA (or as we affectionately call her, "Li Ya / 莉丫").**

RIA is an open-source tool designed to democratize fluorescence imaging analysis. **Whether you are doing Ratiometric Imaging (FRET, pH, Ca²⁺) or Single-Channel Intensity Analysis (GCaMP, Fluo-4), RIA has you covered.**

Originally built to break the reliance on expensive microscope workstations (like MetaMorph or NIS-Elements), RIA allows researchers to perform rigorous, quantitative analysis on their own laptops—no coding required.

<p align="center">
  <img src="[https://raw.githubusercontent.com/Epivitae/RatioImagingAnalyzer/main/src/ria_gui/assets/figure/analysis.gif](https://raw.githubusercontent.com/Epivitae/RatioImagingAnalyzer/main/src/ria_gui/assets/figure/analysis.gif)" width="600" alt="RIA Interface showing trace analysis">
</p>

## 💡 Why use RIA?

* **Universal Analysis (v1.8+)**: Not just for ratios anymore! RIA now fully supports **Single-Channel** time-lapse data. It automatically detects your file type and adapts the workflow.
* **Project Management**: Save your entire analysis session (ROIs, thresholds, background settings) into a lightweight `.ria` file. Open it later to resume exactly where you left off.
* **Math Done Right**: Calculating ratios isn't just `A / B`. We use **normalized convolution algorithms** to handle `NaN` correctly, preventing edge artifacts that plague simple script-based analysis.
* **Analysis Unchained**: A standalone executable that runs on standard PCs. Stop queuing for the lab workstation.
* **Trust Your Data**: You get the visual stacks, but you also get the **raw float32 data** and time-series CSVs. Compatible with Prism, Origin, and Excel.

## 📁 Project Structure (MVC Architecture)

RIA follows a clean Model-View-Controller (MVC) pattern for stability and extensibility.

```text
RatioImagingAnalyzer/
├── data/               # Sample TIFFs
├── src/ria_gui         # Source Code
│   ├── main.py         # Entry point
│   ├── gui.py          # View: UI Layout & Interaction
│   ├── model.py        # Model: Data State & Business Logic (New in v1.8)
│   ├── processing.py   # Core Algorithms (Math/CV2)
│   └── components.py   # Custom Widgets
├── tests/              # Automated E2E Tests
└── requirements.txt    # Dependencies
```

## 🚀 Installation

### Option 1: Install via PyPI (Recommended)

```bash
pip install ria-gui
```
Run:
```bash
ria
```

### Option 2: Running from Source (For Developers)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Epivitae/RatioImagingAnalyzer.git
   cd RatioImagingAnalyzer
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the application:**
   ```bash
   python src/ria_gui/main.py
   ```

### Option 3: Standalone Executable (Windows)
Download the latest `.exe` from [Releases](https://github.com/Epivitae/RatioImagingAnalyzer/releases). No Python required.

## 📖 Usage Workflow

1. **Load Files**: 
   * Supports both **Single-Channel** (Intensity) and **Multi-Channel** (Ratio) Tiff stacks.
   * Drag & drop or browse files. RIA automatically detects the channel structure.
2. **Preprocessing**:
   * **Motion Correction**: Align shaky time-lapse data using the built-in ECC algorithm.
   * **Background**: Set a global background subtraction (Percentile) or use a custom ROI.
3. **Visualization**:
   * Switch views between **Ratio**, **Ch1**, **Ch2**, or **Aux** channels using the toolbar.
4. **Analyze**:
   * Draw ROIs (Rectangle, Circle, Polygon).
   * Click **Plot Curve** to see real-time intensity/ratio changes.
5. **Save & Export**:
   * **Save Project**: Save your session as a `.ria` file.
   * **Export Data**: Copy data to clipboard or save processed images as Tiff stacks.

## 🧪 Automated Testing

RIA v1.8.0 introduces a "Ghost Pilot" automated testing script powered by `rich` to ensure stability.

To run the visual E2E test demo:

```bash
python tests/auto_drive_rich.py
```

## 🤝 Contributing

Contributions are welcome! Please check the [Issue Tracker](https://github.com/Epivitae/RatioImagingAnalyzer/issues) or submit a Pull Request.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

## Citation

If you use **RIA** in your research, please cite:

> Wang, K. (2025). Ratio Imaging Analyzer (RIA): A Lightweight, Standalone Python Tool for Portable Fluorescence Analysis (v1.8.0). Zenodo. [https://doi.org/10.5281/zenodo.18107966](https://doi.org/10.5281/zenodo.18107966)

Or use the BibTeX entry:

```bibtex
@software{Wang_RIA_2025,
  author = {Wang, Kui},
  title = {{Ratio Imaging Analyzer (RIA): A Lightweight, Standalone Python Tool for Portable Fluorescence Analysis}},
  month = dec,
  year = {2025},
  publisher = {Zenodo},
  version = {v1.8.0},
  doi = {10.5281/zenodo.18107966},
  url = {https://doi.org/10.5281/zenodo.18107966}
}
```