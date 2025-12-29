# src/processing.py
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

def calculate_background(stack_data, percentile):
    if stack_data is None:
        return 0
    return np.nanpercentile(stack_data, percentile)

def smooth_nan_safe(arr, size):
    """
    SciPy NaN-safe smoothing.
    """
    if size <= 1: return arr
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
    # 1. 减背景 (保留 NaN，因为 NaN - bg = NaN)
    img1 = d1_frame - bg1
    img2 = d2_frame - bg2

    # 2. Clip 负值为 0 (NaN 会保持为 NaN)
    # 注意：这里我们不 clip 上限，只处理负底噪
    img1 = np.clip(img1, 0, None)
    img2 = np.clip(img2, 0, None)

    # 3. 计算 Ratio
    # 关键逻辑：如果 img2 太小 (接近0或为NaN)，结果设为 NaN
    # 使用 out=np.nan 初始化，只在 where 条件满足时计算
    with np.errstate(divide='ignore', invalid='ignore'):
        # 设定一个极小的 epsilon 防止除零 (0.001 对应 uint16 来说远小于 1)
        ratio = np.divide(img1, img2, out=np.full_like(img1, np.nan), where=img2 > 0.001)
        
        # 兼容旧逻辑：分子为0时，结果为0 (背景平滑)
        # 但只有在分母有效时才设为0
        ratio[(img1 == 0) & (img2 > 0.001)] = 0
    
    # 4. 应用强度阈值 (Int. Min)
    if int_thresh > 0:
        # 如果原始信号低于阈值，也标记为 NaN
        mask_low = (img1 < int_thresh) | (img2 < int_thresh)
        ratio[mask_low] = np.nan

    # 5. 应用比率阈值
    if ratio_thresh > 0:
        ratio[ratio < ratio_thresh] = np.nan
        
    if log_scale:
        ratio = np.log1p(ratio)
    
    if smooth_size > 1:
        ratio = smooth_nan_safe(ratio, int(smooth_size))
        
    return ratio

def align_stack_ecc(data1, data2, progress_callback=None):
    """
    自动选择较亮通道作为基准进行 ECC 配准。
    """
    if cv2 is None:
        raise ImportError("OpenCV not installed.")

    frames, h, w = data1.shape
    
    # --- 1. 自动检测较亮通道 ---
    # 计算全栈平均值（简单有效）
    mean1 = np.mean(data1)
    mean2 = np.mean(data2)
    
    # 确定谁是基准 (ref), 谁是跟随 (move)
    if mean1 >= mean2:
        is_c1_ref = True
        stack_ref = data1
        stack_move = data2
    else:
        is_c1_ref = False
        stack_ref = data2
        stack_move = data1

    # 初始化输出 (float32 以支持 NaN)
    aligned_ref = np.zeros((frames, h, w), dtype=np.float32)
    aligned_move = np.zeros((frames, h, w), dtype=np.float32)
    
    template = stack_ref[0].astype(np.float32)
    aligned_ref[0] = template
    aligned_move[0] = stack_move[0].astype(np.float32)

    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 1e-5)
    motion_mode = cv2.MOTION_TRANSLATION

    for i in range(1, frames):
        current_img = stack_ref[i].astype(np.float32)
        warp_matrix = np.eye(2, 3, dtype=np.float32)

        try:
            (_, warp_matrix) = cv2.findTransformECC(
                template, current_img, warp_matrix, motion_mode, criteria, None, 5
            )
            
            # 应用变换，填充 NaN
            aligned_ref[i] = cv2.warpAffine(
                stack_ref[i].astype(np.float32), warp_matrix, (w, h), 
                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_CONSTANT, borderValue=np.nan 
            )
            aligned_move[i] = cv2.warpAffine(
                stack_move[i].astype(np.float32), warp_matrix, (w, h), 
                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_CONSTANT, borderValue=np.nan
            )
        except cv2.error:
            aligned_ref[i] = stack_ref[i].astype(np.float32)
            aligned_move[i] = stack_move[i].astype(np.float32)

        if progress_callback: progress_callback(i, frames)

    # --- 2. 按原始顺序返回 ---
    if is_c1_ref:
        return aligned_ref, aligned_move
    else:
        return aligned_move, aligned_ref