# src/processing.py
import numpy as np
# [优化] 删除顶部的 from scipy.ndimage import uniform_filter，移入函数内部

def calculate_background(stack_data, percentile):
    if stack_data is None:
        return 0
    return np.nanpercentile(stack_data, percentile)

def smooth_nan_safe(arr, size):
    """
    使用 SciPy 优化的 NaN 安全平滑算法。
    """
    if size <= 1:
        return arr
    
    # [优化] 延迟导入 Scipy，极大加快软件启动速度
    from scipy.ndimage import uniform_filter
    
    arr = arr.astype(np.float32)
    mask = ~np.isnan(arr)
    arr_filled = np.nan_to_num(arr, nan=0.0)
    
    window_area = size * size
    sum_data = uniform_filter(arr_filled, size=size, mode='constant') * window_area
    sum_mask = uniform_filter(mask.astype(np.float32), size=size, mode='constant') * window_area
    
    with np.errstate(divide='ignore', invalid='ignore'):
        result = sum_data / sum_mask
        
    result[sum_mask < 1e-6] = np.nan
    return result

def process_frame_ratio(d1_frame, d2_frame, bg1, bg2, int_thresh, ratio_thresh, smooth_size, log_scale=False):
    img1 = np.clip(d1_frame - bg1, 0, None)
    img2 = np.clip(d2_frame - bg2, 0, None)

    mask_int = (img1 < int_thresh) | (img2 < int_thresh)

    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = np.divide(img1, img2)
        ratio[img2 == 0] = np.nan 
        ratio[img1 == 0] = 0
    
    ratio[mask_int] = np.nan

    if ratio_thresh > 0:
        ratio[ratio < ratio_thresh] = np.nan
        
    if log_scale:
        ratio = np.log1p(ratio)
    
    if smooth_size > 1:
        ratio = smooth_nan_safe(ratio, int(smooth_size))
        
    return ratio