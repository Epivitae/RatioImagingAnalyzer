# src/processing.py
import numpy as np

# [核心依赖] 必须安装 OpenCV
try:
    import cv2
except ImportError:
    cv2 = None

def calculate_background(stack_data, percentile):
    """
    计算背景值。
    """
    if stack_data is None:
        return 0.0
    return np.nanpercentile(stack_data, percentile)

def smooth_nan_safe(arr, size):
    """
    平滑处理 (Smoothing)。
    [优化] 仅依赖 OpenCV，移除 SciPy 依赖以瘦身。
    """
    if size <= 1: return arr
    
    # 如果没有 OpenCV，直接报错提示用户安装，不再依赖 scipy
    if cv2 is None:
        raise ImportError("Missing Dependency: Please install 'opencv-python' to use Smoothing features.")

    # 确保是 float32
    arr = arr.astype(np.float32)
    k = int(size)
    
    # 1. 生成有效像素掩膜 (1.0 = Valid, 0.0 = NaN)
    valid_mask = (~np.isnan(arr)).astype(np.float32)
    
    # 2. 填充 NaN 为 0
    arr_filled = np.nan_to_num(arr, nan=0.0)
    
    # 3. 归一化卷积 (Normalized Convolution)
    blurred_img = cv2.blur(arr_filled, (k, k))
    blurred_mask = cv2.blur(valid_mask, (k, k))
    
    # 4. 计算结果
    with np.errstate(divide='ignore', invalid='ignore'):
        result = blurred_img / blurred_mask
        
    # 5. 清理无效区域
    result[blurred_mask < 1e-6] = np.nan
    
    return result

def process_frame_ratio(d1_frame, d2_frame, bg1, bg2, int_thresh, ratio_thresh, smooth_size, log_scale=False):
    """
    核心比率计算函数。
    """
    # 1. 类型转换 float32 防止下溢
    img1 = d1_frame.astype(np.float32) - bg1
    img2 = d2_frame.astype(np.float32) - bg2

    # 2. Clip 负值
    img1 = np.clip(img1, 0, None)
    img2 = np.clip(img2, 0, None)

    # 3. 计算 Ratio
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = np.full_like(img1, np.nan)
        np.divide(img1, img2, out=ratio, where=img2 > 0.001)
    
    # 4. 阈值处理
    if int_thresh > 0:
        mask_low = (img1 < int_thresh) | (img2 < int_thresh)
        ratio[mask_low] = np.nan

    if ratio_thresh > 0:
        ratio[ratio < ratio_thresh] = np.nan
        
    # 5. 平滑处理
    if smooth_size > 1:
        ratio = smooth_nan_safe(ratio, int(smooth_size))

    # 6. Log 显示
    if log_scale:
        ratio = np.log1p(ratio)
        
    return ratio

def align_stack_ecc(data1, data2, progress_callback=None):
    """
    图像配准 (ECC)。
    """
    if cv2 is None:
        raise ImportError("Missing Dependency: Please install 'opencv-python' to run Alignment.")

    frames, h, w = data1.shape
    
    mean1 = np.nanmean(data1)
    mean2 = np.nanmean(data2)
    
    if mean1 >= mean2:
        is_c1_ref = True; stack_ref = data1; stack_move = data2
    else:
        is_c1_ref = False; stack_ref = data2; stack_move = data1

    aligned_ref = np.zeros((frames, h, w), dtype=np.float32)
    aligned_move = np.zeros((frames, h, w), dtype=np.float32)
    
    template = stack_ref[0].astype(np.float32)
    template = np.nan_to_num(template, nan=0.0)

    aligned_ref[0] = template
    aligned_move[0] = stack_move[0].astype(np.float32)

    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 1e-5)
    motion_mode = cv2.MOTION_TRANSLATION
    warp_matrix = np.eye(2, 3, dtype=np.float32)

    for i in range(1, frames):
        current_img = stack_ref[i].astype(np.float32)
        current_img = np.nan_to_num(current_img, nan=0.0)

        try:
            (_, warp_matrix) = cv2.findTransformECC(
                template, current_img, warp_matrix, motion_mode, criteria, None, 5
            )
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

    if is_c1_ref: return aligned_ref, aligned_move
    else: return aligned_move, aligned_ref