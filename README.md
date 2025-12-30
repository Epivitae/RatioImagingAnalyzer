# Ratio Imaging Analyzer (RIA / 莉丫)

<div align="center">
  <img src="assets/WK.png" width="120" alt="Logo">

  <h1>Ratio Imaging Analyzer (RIA / 莉丫)</h1>

  <p>
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

... (接你原来的介绍文字)

**Meet RIA (or as we affectionately call her, "Li Ya / 莉丫").**

RIA is an open-source tool built to solve a simple but annoying problem: **Ratiometric analysis shouldn't be stuck on the microscope computer.**

Ratiometric imaging (like FRET or sensors for Tryptophan/pH/Ca²⁺) is amazing for normalizing data, but analyzing it usually requires expensive commercial software (like MetaMorph or NIS-Elements) that is locked to a specific workstation with a dongle.

We built RIA so you can take your TIFF stacks, go to a coffee shop (or just your desk), and run rigorous analysis on your own laptop—no coding required.

<p align="center">
  <img src="assets/figure/analysis.gif" width="70%" alt="RIA Interface showing trace analysis">
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
├── src/                # The actual code
│   ├── main.py         # Start here
│   ├── gui.py          # The frontend logic
│   ├── processing.py   # The math/algorithm heavy lifting
│   └── components.py   # UI Widgets
├── tests/              # Automated tests to keep bugs away
└── requirements.txt    # Dependencies
```

## 🚀 Installation

### Option 1: Running from Source (Recommended for Developers/Reviewers)

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

## Citation
Welcome to use RIA, please cite:<br>
Wang, K. (2025). Ratio Imaging Analyzer (RIA): A Lightweight, Standalone Python Tool for Portable Ratiometric Fluorescence Analysis (v1.7.9.1). Zenodo.<br>
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18091693-blue)](https://doi.org/10.5281/zenodo.18091693)


