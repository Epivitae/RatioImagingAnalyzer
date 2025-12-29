# src/processing.py
import numpy as np
# 新增: 导入 OpenCV
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

# src/processing.py
import numpy as np
# 新增: 导入 OpenCV
try:
    import cv2
except ImportError:
    cv2 = None

# ... (保留原有的 calculate_background, smooth_nan_safe 函数不变) ...

def process_frame_ratio(d1_frame, d2_frame, bg1, bg2, int_thresh, ratio_thresh, smooth_size, log_scale=False):
    # ... (保留原有内容不变) ...
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

# --- 新增: ECC 配准算法 ---
def align_stack_ecc(stack_ref, stack_move, progress_callback=None):
    """
    使用 OpenCV ECC 算法校正图像漂移 (Translation 模式)。
    基于 stack_ref (Ch1) 计算位移，应用到 ref 和 move (Ch2)。
    """
    if cv2 is None:
        raise ImportError("OpenCV not installed. Run 'pip install opencv-python'")

    frames, h, w = stack_ref.shape
    
    # 结果容器
    aligned_ref = np.zeros_like(stack_ref)
    aligned_move = np.zeros_like(stack_move)
    
    # 第一帧作为 Template (基准)
    template = stack_ref[0].astype(np.float32)
    aligned_ref[0] = template
    aligned_move[0] = stack_move[0]

    # ECC 配置: 终止条件 (迭代50次 或 误差<1e-5)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 1e-5)
    motion_mode = cv2.MOTION_TRANSLATION # 仅校正平移，生物数据通常更安全

    # 循环处理
    for i in range(1, frames):
        current_img = stack_ref[i].astype(np.float32)
        
        # 初始化单位矩阵
        warp_matrix = np.eye(2, 3, dtype=np.float32)

        try:
            # 1. 计算变换矩阵 (Template -> Current)
            # Find the transform that maps Template to Current
            (_, warp_matrix) = cv2.findTransformECC(
                template, 
                current_img, 
                warp_matrix, 
                motion_mode, 
                criteria,
                None, # input mask
                5     # gauss filter size (平滑以增加稳定性)
            )
            
            # 2. 应用变换 (使用 WARP_INVERSE_MAP 因为我们需要将 Current 扭曲回 Template)
            # 对 Ch1 (Ref)
            aligned_ref[i] = cv2.warpAffine(
                stack_ref[i], warp_matrix, (w, h), 
                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP
            )
            # 对 Ch2 (Move) - 使用完全相同的矩阵！
            aligned_move[i] = cv2.warpAffine(
                stack_move[i], warp_matrix, (w, h), 
                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP
            )
            
        except cv2.error:
            # 如果配准失败 (如差异过大), 回退到原始帧
            aligned_ref[i] = stack_ref[i]
            aligned_move[i] = stack_move[i]

        # UI 回调
        if progress_callback:
            progress_callback(i, frames)

    return aligned_ref, aligned_move