<div align="center">
  <img src="https://raw.githubusercontent.com/Epivitae/RatioImagingAnalyzer/main/src/ria_gui/assets/app_ico.png" width="120" alt="Logo">

  <h1>Ratio Imaging Analyzer (RIA / 莉丫)</h1>

  <p>
    <a href="https://pypi.org/project/ria-gui/"><img src="https://img.shields.io/pypi/v/ria-gui?color=blue" alt="PyPI"></a>
    <a href="https://joss.theoj.org/papers/@epivitae"><img src="https://joss.theoj.org/papers/please-replace-with-your-id/status.svg" alt="Status"></a>
    <a href="https://doi.org/10.5281/zenodo.18091693"><img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18091693-0099CC" alt="DOI"></a>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white" alt="Python"></a>
    <a href="LICENSE"><img src="https://img.shields.io/github/license/Epivitae/RatioImagingAnalyzer?color=yellow" alt="License"></a>
  </p>

  <p>
    <a href="https://github.com/Epivitae/RatioImagingAnalyzer/actions/workflows/test.yml"><img src="https://img.shields.io/github/actions/workflow/status/Epivitae/RatioImagingAnalyzer/test.yml?branch=main&label=tests&color=brightgreen" alt="Tests"></a>
    <a href="https://opensource.org/"><img src="https://img.shields.io/badge/Open_Source-Yes-2ea44f?logo=open-source-initiative&logoColor=white" alt="Open Source"></a>
    <img src="https://img.shields.io/github/repo-size/Epivitae/RatioImagingAnalyzer?color=ff69b4" alt="Size">
    <img src="https://img.shields.io/endpoint?color=blueviolet&url=https://gist.githubusercontent.com/Epivitae/65b61a32eaccf5de9624892da2ddd0d8/raw/gistfile1.txt" alt="LOC">
    <img src="https://visitor-badge.laobi.icu/badge?page_id=Epivitae.RatioImagingAnalyzer" alt="Visitors">
  </p>
</div>

---


**Meet RIA (or as we affectionately call her, "Li Ya / 莉丫").**

RIA is an open-source tool built to solve a simple but annoying problem: **Ratiometric analysis shouldn't be stuck on the microscope computer.**

Ratiometric imaging (like FRET or sensors for Tryptophan/pH/Ca²⁺) is amazing for normalizing data, but analyzing it usually requires expensive commercial software (like MetaMorph or NIS-Elements) that is locked to a specific workstation with a dongle.

We built RIA so you can take your TIFF stacks, go to a coffee shop (or just your desk), and run rigorous analysis on your own laptop—no coding required.

<p align="center">
  <img src="https://raw.githubusercontent.com/Epivitae/RatioImagingAnalyzer/main/src/ria_gui/assets/figure/analysis.gif" width="600" alt="RIA Interface showing trace analysis">
</p>


[Image of fluorescence ratiometric imaging process diagram]


## 💡 Why use RIA?

* **Analysis Unchained**: Stop queuing for the lab workstation. RIA is a standalone executable that runs on standard PCs.
* **Math Done Right**: Calculating ratios isn't just `A / B`. Biological images have edges and noise. We implemented a **normalized convolution algorithm** that handles `NaN` (Not a Number) values correctly. This means your data doesn't get eroded or corrupted at cell boundaries—a common issue in simple script-based analysis.
* **Zero Coding Needed**: We know not everyone loves Python. RIA has a full GUI for background subtraction, thresholding, and dragging-and-dropping ROIs.
* **Trust Your Data**: We don't hide the numbers. You get the visual stacks, but you also get the **raw float32 ratio data** and time-series CSVs. You can take these straight to Prism, Origin, or Excel.

## 📁 Project Structure

```text
RatioImagingAnalyzer/
├── data/               # Sample TIFFs so you can try it out immediately
├── paper/              # JOSS submission files
├── src/ria_gui         # The actual code
│   ├── main.py         # Start here
│   ├── gui.py          # The frontend logic
│   ├── processing.py   # The math/algorithm heavy lifting
│   └── components.py   # UI Widgets
├── tests/              # Automated tests to keep bugs away
└── requirements.txt    # Dependencies
```

## 🚀 Installation

### Option 1: Install via PyPI (Recommended for Pythoners)

RIA is available on the Python Package Index. Open your terminal and run:

```bash
pip install ria-gui
```
Once installed, simply type the following command to launch the software:
```bash
ria
```


### Option 2: Running from Source (Recommended for Developers/Reviewers)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Epivitae/RatioImagingAnalyzer.git
   cd RatioImagingAnalyzer
   ```

2. **Install dependencies:**
   It is recommended to use a virtual environment.

   ```bash
   pip install -r requirements.txt
   ```
3. **Run the application:**
   The source code is located in the `src` directory:

   ```bash
   python src/ria_gui/main.py
   ```

### Option 3: Standalone Executable (For End Users)

Check the [Releases](https://github.com/Epivitae/RatioImagingAnalyzer/releases) page to download the latest compiled `.exe` file for Windows. No Python installation is required.

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