import numpy as np
from scipy.ndimage import uniform_filter

def calculate_background(stack_data, percentile):
    """
    计算图像堆栈的背景值。
    """
    if stack_data is None:
        return 0
    return np.nanpercentile(stack_data, percentile)

def smooth_nan_safe(arr, size):
    """
    NaN-safe 平滑算法 (Normalized Convolution)。
    解决传统平滑会导致边缘 NaN 扩散的问题。
    """
    if size <= 1:
        return arr
    
    arr_copy = arr.copy()
    mask = ~np.isnan(arr_copy)
    arr_copy[~mask] = 0 
    
    # 分别平滑数据和掩膜
    smoothed_data = uniform_filter(arr_copy, size=size, mode='constant')
    smoothed_mask = uniform_filter(mask.astype(float), size=size, mode='constant')
    
    with np.errstate(divide='ignore', invalid='ignore'):
        result = smoothed_data / smoothed_mask
        
    # 如果掩膜值太小，说明周围全是NaN
    result[smoothed_mask < 1e-6] = np.nan
    return result

def process_frame_ratio(d1_frame, d2_frame, bg1, bg2, int_thresh, ratio_thresh, smooth_size, log_scale=False):
    """
    处理单帧图像：扣背景 -> 阈值 -> 比率计算 -> 平滑。
    这是核心业务逻辑，独立出来方便测试。
    """
    # 1. 扣背景
    img1 = np.clip(d1_frame - bg1, 0, None)
    img2 = np.clip(d2_frame - bg2, 0, None)

    # 2. 强度阈值 (Mask)
    mask_int = (img1 < int_thresh) | (img2 < int_thresh)

    # 3. 计算比值
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = np.divide(img1, img2)
        # 处理除零错误
        ratio[img2 == 0] = np.nan 
        ratio[img1 == 0] = 0
    
    # 应用强度掩膜
    ratio[mask_int] = np.nan

    # 4. 比值阈值过滤
    if ratio_thresh > 0:
        ratio[ratio < ratio_thresh] = np.nan
        
    # 5. 对数变换
    if log_scale:
        ratio = np.log1p(ratio)
    
    # 6. 平滑
    if smooth_size > 1:
        ratio = smooth_nan_safe(ratio, smooth_size)
        
    return ratio