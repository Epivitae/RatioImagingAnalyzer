# 🚀 START HERE - Bugfix Testing Guide

**Date**: 2026-01-05
**Issue Fixed**: Zero-dimension slicing error that crashed file loading
**Status**: ✅ Ready to test

---

## What Was Fixed

The app was crashing with this error:
```
ValueError: non-broadcastable output operand with shape (134,229)
doesn't match the broadcast shape (0,134,229)
```

**Root cause**: LazyArray was returning `(0, H, W)` instead of `(H, W)` when extracting frames.

**Solution**: Fixed 3 files to properly squeeze dimensions and add safety checks.

---

## Quick Test (Do This Now!)

### 1️⃣ Launch the GUI

```bash
cd D:\2_Greek\RatioImagingAnalyzer
python src/ria_gui/gui.py
```

### 2️⃣ Load a Test File

**Recommended order**:
1. ✅ Start with a **TIFF file** (simpler, no Java issues)
2. Then try an **OIR file** (requires working Java/aicsimageio)

### 3️⃣ What You Should See

**In the GUI**:
- ✅ File loads successfully (no crash)
- ✅ First frame displays
- ✅ Can navigate between frames

**In the console** (you should see debug output like this):
```
[IO] Selected reader: TiffReader
[TiffReader] Read shape: (100, 512, 512), axes: TYX
[TiffReader] Expanded to 5D: (100, 1, 1, 512, 512)

[split_channels] Input shape: (100, 1, 1, 512, 512), n_channels: 2, interleaved: True
[split_channels] Interleaved channel 0 shape: (50, 1, 1, 512, 512)
[split_channels] Interleaved channel 1 shape: (50, 1, 1, 512, 512)

[get_processed_frame] === Frame 0 ===
[get_processed_frame] data1.shape: (50, 1, 1, 512, 512)
[get_processed_frame] Extracting frame 0 from data1...
[get_processed_frame] frame_num raw shape: (512, 512)
[get_processed_frame] frame_num after squeeze: (512, 512)
[get_processed_frame] Extracting frame 0 from data2...
[get_processed_frame] frame_den raw shape: (512, 512)
[get_processed_frame] frame_den after squeeze: (512, 512)
[get_processed_frame] Passing to process_frame_ratio: frame_num=(512, 512), frame_den=(512, 512)
[get_processed_frame] Result shape: (512, 512)
```

**✅ Good signs**:
- All shapes end with `(H, W)` - two dimensions only
- No shapes with `0` in them
- No crash when displaying frame

**❌ Bad signs**:
- Shape contains `0` like `(0, 512, 512)`
- Shape has wrong dimensions like `(1, 512, 512)` or `(512, 512, 1)`
- Error message with "LazyArray slicing produced empty array"

---

## If It Works ✅

Congratulations! The bugfix is successful. You can now:

1. **Disable debug prints** (optional):
   - Edit `src/ria_gui/model.py` line 214-355
   - Comment out or remove `print()` statements
   - Keeps console clean in production

2. **Test with large files**:
   - Try your 5GB+ OIR files
   - Verify lazy loading works (minimal memory usage)
   - Check performance is good

3. **Continue development**:
   - The lazy loading refactoring is complete
   - All features should work normally

---

## If It Still Crashes ❌

### The New Error Messages Will Help!

The fixes include extensive error messages that tell you **exactly** what's wrong:

**Example 1: Zero dimension detected**
```
ValueError: frame_num has zero-dimension! Shape: (0, 512, 512).
Frame index: 5, data1 shape: (100, 1, 1, 512, 512)
```
→ This tells you frame 5 has an empty first dimension

**Example 2: Wrong dimensions**
```
ValueError: Expected 2D frame_num, got 3D: (1, 512, 512).
Frame index: 0, data1 shape: (100, 1, 1, 512, 512)
```
→ This tells you squeeze didn't work, frame still has 3 dimensions

**Example 3: Shape mismatch**
```
ValueError: Shape mismatch between channels!
frame_num: (512, 512), frame_den: (256, 256).
Frame index: 0
```
→ This tells you channel 1 and channel 2 have different image sizes

### What to Do If You Get Errors:

1. **Copy the full error message** (including the stack trace)
2. **Copy the console output** (all the debug prints above the error)
3. **Tell me**:
   - What file you were loading (TIFF? OIR? How big?)
   - What settings you used (interleaved? how many channels?)
   - The error message and console output

The debug information will pinpoint exactly what needs adjustment.

---

## Files That Were Changed

If you need to review the changes:

1. **`src/ria_gui/lazy_array.py`** (lines 47-84)
   - Core fix: Squeeze dimensions, detect zeros

2. **`src/ria_gui/io_utils.py`** (lines 522-607)
   - Channel splitting safety checks

3. **`src/ria_gui/model.py`** (lines 200-356)
   - Defensive coding, debug prints

**Documentation**:
- `BUGFIX_ZERO_DIMENSION.md` - Technical details of fixes
- `VERIFICATION_RESULTS.md` - Test results
- `START_HERE.md` - This file!

---

## Troubleshooting

### Problem: Console output is too verbose

**Solution**: Once everything works, you can reduce debug output:
- Edit `model.py` and comment out the `print()` statements
- Keep the safety checks (the `if` statements that raise `ValueError`)

### Problem: Import errors or segfaults

**Possible causes**:
1. NumPy version issue → Use `pip install "numpy<2.0"`
2. Java not configured → OIR files need Java, try TIFF first
3. aicsimageio issue → Update: `pip install -U aicsimageio`

### Problem: File loads but image is blank

**Possible causes**:
1. Background subtraction too aggressive → Adjust background percentage
2. Ratio threshold too high → Lower the threshold
3. Data range issue → Check the intensity values in debug output

---

## Quick Reference: File Loading Flow

```
User clicks "Load File"
    ↓
get_reader() selects TiffReader or AICSReader
    ↓
read_metadata() checks axes, channels, Z-slices
    ↓
read_lazy() loads as LazyArray (Dask for OIR, NumPy for TIFF)
    ↓
split_channels() splits into channel 1, channel 2, etc.
    ↓
set_data() stores channels in session
    ↓
recalc_background() samples first 10 frames
    ↓
User views frame 0
    ↓
get_processed_frame(0) called
    ↓
LazyArray[0] extracts and squeezes frame
    ↓
process_frame_ratio() calculates ratio
    ↓
Frame displayed in GUI ✅
```

---

## Next Steps After Testing

### ✅ If successful:
1. Test with all your file types (TIFF, OIR, ND2)
2. Test with different channel configurations
3. Consider reducing debug output for production
4. Continue using the app normally

### ❌ If issues remain:
1. Capture error messages and debug output
2. Note what file/settings triggered the error
3. Report back - the diagnostics will show exactly what needs fixing

---

## Summary

**What to do RIGHT NOW**:
```bash
python src/ria_gui/gui.py
```
Load a file and check if it works!

**Expected result**: File loads, frame displays, no crash ✅

**If it crashes**: Error messages will tell us exactly what's wrong

---

**Good luck! The fixes are in place and verified. Time to test! 🚀**

Questions? Issues? The debug output will provide all the information needed to troubleshoot.
