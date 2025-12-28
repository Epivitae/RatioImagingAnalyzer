# io_utils.py
import tifffile as tiff
import numpy as np

def read_and_split_dual_channel(file_path, is_interleaved):
    """
    读取单文件并根据设置拆分为双通道数据。
    返回: (d1, d2)
    """
    try:
        raw_data = tiff.imread(file_path).astype(np.float32)
    except Exception as e:
        raise ValueError(f"无法读取文件: {e}")

    d1, d2 = None, None

    # 逻辑分支 1: 交错堆栈 (Frame 0=Ch1, Frame 1=Ch2...)
    if is_interleaved:
        if raw_data.ndim != 3:
             raise ValueError(f"交错模式需要 3D 堆栈 (T, Y, X)，当前维度: {raw_data.shape}")
        
        if raw_data.shape[0] % 2 != 0:
            # 警告：奇数帧无法完美拆分，丢弃最后一帧
            # 在这里我们静默处理，或者也可以打印 log
            raw_data = raw_data[:-1]
        
        d1 = raw_data[0::2]
        d2 = raw_data[1::2]
        
    # 逻辑分支 2: Hyperstack (按维度拆分)
    else:
        if raw_data.ndim == 4:
            # 假设第二个维度是 Channel (T, C, Y, X)
            if raw_data.shape[1] == 2:
                d1 = raw_data[:, 0, :, :]
                d2 = raw_data[:, 1, :, :]
            # 假设第一个维度是 Channel (C, T, Y, X)
            elif raw_data.shape[0] == 2:
                d1 = raw_data[0, :, :, :]
                d2 = raw_data[1, :, :, :]
            else:
                raise ValueError(f"无法自动识别通道维度 (需为2)。当前形状: {raw_data.shape}")
        elif raw_data.ndim == 3:
                raise ValueError("检测到 3D 数据。如果是时间序列，请勾选 '交错堆栈' (Interleaved)。")
        else:
            raise ValueError(f"不支持的维度: {raw_data.shape}")

    return d1, d2

def read_separate_files(path1, path2):
    """读取两个独立文件"""
    d1 = tiff.imread(path1).astype(np.float32)
    d2 = tiff.imread(path2).astype(np.float32)
    
    if d1.shape != d2.shape:
        raise ValueError("通道1和通道2的图像尺寸/帧数不匹配！")
        
    return d1, d2