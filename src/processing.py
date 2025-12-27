import numpy as np

def calculate_background(stack_data, percentile):
    """
    计算图像堆栈的背景值。
    使用百分位数法（如 5% 或 10%）来估算图像中最暗区域的背景水平。
    """
    if stack_data is None:
        return 0
    # np.nanpercentile 会忽略数据中的 NaN 值计算百分位
    return np.nanpercentile(stack_data, percentile)

def smooth_nan_safe(arr, size):
    """
    使用纯 NumPy 实现的 NaN-safe 平滑算法 (Normalized Convolution)。
    该算法模仿了 SciPy 的 uniform_filter，但解决了两个核心问题：
    1. 避免 NaN 扩散：传统平滑如果周围有一个像素是 NaN，结果就会变 NaN。
    2. 边缘权重补偿：确保边缘像素的平均值计算是准确的。
    """
    if size <= 1:
        return arr
    
    # 1. 创建掩膜：记录哪些位置是有效数字
    mask = ~np.isnan(arr)
    # 2. 将原数组中的 NaN 替换为 0，以便进行加法卷积
    arr_filled = np.nan_to_num(arr, nan=0.0)
    
    # 定义滑动窗口求和函数 (等效于非归一化的 uniform_filter)
    def fast_sum_convolve(a, s):
        res = np.zeros_like(a)
        offset = s // 2
        # 在二维空间内进行滚动累加
        # 注意：此方法在图像边缘会产生环绕效应 (Wrap-around effect)
        for i in range(s):
            for j in range(s):
                res += np.roll(np.roll(a, i - offset, axis=0), j - offset, axis=1)
        return res

    # 分别计算有效像素的和，以及有效像素的数量
    sum_data = fast_sum_convolve(arr_filled, size)
    sum_mask = fast_sum_convolve(mask.astype(float), size)
    
    # 执行归一化：平均值 = 总和 / 有效像素个数
    with np.errstate(divide='ignore', invalid='ignore'):
        result = sum_data / sum_mask
        
    # 如果某个区域全是 NaN (sum_mask 为 0)，则结果仍为 NaN
    result[sum_mask < 1e-6] = np.nan
    return result

def process_frame_ratio(d1_frame, d2_frame, bg1, bg2, int_thresh, ratio_thresh, smooth_size, log_scale=False):
    """
    处理单帧图像的核心逻辑：
    扣背景 -> 强度过滤 -> 比率计算 -> 阈值过滤 -> (对数变换) -> 平滑。
    """
    # 1. 扣除背景并剪裁负值（防止负数比率）
    img1 = np.clip(d1_frame - bg1, 0, None)
    img2 = np.clip(d2_frame - bg2, 0, None)

    # 2. 强度阈值过滤：如果任一通道强度低于阈值，则视为背景
    mask_int = (img1 < int_thresh) | (img2 < int_thresh)

    # 3. 计算比值 (Ratio = Ch1 / Ch2)
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = np.divide(img1, img2)
        # 特殊情况处理：分母为0设为NaN，分子为0设为0
        ratio[img2 == 0] = np.nan 
        ratio[img1 == 0] = 0
    
    # 应用强度掩膜
    ratio[mask_int] = np.nan

    # 4. 比值阈值过滤：剔除不符合生理或物理常识的极低比值
    if ratio_thresh > 0:
        ratio[ratio < ratio_thresh] = np.nan
        
    # 5. 对数变换 (可选)
    if log_scale:
        ratio = np.log1p(ratio)
    
    # 6. 平滑处理：在比率计算完成后进行，以减少噪声干扰
    if smooth_size > 1:
        ratio = smooth_nan_safe(ratio, int(smooth_size))
        
    return ratio