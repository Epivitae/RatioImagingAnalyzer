# src/io_utils.py
import tifffile as tiff
import numpy as np
import warnings
import os

def perform_z_projection(data, axis, method='max'):
    """
    对指定轴执行投影。
    method: 'max' (最大密度投影 MIP) 或 'ave' (平均密度投影 AIP)
    """
    print(f"Applying Z-Projection ({method}) on axis {axis}, original shape: {data.shape}")
    if method == 'max':
        return np.max(data, axis=axis)
    elif method == 'ave':
        # 保持原有数据类型 (如 uint16)
        return np.mean(data, axis=axis).astype(data.dtype)
    return data

def read_and_split_multichannel(file_path, is_interleaved, n_channels=2, z_projection_method=None, override_axes=None):
    """
    Universal reading function.
    override_axes: 如果用户手动指定了 Axes (如 'TYX')，则忽略文件自带的元数据。
    """
    try:
        with tiff.TiffFile(file_path) as tif:
            raw_data = tif.asarray()
            
            # [核心逻辑] 优先级：用户输入 > 文件自带 > 空字符串
            if override_axes:
                print(f"[IO] Using user override axes: {override_axes}")
                axes = override_axes
            else:
                axes = tif.series[0].axes if hasattr(tif.series[0], 'axes') else ""
                
    except Exception as e:
        raise ValueError(f"Could not read file: {e}")

    # =================================================================
    # Z-Stack 处理逻辑
    # =================================================================
    # 这里的逻辑非常巧妙：
    # 如果系统识别是 ZYX，用户手动改成了 TYX。
    # 此时 axes 变量变成了 "TYX"。
    # 下面的 'Z' in axes 判断就会失败。
    # 于是直接跳过投影，数据保留原样进入后续流程，完美解决问题！
    if z_projection_method and 'Z' in axes:
        z_index = axes.find('Z')
        if z_index < raw_data.ndim and raw_data.shape[z_index] > 1:
            raw_data = perform_z_projection(raw_data, axis=z_index, method=z_projection_method)

    channels = []


    # Logic 1: Interleaved Stack
    if is_interleaved:
        if raw_data.ndim != 3:
             # 如果选了 None (Treat as T)，原本 (Z,Y,X) 的 3D 数据会被保留
             # 这里 (Z,Y,X) 从 numpy 角度看就是 (Time, Y, X)，完全符合 3D Stack 要求
             # 所以这里的检查通过
             raise ValueError(f"Interleaved mode requires 3D stack (T, Y, X). Current shape: {raw_data.shape}")
        
        n_frames = raw_data.shape[0]
        if n_channels == 1:
            channels.append(raw_data)
        else:
            remainder = n_frames % n_channels
            if remainder != 0:
                raw_data = raw_data[:-remainder]
            for c in range(n_channels):
                channels.append(raw_data[c::n_channels])

    # Logic 2: Hyperstack (4D/3D)
    else:
        if raw_data.ndim == 4:
            # (T, C, Y, X)
            if raw_data.shape[1] >= 1 and raw_data.shape[1] <= 10: 
                for c in range(raw_data.shape[1]):
                    channels.append(raw_data[:, c, :, :])
            # (C, T, Y, X)
            elif raw_data.shape[0] >= 1 and raw_data.shape[0] <= 10 and raw_data.shape[1] > 10: 
                 for c in range(raw_data.shape[0]):
                     channels.append(raw_data[c, :, :, :])
            else:
                raise ValueError(f"Cannot identify channel dimension. Shape: {raw_data.shape}.")
                    
        elif raw_data.ndim == 3:
             # (T, Y, X)
             # [关键] 当选择了 None 投影，(90, 512, 512) 的数据会走到这里
             # 这时候它就被当作 90 帧的时间序列处理了。
             channels.append(raw_data)
        else:
            raise ValueError(f"Unsupported dimensions: {raw_data.shape}.")

    if not channels:
        raise ValueError("No channel data extracted.")
        
    min_len = min(len(c) for c in channels)
    channels = [c[:min_len] for c in channels]

    return channels




def read_separate_files(path1, path2):
    """
    读取两个独立的文件作为 Ch1 和 Ch2。
    """
    if not os.path.exists(path1) or not os.path.exists(path2):
        raise FileNotFoundError("One or both files not found.")

    with tiff.TiffFile(path1) as tif:
        d1 = tif.asarray()
    
    with tiff.TiffFile(path2) as tif:
        d2 = tif.asarray()

    # 简单的维度检查
    if d1.ndim == 2: d1 = d1[np.newaxis, ...] # 补齐 T 轴
    if d2.ndim == 2: d2 = d2[np.newaxis, ...]

    # 确保长度一致
    min_len = min(d1.shape[0], d2.shape[0])
    return d1[:min_len], d2[:min_len]