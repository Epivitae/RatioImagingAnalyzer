import numpy as np

def calculate_background(stack_data, percentile):
    """
    Calculate the background level of the image stack using percentiles.
    This estimates the background noise level from the darkest regions.
    """
    if stack_data is None:
        return 0
    # np.nanpercentile ignores NaNs during calculation
    return np.nanpercentile(stack_data, percentile)

def smooth_nan_safe(arr, size):
    """
    Pure NumPy implementation of NaN-safe spatial smoothing (Normalized Convolution).
    Similar to SciPy's uniform_filter but solves two key issues:
    1. Prevents NaN propagation: Standard smoothing turns the result to NaN if any neighbor is NaN.
    2. Edge correction: Ensures accurate averaging at the boundaries of valid data masks.
    """
    if size <= 1:
        return arr
    
    # 1. Create a mask of valid data points
    mask = ~np.isnan(arr)
    # 2. Replace NaNs with 0 in the original array for convolution
    arr_filled = np.nan_to_num(arr, nan=0.0)
    
    # Define a fast sliding window sum function
    def fast_sum_convolve(a, s):
        res = np.zeros_like(a)
        offset = s // 2
        # Roll and accumulate in 2D space
        for i in range(s):
            for j in range(s):
                res += np.roll(np.roll(a, i - offset, axis=0), j - offset, axis=1)
        return res

    # Calculate sum of data and sum of valid weights (mask)
    sum_data = fast_sum_convolve(arr_filled, size)
    sum_mask = fast_sum_convolve(mask.astype(float), size)
    
    # Normalize: Average = Sum / Count of valid pixels
    with np.errstate(divide='ignore', invalid='ignore'):
        result = sum_data / sum_mask
        
    # If a region is entirely NaN (sum_mask is 0), result remains NaN
    result[sum_mask < 1e-6] = np.nan
    return result

def process_frame_ratio(d1_frame, d2_frame, bg1, bg2, int_thresh, ratio_thresh, smooth_size, log_scale=False):
    """
    Core logic for single-frame processing:
    BG Subtraction -> Intensity Thresholding -> Ratio Calculation -> Ratio Thresholding -> (Log) -> Smoothing.
    """
    # 1. Subtract background and clip negative values
    img1 = np.clip(d1_frame - bg1, 0, None)
    img2 = np.clip(d2_frame - bg2, 0, None)

    # 2. Intensity threshold mask: Mark as invalid if either channel is too dim
    mask_int = (img1 < int_thresh) | (img2 < int_thresh)

    # 3. Calculate Ratio (Ch1 / Ch2)
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = np.divide(img1, img2)
        # Handle division by zero
        ratio[img2 == 0] = np.nan 
        ratio[img1 == 0] = 0
    
    # Apply intensity mask
    ratio[mask_int] = np.nan

    # 4. Ratio threshold mask: Remove biologically impossible low ratios
    if ratio_thresh > 0:
        ratio[ratio < ratio_thresh] = np.nan
        
    # 5. Logarithmic transformation (Optional)
    if log_scale:
        ratio = np.log1p(ratio)
    
    # 6. Spatial smoothing: Applied after ratio calculation to reduce noise
    if smooth_size > 1:
        ratio = smooth_nan_safe(ratio, int(smooth_size))
        
    return ratio