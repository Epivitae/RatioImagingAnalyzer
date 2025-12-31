# src/io_utils.py
import tifffile as tiff
import numpy as np
import warnings

def read_and_split_multichannel(file_path, is_interleaved, n_channels=2):
    """
    通用读取函数，支持任意通道数。
    返回: List [ch0, ch1, ch2, ...]
    """
    try:
        # 读取原始数据，不强制转换类型以节省内存
        raw_data = tiff.imread(file_path)
    except Exception as e:
        raise ValueError(f"无法读取文件: {e}")

    channels = []

    # 逻辑 1: 交错堆栈 (Interleaved) - 如: Ch1, Ch2, Ch3, Ch1...
    if is_interleaved:
        if raw_data.ndim != 3:
             raise ValueError(f"交错模式需要 3D 堆栈 (T, Y, X)，当前维度: {raw_data.shape}")
        
        n_frames = raw_data.shape[0]
        # 截断无法整除的多余帧
        remainder = n_frames % n_channels
        if remainder != 0:
            raw_data = raw_data[:-remainder]
            
        # 使用切片分离通道，不产生额外内存拷贝
        for c in range(n_channels):
            # start=c, step=n_channels
            channels.append(raw_data[c::n_channels])

    # 逻辑 2: Hyperstack (4D) - 如: (T, C, Y, X)
    else:
        if raw_data.ndim == 4:
            # 情况 A: 标准顺序 (T, C, Y, X) -> shape[1] 是通道
            if raw_data.shape[1] >= 2 and raw_data.shape[1] <= 10: 
                for c in range(raw_data.shape[1]):
                    channels.append(raw_data[:, c, :, :])
            
            # 情况 B: ImageJ 某些格式 (C, T, Y, X) -> shape[0] 是通道
            # 这里的判断逻辑是：通常通道数比较少 (<10)，而时间帧数比较多
            elif raw_data.shape[0] >= 2 and raw_data.shape[0] <= 10 and raw_data.shape[1] > 10:
                 for c in range(raw_data.shape[0]):
                     channels.append(raw_data[c, :, :, :])
            else:
                raise ValueError(f"无法自动识别通道维度 (T,C,Y,X or C,T,Y,X)。当前形状: {raw_data.shape}")
                    
        elif raw_data.ndim == 3:
             raise ValueError("检测到 3D 数据。如果是多通道交错时间序列，请勾选 'Mixed Stacks' 并设置正确的通道数。")
        else:
            raise ValueError(f"不支持的维度: {raw_data.shape}")

    # 简单检查长度一致性 (通常切片后是一致的)
    if not channels:
        raise ValueError("未能提取到任何通道数据。")
        
    min_len = min(len(c) for c in channels)
    channels = [c[:min_len] for c in channels]

    return channels

def read_and_split_dual_channel(file_path, is_interleaved):
    """兼容旧接口的 Wrapper，默认只读2通道"""
    res = read_and_split_multichannel(file_path, is_interleaved, n_channels=2)
    if len(res) < 2:
        raise ValueError("文件通道数少于 2 个。")
    return res[0], res[1]

def read_separate_files(path1, path2):
    """读取两个独立文件"""
    d1 = tiff.imread(path1)
    d2 = tiff.imread(path2)
    
    if d1.shape != d2.shape:
        # 尝试自动修复帧数不匹配
        if d1.ndim == d2.ndim and d1.ndim == 3:
             min_frames = min(d1.shape[0], d2.shape[0])
             if min_frames > 0:
                 warnings.warn(f"帧数不匹配 ({d1.shape[0]} vs {d2.shape[0]}), 自动截断至 {min_frames} 帧。")
                 d1 = d1[:min_frames]
                 d2 = d2[:min_frames]
             else:
                 raise ValueError("通道1和通道2的帧数严重不匹配！")
        else:
            raise ValueError(f"图像尺寸不匹配: {d1.shape} vs {d2.shape}")
        
    return d1, d2