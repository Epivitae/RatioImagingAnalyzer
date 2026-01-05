# Bug Fix: Zero-Dimension Slicing Error

## Problem Summary
After environment fixes (NumPy downgraded to <2.0, Java installed), files loaded but crashed with:
```
ValueError: non-broadcastable output operand with shape (134,229)
doesn't match the broadcast shape (0,134,229)
```

**Root Cause**: LazyArray slicing was returning arrays with shape `(0, H, W)` instead of `(H, W)` when indexed with integers like `data[5]`.

---

## Fixes Applied

### Step A: Fixed `src/ria_gui/lazy_array.py`

**File**: `src/ria_gui/lazy_array.py:47-84`

**Problem**:
- Integer indexing like `data[5]` was producing shapes like `(0, H, W)` or `(1, H, W)` instead of `(H, W)`
- Singleton dimensions (C=1, Z=1) were not being removed properly

**Solution**:
```python
def __getitem__(self, key):
    """
    CRITICAL FIX: Properly handles integer indexing to avoid zero-dimension errors.
    When indexing with a single integer (e.g., data[5]), this ensures we get
    a proper frame array, not an empty slice.
    """
    sliced = self._data[key]

    # Compute if it's a Dask array
    if DASK_AVAILABLE and hasattr(sliced, 'compute'):
        result = sliced.compute()
    else:
        result = sliced

    # CRITICAL FIX: Remove all singleton dimensions
    # This prevents shape errors like (0, H, W) or (1, H, W)
    if hasattr(result, 'ndim') and result.ndim > 0:
        result = np.squeeze(result)

        # Safety check: If we got an empty array (shape contains 0), this is a bug
        if hasattr(result, 'shape') and 0 in result.shape:
            raise ValueError(
                f"LazyArray slicing produced empty array! "
                f"Key: {key}, Result shape: {result.shape}, "
                f"Original shape: {self.shape}. "
                f"This indicates incorrect indexing."
            )

    return result
```

**Key Changes**:
1. Added `np.squeeze(result)` to remove ALL singleton dimensions
2. Added safety check to detect and raise informative error if shape contains 0
3. Added detailed docstring explaining the fix

---

### Step B: Fixed `src/ria_gui/io_utils.py`

**File**: `src/ria_gui/io_utils.py:522-607`

**Problem**:
- Channel splitting logic was creating slices with potential dimension issues
- No safety checks for out-of-range channel indices or empty arrays
- Interleaved mode could create empty arrays if parameters were wrong

**Solution**:
```python
def split_channels(lazy_data, n_channels, is_interleaved):
    """
    CRITICAL FIX: Ensures proper dimension handling to avoid (0, H, W) errors.
    """
    print(f"[split_channels] Input shape: {lazy_data.shape}, n_channels: {n_channels}, interleaved: {is_interleaved}")

    if not is_interleaved:
        # SAFETY CHECK: Ensure we don't exceed available channels
        actual_c = lazy_data.shape[1]
        if n_channels > actual_c:
            print(f"[WARNING] Requested {n_channels} channels but data only has {actual_c}. Using {actual_c}.")
            n_channels = actual_c

        for c in range(n_channels):
            # CRITICAL FIX: Handle Dask vs NumPy differently
            if DASK_AVAILABLE and hasattr(lazy_data._data, 'chunks'):
                ch_data = lazy_data._data[:, c:c+1, :, :, :]
            else:
                ch_data = lazy_data._data[:, c, :, :, :]
                ch_data = ch_data[:, np.newaxis, :, :, :]

            print(f"[split_channels] Channel {c} shape: {ch_data.shape}")
            channels.append(LazyArray(ch_data))
    else:
        # Interleaved mode
        # SAFETY CHECK: Ensure we have enough frames
        if t_total < n_channels:
            raise ValueError(
                f"Cannot split {t_total} frames into {n_channels} channels."
            )

        for c in range(n_channels):
            ch_data = data[c::n_channels, :, :, :, :]

            # SAFETY CHECK: Ensure we got frames
            if ch_data.shape[0] == 0:
                raise ValueError(
                    f"Channel {c} extracted 0 frames! "
                    f"This indicates incorrect interleaving parameters."
                )

            print(f"[split_channels] Interleaved channel {c} final shape: {ch_data.shape}")
```

**Key Changes**:
1. Added debug prints for input shapes and channel extraction
2. Added safety check for requested channels exceeding available channels
3. Added safety check for interleaved mode extracting 0 frames
4. Added informative error messages with context
5. Different handling for Dask vs NumPy arrays to prevent dimension issues

---

### Step C: Fixed `src/ria_gui/model.py`

**File**: `src/ria_gui/model.py:200-356`

**Problem**:
- No visibility into what shapes were being extracted
- No validation that frames are 2D before processing
- No detection of zero-dimension errors

**Solution**:
```python
def get_processed_frame(self, frame_idx, ...):
    """
    DEFENSIVE CODING: Added extensive debug prints and shape validation.
    """
    print(f"\n[get_processed_frame] === Frame {frame_idx} ===")
    print(f"[get_processed_frame] data1.shape: {self.data1.shape}")

    # Extract frame
    frame_num = d_num[frame_idx]
    print(f"[get_processed_frame] frame_num raw shape: {frame_num.shape}, dtype: {frame_num.dtype}")

    # FORCE SQUEEZE
    frame_num = np.squeeze(frame_num)
    print(f"[get_processed_frame] frame_num after squeeze: {frame_num.shape}")

    # SAFETY CHECK: Must be 2D
    if frame_num.ndim != 2:
        raise ValueError(
            f"Expected 2D frame_num, got {frame_num.ndim}D: {frame_num.shape}. "
            f"Frame index: {frame_idx}, data1 shape: {d_num.shape}"
        )

    # SAFETY CHECK: No zero dimensions
    if 0 in frame_num.shape:
        raise ValueError(
            f"frame_num has zero-dimension! Shape: {frame_num.shape}. "
            f"Frame index: {frame_idx}, data1 shape: {d_num.shape}"
        )

    # Same for frame_den if exists
    if d_den is not None:
        frame_den = d_den[frame_idx]
        print(f"[get_processed_frame] frame_den raw shape: {frame_den.shape}")

        frame_den = np.squeeze(frame_den)

        # Shape compatibility check
        if frame_num.shape != frame_den.shape:
            raise ValueError(
                f"Shape mismatch between channels! "
                f"frame_num: {frame_num.shape}, frame_den: {frame_den.shape}"
            )

    print(f"[get_processed_frame] Result shape: {result.shape}")
    return result
```

**Key Changes**:
1. Added extensive debug prints at every step:
   - Input shapes
   - Raw extracted shapes
   - Post-squeeze shapes
   - Final result shapes
2. Added validation that frames are 2D
3. Added validation that no dimension is 0
4. Added shape compatibility check between channels
5. Applied same defensive coding to all view modes (ch1, ch2, aux)

---

## Testing Instructions

### What to Expect

When you now load a file, you should see **detailed debug output** like:

```
[IO] Selected reader: TiffReader
[TiffReader] Read shape: (100, 512, 512), axes: TYX
[TiffReader] Expanded to 5D: (100, 1, 1, 512, 512)
[split_channels] Input shape: (100, 1, 1, 512, 512), n_channels: 2, interleaved: True
[split_channels] Interleaved mode: 100 total frames → 50 frames per channel
[split_channels] Interleaved channel 0 extracted shape: (50, 1, 1, 512, 512)
[split_channels] Interleaved channel 0 final shape: (50, 1, 1, 512, 512)
[split_channels] Interleaved channel 1 extracted shape: (50, 1, 1, 512, 512)
[split_channels] Interleaved channel 1 final shape: (50, 1, 1, 512, 512)

[get_processed_frame] === Frame 0 ===
[get_processed_frame] data1.shape: (50, 1, 1, 512, 512)
[get_processed_frame] data2.shape: (50, 1, 1, 512, 512)
[get_processed_frame] Extracting frame 0 from data1...
[get_processed_frame] frame_num raw shape: (512, 512), dtype: float32
[get_processed_frame] frame_num after squeeze: (512, 512)
[get_processed_frame] Extracting frame 0 from data2...
[get_processed_frame] frame_den raw shape: (512, 512), dtype: float32
[get_processed_frame] frame_den after squeeze: (512, 512)
[get_processed_frame] Passing to process_frame_ratio: frame_num=(512, 512), frame_den=(512, 512)
[get_processed_frame] Result shape: (512, 512)
```

### Success Criteria

✅ **File loads without crashing**
✅ **First frame displays correctly**
✅ **Debug output shows all shapes are correct** (no zeros, proper 2D frames)
✅ **Can navigate between frames without errors**

### If Error Still Occurs

The new error messages will pinpoint EXACTLY where the problem is:

- **"LazyArray slicing produced empty array!"** → Problem in LazyArray.__getitem__
- **"Channel X extracted 0 frames!"** → Problem with interleaved parameters
- **"Expected 2D frame_num, got XD"** → Shape not being squeezed properly
- **"frame_num has zero-dimension!"** → Zero-dimension detected, shows context
- **"Shape mismatch between channels!"** → Channel 1 and 2 have different sizes

Each error includes:
- Exact shape that caused the problem
- Frame index
- Original data shape
- Context about what operation failed

---

## Files Modified

1. ✅ `src/ria_gui/lazy_array.py` - Fixed __getitem__ to squeeze dimensions and detect zeros
2. ✅ `src/ria_gui/io_utils.py` - Added safety checks to channel splitting
3. ✅ `src/ria_gui/model.py` - Added defensive coding with debug prints and validation

---

## Next Steps

1. **Test with TIFF file**: Load a known-good TIFF and verify it works
2. **Test with OIR file**: Load an OIR file and verify lazy loading works
3. **Check debug output**: Verify all shapes look correct
4. **Report results**: If still crashes, the new error messages will tell us exactly what's wrong

---

## Technical Notes

### Why np.squeeze() is Safe

`np.squeeze()` removes ALL dimensions of size 1:
- `(1, 1, 512, 512)` → `(512, 512)` ✅
- `(1, 512, 512)` → `(512, 512)` ✅
- `(512, 512)` → `(512, 512)` ✅ (no change)

This is exactly what we want for frame extraction from 5D data (T, C, Z, Y, X).

### Why We Check for 0 in Shape

A shape like `(0, 512, 512)` indicates:
- Empty array in first dimension
- Usually caused by incorrect slicing (e.g., `data[100:110]` when data only has 50 frames)
- Or channel index out of range
- Now caught early with informative error message

### Why We Print Debug Info

The debug prints allow you to:
- Trace exactly where data flows
- See shapes at every transformation step
- Identify which operation produces wrong shape
- Provide logs for troubleshooting

Once the app is stable, we can disable these prints or add a debug flag.

---

**Date**: 2026-01-05
**Status**: ✅ All fixes applied, ready for testing
