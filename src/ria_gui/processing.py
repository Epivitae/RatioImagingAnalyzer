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
    [修改] 增加了单通道模式支持 (d2_frame is None)。
    """
    # 1. 类型转换 float32 防止下溢
    img1 = d1_frame.astype(np.float32) - bg1
    img1 = np.clip(img1, 0, None)

    # [修改] 单通道模式检测
    if d2_frame is None:
        # 单通道模式：仅做强度阈值处理
        if int_thresh > 0:
            img1[img1 < int_thresh] = np.nan # 或者 0，视需求而定，这里用 NaN 保持背景干净
        
        # 单通道通常不需要 Log Scale，但如果你想保留也可以
        # if log_scale: img1 = np.log1p(img1)
        return img1

    # --- 以下为原本的双通道比率逻辑 ---
    img2 = d2_frame.astype(np.float32) - bg2
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
    [修改] 返回值增加了 matrices 列表
    Returns: (aligned_1, aligned_2, matrices_list)
    """
    if cv2 is None: raise ImportError("OpenCV required.")

    frames, h, w = data1.shape
    
    # 简单的参考帧选择逻辑
    mean1 = np.nanmean(data1)
    mean2 = np.nanmean(data2)
    is_c1_ref = (mean1 >= mean2)
    stack_ref = data1 if is_c1_ref else data2
    stack_move = data2 if is_c1_ref else data1

    aligned_ref = np.zeros((frames, h, w), dtype=np.float32)
    aligned_move = np.zeros((frames, h, w), dtype=np.float32)
    
    template = np.nan_to_num(stack_ref[0].astype(np.float32), nan=0.0)
    aligned_ref[0] = template
    aligned_move[0] = stack_move[0].astype(np.float32)

    # 存储矩阵
    # 格式：List of 2x3 numpy arrays
    matrices = []
    
    # 第0帧是单位矩阵 (无位移)
    eye_matrix = np.eye(2, 3, dtype=np.float32)
    matrices.append(eye_matrix)

    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 1e-5)
    motion_mode = cv2.MOTION_TRANSLATION # 或者 MOTION_EUCLIDEAN
    
    # 当前的变换矩阵 (累积)
    warp_matrix = np.eye(2, 3, dtype=np.float32)

    for i in range(1, frames):
        current_img = np.nan_to_num(stack_ref[i].astype(np.float32), nan=0.0)

        try:
            # 计算矩阵
            (_, warp_matrix) = cv2.findTransformECC(
                template, current_img, warp_matrix, motion_mode, criteria, None, 5
            )
            
            # 应用矩阵
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
            
            # 保存该帧的矩阵 (深拷贝)
            matrices.append(warp_matrix.copy())

        except cv2.error:
            # 配准失败，使用上一帧的矩阵或单位矩阵
            # 这里简单处理：不做变换
            aligned_ref[i] = stack_ref[i].astype(np.float32)
            aligned_move[i] = stack_move[i].astype(np.float32)
            matrices.append(np.eye(2, 3, dtype=np.float32)) # 记录无位移

        if progress_callback: progress_callback(i, frames)

    # 返回结果：根据谁是参考帧，决定返回顺序
    # 重要：我们也需要保存“谁是参考帧”的信息，但为了简化，我们假设矩阵是用于 warp_inverse 的
    if is_c1_ref: 
        return aligned_ref, aligned_move, matrices
    else: 
        return aligned_move, aligned_ref, matrices





def apply_alignment_matrices(data, matrices):
    """
    [新增] 快速应用已知的矩阵列表
    """
    if cv2 is None: raise ImportError("OpenCV required.")
    if data is None: return None
    
    frames, h, w = data.shape
    aligned = np.zeros_like(data, dtype=np.float32)
    
    # 确保矩阵数量匹配
    count = min(frames, len(matrices))
    
    for i in range(count):
        mat = matrices[i]
        src = data[i].astype(np.float32)
        
        # 检查是否是单位矩阵 (无需变换)
        if np.allclose(mat, np.eye(2, 3, dtype=np.float32)):
            aligned[i] = src
        else:
            aligned[i] = cv2.warpAffine(
                src, mat, (w, h),
                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_CONSTANT, borderValue=np.nan
            )
            
    return aligned




def extract_kymograph(stack, p1, p2):
    """
    从图像堆栈中提取沿直线的 Kymograph 数据。
    stack: (Frames, Height, Width)
    p1: (x1, y1) 起点
    p2: (x2, y2) 终点
    返回: (Frames, Distance) 的 2D 矩阵
    """
    import numpy as np
    
    # 1. 计算两点间距离 (作为 Kymograph 的宽度)
    x1, y1 = p1
    x2, y2 = p2
    length = int(np.hypot(x2 - x1, y2 - y1))
    
    if length == 0: return None

    # 2. 生成采样坐标 (使用线性插值)
    x_coords = np.linspace(x1, x2, length)
    y_coords = np.linspace(y1, y2, length)
    
    # 3. 转换为整数索引并限制在图像范围内
    h, w = stack.shape[1], stack.shape[2]
    x_idxs = np.clip(x_coords.astype(int), 0, w - 1)
    y_idxs = np.clip(y_coords.astype(int), 0, h - 1)
    
    # 4. 利用 NumPy 高级索引一次性提取所有帧的数据
    # stack 形状为 (T, Y, X)，我们提取所有 T，特定的 Y 和 X
    kymo_matrix = stack[:, y_idxs, x_idxs]
    
    return kymo_matrix


