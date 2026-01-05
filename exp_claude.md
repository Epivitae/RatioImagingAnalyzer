> explain src/ria_gui

● I'll explore the src/ria_gui directory to understand its structure and purpose.

● Search(pattern: "src/ria_gui/**/*")
  ⎿  Found 38 files (ctrl+o to expand)

● Read(src\ria_gui\__init__.py)
  ⎿  Read 1 line

● Read(src\ria_gui\main.py)
  ⎿  Read 286 lines

● Read(src\ria_gui\gui.py)
  ⎿  Read 3205 lines

● Read(src\ria_gui\model.py)
  ⎿  Read 310 lines

● Now let me read a few more key files to understand the complete structure:

● Read(src\ria_gui\processing.py)
  ⎿  Read 100 lines

● Read(src\ria_gui\gui_components.py)
  ⎿  Read 100 lines

● Read(src\ria_gui\constants.py)
  ⎿  Read 74 lines

● Based on my exploration of the src/ria_gui directory, here's a comprehensive explanation:

  RIA GUI - Ratio Imaging Analyzer GUI Module

  The src/ria_gui directory contains a complete Tkinter-based desktop application for analyzing ratiometric imaging data (e.g., calcium imaging with dual-wavelength fluorescence). This is a scientific image analysis tool designed for neuroscience/biology research.

  ---
  Architecture Overview

  The application follows an MVC-like pattern:

  Core Components

  1. main.py - Entry point
    - CLI argument parsing (-v, -s, -i, --debug, --init)
    - Prints ASCII art banner (a fish named "Liya")
    - Launches the Tkinter GUI
    - Supports startup file loading (double-click .ria project files)
  2. gui.py (3200+ lines) - Main application controller
    - RatioAnalyzerApp class - the central GUI controller
    - Manages all UI panels, buttons, sliders, and user interactions
    - Coordinates between Model and View layers
    - Handles threading for I/O operations
  3. model.py - Data model and business logic
    - AnalysisSession class - manages imaging data state
    - File I/O (supports .tif, .nd2, .oir formats)
    - Metadata inspection (ImageJ, AICS formats)
    - Z-stack projection (Max/Average)
    - Background calculation
    - Ratio computation
  4. processing.py - Image processing algorithms
    - Background subtraction
    - Ratio calculation (Ch1/Ch2)
    - Smoothing (OpenCV-based)
    - Motion correction (ECC alignment using OpenCV)
    - Kymograph extraction
  5. gui_components.py - Reusable UI components
    - PlotManager - Matplotlib integration
    - RoiManager - ROI drawing and management
    - Interactive selectors (rectangle, circle, polygon, line)
  6. plot_window.py - Separate plotting window
    - ROIPlotWindow - displays time-series curves
    - Live monitoring mode
    - Data export (CSV, clipboard)
  7. io_utils.py - File I/O utilities
    - Multi-channel TIFF reading
    - Interleaved stack splitting
    - Support for professional formats (OIR, ND2) via aicsimageio
  8. constants.py - Internationalization
    - LANG_MAP - English/Chinese translations
  9. components.py - Custom widgets
    - ToggledFrame - Collapsible panel

  ---
  Key Features

  1. File Loading

  - Single File Mode: Load multi-channel TIFF/ND2/OIR files
  - Separate Files Mode: Load Ch1 and Ch2 from different files
  - Project Mode: Save/load .ria project files (JSON-based)
  - Smart Metadata Detection: Auto-detects channels, Z-stacks, axes order

  2. Image Registration

  - Motion correction using OpenCV's ECC algorithm
  - Aligns time-lapse stacks to compensate for drift
  - Undo functionality

  3. Calibration & Processing

  - Intensity Threshold: Filter low-signal pixels
  - Ratio Threshold: Filter low-ratio pixels
  - Smoothing: Gaussian blur (1-10 pixels)
  - Background Subtraction: Percentile-based (0-50%)
  - Custom BG ROI: Draw region to measure background
  - Log Scale: Logarithmic display

  4. Display Settings

  - Colormaps: coolwarm, jet, viridis, magma
  - Background Color: Transparent, Black, White
  - Lock Range: Manual vmin/vmax control
  - Channel Switching: View Ratio, Ch1, Ch2, or auxiliary channels

  5. ROI Tools

  - Shapes: Rectangle, Circle, Polygon, Line
  - Kymograph: Space-time plot along line ROI
  - Curve Plotting: Time-series analysis with normalization (ΔR/R₀)
  - Live Monitor: Real-time curve updates during playback
  - Save/Load ROIs: JSON format

  6. Data Export

  - Save Frame: Current processed frame as TIFF
  - Save Stack: Full processed stack
  - Save Raw Ratio: Clean ratio stack (no smoothing/log)
  - Save Z-Proj TIFF: Preprocessed input data (for faster reloading)

  7. Playback Controls

  - Frame-by-frame navigation
  - Play/Pause with adjustable FPS (1-20 FPS, Max)
  - Loop mode with custom start/end points

  8. Advanced Features

  - Dark/Light Theme: Toggle with 🌙/☀️ button
  - Font Scaling: A+/A- buttons
  - Bilingual UI: English/Chinese
  - Keyboard Shortcuts: Ctrl+T (new ROI), Ctrl+P (plot), Ctrl+L (live)
  - Update Checker: GitHub API integration

  ---
  Technical Highlights

  Multi-threading

  - File loading runs in background threads with progress callbacks
  - Prevents UI freezing during I/O operations
  - Thread-safe UI updates using root.after()

  Professional Format Support

  - Uses aicsimageio for OIR/ND2 (Olympus/Nikon microscopes)
  - Handles complex metadata (TZCYX axes, ImageJ hyperstack)
  - Z-projection (Max/Average Intensity Projection)

  Matplotlib Integration

  - Embedded canvas with custom toolbar
  - Interactive ROI drawing with matplotlib widgets
  - Colorbar with dynamic range control

  Project System

  - Saves entire analysis state to JSON
  - Relative path resolution (portable projects)
  - Restores ROIs, parameters, alignment matrices, window positions

  Error Handling

  - Graceful degradation (e.g., OpenCV optional for alignment)
  - User-friendly error messages
  - Debug mode with verbose logging

  ---
  File Structure Summary

  src/ria_gui/
  ├── main.py              # Entry point, CLI args
  ├── gui.py               # Main GUI controller (3200 lines)
  ├── model.py             # Data model, session management
  ├── processing.py        # Image processing algorithms
  ├── gui_components.py    # PlotManager, RoiManager
  ├── plot_window.py       # Separate plotting window
  ├── io_utils.py          # File I/O utilities
  ├── constants.py         # Translations (EN/CN)
  ├── components.py        # Custom widgets (ToggledFrame)
  ├── _version.py          # Version string
  └── assets/              # Icons, images
      ├── app_ico.png
      ├── ratiofish.ico
      └── figure/*.gif

  ---
  Use Case

  This tool is designed for calcium imaging analysis in neuroscience:
  1. Load dual-wavelength fluorescence images (e.g., Fura-2: 340nm/380nm)
  2. Calculate ratio (Ch1/Ch2) to measure calcium concentration
  3. Draw ROIs on neurons/cells
  4. Extract time-series curves (ΔF/F or ΔR/R₀)
  5. Export data for statistical analysis

  The GUI provides a complete workflow from raw data to publication-ready figures, with professional features like motion correction, kymographs, and project management.