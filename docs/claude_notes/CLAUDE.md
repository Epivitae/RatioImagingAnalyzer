# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**RIA (Ratio Imaging Analyzer / 莉丫)** is a desktop GUI application for analyzing ratiometric fluorescence imaging data (e.g., calcium imaging, FRET, pH sensors). It's built with Python/Tkinter and designed for neuroscience/biology researchers who need to analyze dual-wavelength microscopy data without commercial software.

**Key Technologies:**
- Python 3.8+ with Tkinter for GUI
- NumPy/Matplotlib for data processing and visualization
- OpenCV for motion correction and image processing
- aicsimageio for professional microscopy formats (OIR, ND2)
- Threading for non-blocking I/O operations

## Development Commands

### Running the Application

```bash
# From source (development mode)
python src/ria_gui/main.py

# After pip install
ria

# With debug logging
python src/ria_gui/main.py --debug

# Open a specific file on startup
python src/ria_gui/main.py path/to/file.tif

# Show system info
python src/ria_gui/main.py --sysinfo

# Inspect file metadata without GUI
python src/ria_gui/main.py --info path/to/file.tif
```

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install as editable package (for development)
pip install -e .

# Install from PyPI
pip install ria-gui
```

### Testing

```bash
# Run automated GUI test (visual E2E test with "ghost pilot")
python tests/auto_drive.py

# Run unit tests (if available)
python -m pytest tests/
```

### Building

The project uses PyInstaller for creating standalone executables (not included in repo). Build configuration would typically be in a `.spec` file.

## Architecture Overview

### MVC-Like Pattern

The codebase follows a Model-View-Controller separation:

**Model Layer (`model.py`):**
- `AnalysisSession` class manages all imaging data state
- Handles file I/O, metadata inspection, Z-projection
- Stores data arrays (`data1`, `data2`, `data_aux`), background values, alignment matrices
- Provides methods like `get_processed_frame()`, `export_processed_stack()`

**View Layer (`gui.py`):**
- `RatioAnalyzerApp` is the main GUI controller (3200+ lines)
- Manages all Tkinter widgets, user interactions, and UI state
- Delegates data operations to `AnalysisSession`
- Uses threading for I/O operations to prevent UI freezing

**Processing Layer (`processing.py`):**
- Pure functions for image processing algorithms
- `calculate_background()`, `process_frame_ratio()`, `smooth_nan_safe()`
- Motion correction via OpenCV's ECC algorithm
- Kymograph extraction for line ROIs

**Components (`gui_components.py`):**
- `PlotManager`: Matplotlib canvas integration, handles image display
- `RoiManager`: Interactive ROI drawing (rectangle, circle, polygon, line)
- `ROIPlotWindow` (in `plot_window.py`): Separate window for time-series curves

### Critical Data Flow

1. **File Loading** (threaded):
   ```
   User selects file → gui.py:load_data() → threading.Thread
   → io_utils.py:read_and_split_multichannel() → model.py:set_data()
   → gui.py:_load_data_post_process() → update UI
   ```

2. **Frame Processing** (real-time):
   ```
   User adjusts slider → gui.py:update_plot()
   → gui.py:get_processed_frame() (collects UI params)
   → model.py:get_processed_frame() (delegates to processing.py)
   → processing.py:process_frame_ratio() → returns processed array
   → PlotManager.update_image() → matplotlib renders
   ```

3. **ROI Analysis** (threaded):
   ```
   User draws ROI → RoiManager stores coordinates
   → User clicks "Plot Curve" → threading.Thread
   → Extract pixels for each frame → Calculate mean/ratio
   → ROIPlotWindow.update_data() → Display curve
   ```

### Threading Model

**Critical Rule:** All UI updates MUST use `root.after(0, callback)` to execute on the main thread. Background threads are used for:
- File I/O (`_load_data_thread`, `_metadata_task`)
- Motion correction (`alignment_task`)
- Stack export (`save_stack_task`, `save_raw_task`)
- ROI curve calculation (`roi_mgr.plot_curve`)

Progress callbacks from background threads use `root.after(0, lambda: update_ui())` pattern.

### Project File Format

`.ria` files are JSON with this structure:
```json
{
  "version": "1.8.1.6",
  "source": {
    "mode": "single|separate",
    "path_dual": "relative/path/to/file.tif",
    "axes": "TZCYX",
    "z_proj_method": "Max (MIP)",
    "channel_roles": {"num": 0, "den": 1}
  },
  "params": {
    "int_thresh": 0,
    "ratio_thresh": 0.0,
    "smooth": 0,
    "bg_percent": 5.0,
    "use_custom_bg": false
  },
  "alignment": {
    "is_aligned": true,
    "matrices": [[...], [...]]  // OpenCV transformation matrices
  },
  "rois": [...],
  "plot_window": {...},
  "kymographs": [...]
}
```

Paths are stored as **relative to the project file** for portability.

## Key Implementation Details

### Metadata Detection (`model.py:inspect_file_metadata`)

The app intelligently detects file structure:
1. Try `aicsimageio.AICSImage` for OIR/ND2 (professional formats)
2. Fall back to `tifffile` for TIFF with ImageJ metadata parsing
3. Infer axes order (TZCYX vs TCZYX) by matching dimensions to metadata
4. Detect explicit multi-channel vs single-channel files

This affects UI state (enables/disables "Mixed Stacks" checkbox, Z-projection dropdown).

### NaN-Safe Smoothing (`processing.py:smooth_nan_safe`)

Uses **normalized convolution** to handle NaN values correctly:
```python
# Standard blur would propagate NaNs incorrectly
# Instead: blur(image * mask) / blur(mask)
valid_mask = (~np.isnan(arr)).astype(np.float32)
arr_filled = np.nan_to_num(arr, nan=0.0)
blurred_img = cv2.blur(arr_filled, (k, k))
blurred_mask = cv2.blur(valid_mask, (k, k))
result = blurred_img / blurred_mask
```

This prevents edge erosion at cell boundaries—a critical issue in biological imaging.

### Theme System

The app supports light/dark themes. When adding new UI elements:
- Use `style="Card.TFrame"` for containers
- Use `style="White.TLabel"` for labels on white backgrounds
- Register text labels in `ui_elements` dict for translation support
- **Never** register dynamic value labels (those showing numbers) in `ui_elements`

Theme colors are in `THEME_COLORS` dict with keys: `bg`, `card`, `text`, `fg_disabled`, `input_bg`, `accent`, `plot_bg`, `plot_fg`, `toolbar_bg`.

### Internationalization

All UI text goes through `self.t(key)` which looks up `constants.py:LANG_MAP`. When adding new UI elements:
```python
self.lbl_new = ttk.Label(parent, text="", style="White.TLabel")
self.ui_elements["lbl_new"] = self.lbl_new  # Register for translation
# In constants.py:
LANG_MAP["lbl_new"] = {"en": "New Feature", "cn": "新功能"}
```

**Exception:** Labels showing dynamic values (e.g., `"Frame 5/100"`) should use prefix `"val_"` in `ui_elements` to skip translation.

## Common Pitfalls

1. **Don't block the main thread:** File I/O, heavy computation, or sleep() calls must be in background threads.

2. **UI updates from threads:** Always use `self.root.after(0, callback)` pattern. Direct widget.config() from threads causes crashes.

3. **Data access during threading:** The `session` object is accessed from multiple threads. Currently not mutex-protected, so avoid concurrent writes.

4. **Matplotlib in Tkinter:** The `PlotManager` owns the matplotlib figure. Don't create additional figures—reuse `self.plot_mgr.ax`.

5. **ROI coordinate systems:** ROI coordinates are in **image pixel space**, not canvas space. The `RoiManager` handles coordinate transformation.

6. **NaN handling:** Use `np.errstate(divide='ignore', invalid='ignore')` context when computing ratios. Check for NaN before operations like `np.percentile()`.

7. **Path handling in projects:** When saving projects, convert absolute paths to relative using `os.path.relpath(path, project_dir)`. When loading, try relative first, then absolute.

## File Organization

```
src/ria_gui/
├── main.py              # Entry point, CLI args, launches GUI
├── gui.py               # Main application controller (RatioAnalyzerApp)
├── model.py             # Data model (AnalysisSession)
├── processing.py        # Image processing algorithms
├── io_utils.py          # File I/O (TIFF, ND2, OIR)
├── gui_components.py    # PlotManager, RoiManager
├── plot_window.py       # ROIPlotWindow (time-series curves)
├── components.py        # Custom widgets (ToggledFrame)
├── constants.py         # Translations (LANG_MAP)
└── _version.py          # Version string
```

**Key Classes:**
- `RatioAnalyzerApp` (gui.py): Main GUI controller, owns all widgets
- `AnalysisSession` (model.py): Data model, owns numpy arrays
- `PlotManager` (gui_components.py): Matplotlib integration
- `RoiManager` (gui_components.py): ROI drawing and management
- `ROIPlotWindow` (plot_window.py): Separate plotting window
- `KymographWindow` (gui.py): Space-time plot for line ROIs

## Dependencies

**Core:**
- numpy<2.0 (array operations)
- matplotlib>=3.5 (plotting)
- tifffile>=2023 (TIFF I/O)
- opencv-python>=4.5 (motion correction, smoothing)

**Professional Formats:**
- aicsimageio>=4.10 (OIR, ND2 support)
- bioformats_jar>=2020 (Java-based format reader)
- imagecodecs>=2023 (compression codecs)

**Optional:**
- scipy>=1.8 (legacy, being phased out)
- requests>=2.25 (update checker)

## Testing Strategy

The project uses a unique "Ghost Pilot" visual testing approach (`tests/auto_drive.py`):
- Launches the actual GUI
- Simulates user interactions (clicks, typing) via Tkinter events
- Uses `rich` library for colorful console output
- Provides visual feedback with a "ghost cursor" overlay

This is an **E2E integration test**, not unit tests. It validates the full user workflow.
