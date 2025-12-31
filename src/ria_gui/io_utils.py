# src/io_utils.py
import tifffile as tiff
import numpy as np
import warnings

def read_and_split_dual_channel(file_path, is_interleaved):
    """
    读取单文件并根据设置拆分为双通道数据。
    返回: (d1, d2)
    
    [优化] 移除 .astype(np.float32) 以节省 50% 内存。
    保持原始数据类型(通常是 uint16)，只在计算时自动提升精度。
    """
    try:
        # 读取原始数据，不强制转换类型
        raw_data = tiff.imread(file_path)
    except Exception as e:
        raise ValueError(f"无法读取文件: {e}")

    d1, d2 = None, None

    # 逻辑分支 1: 交错堆栈 (Frame 0=Ch1, Frame 1=Ch2...)
    if is_interleaved:
        if raw_data.ndim != 3:
             raise ValueError(f"交错模式需要 3D 堆栈 (T, Y, X)，当前维度: {raw_data.shape}")
        
        if raw_data.shape[0] % 2 != 0:
            # 警告：奇数帧无法完美拆分，丢弃最后一帧
            # 使用 view 切片，不占用额外内存
            raw_data = raw_data[:-1]
        
        # 使用切片 (Slicing) 创建视图 (View)，几乎不占额外内存
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

    # 简单检查数据一致性
    if d1.shape != d2.shape:
        # 极少情况可能发生，做个防守
        min_len = min(len(d1), len(d2))
        d1 = d1[:min_len]
        d2 = d2[:min_len]

    return d1, d2

def read_separate_files(path1, path2):
    """读取两个独立文件"""
    # [优化] 同样移除强制 float32 转换
    d1 = tiff.imread(path1)
    d2 = tiff.imread(path2)
    
    if d1.shape != d2.shape:
        # 尝试自动修复帧数不匹配（取交集）
        if d1.ndim == d2.ndim and d1.ndim == 3:
             min_frames = min(d1.shape[0], d2.shape[0])
             if min_frames > 0:
                 warnings.warn(f"帧数不匹配 ({d1.shape[0]} vs {d2.shape[0]}), 自动截断至 {min_frames} 帧。")
                 d1 = d1[:min_frames]
                 d2 = d2[:min_frames]
             else:
                 raise ValueError("通道1和通道2的帧数严重不匹配且无法自动修复！")
        else:
            raise ValueError(f"图像尺寸不匹配: {d1.shape} vs {d2.shape}")
        
    return d1, d2