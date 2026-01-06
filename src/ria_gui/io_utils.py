# src/io_utils.py
import tifffile as tiff
import numpy as np
import warnings
import os
import sys
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# --- AICS 导入检查 ---
AICS_IMPORT_ERROR = None
try:
    from aicsimageio import AICSImage
except ImportError as e:
    AICSImage = None
    AICS_IMPORT_ERROR = str(e)
# ---------------------

@dataclass
class UnifiedData:
    """
    通用数据容器，用于在 IO 层和 Model 层之间传递标准化的 5D 数据。
    所有数据必须在内部强制转换为 (T, C, Z, Y, X) 格式。
    """
    data: np.ndarray  # Shape: (T, C, Z, Y, X)
    axes: str = "TCZYX"
    channel_names: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.data.ndim != 5:
            # 尝试做一个简单的 Wrap，防止崩溃
            self.data = _emergency_expand(self.data)
            if self.data.ndim != 5:
                raise ValueError(f"UnifiedData must be 5D, got {self.data.ndim}D.")

# =============================================================================
#  核心工具函数：维度标准化
# =============================================================================

# =============================================================================
#  核心工具函数：维度标准化
# =============================================================================

def reorder_to_std_tczyx(data: np.ndarray, current_axes: str) -> np.ndarray:
    """
    将任意维度的 data 按照 current_axes 的描述，
    物理搬运（Transpose/Reshape）成标准的 (T, C, Z, Y, X) 5D 格式。
    
    [User Request]: 
    对于 3D 数据，必须强制视为 TYX (Time Series)，
    确保它能进入 RIA 的处理流程并被可视化。
    """
    current_axes = current_axes.upper()
    shape = data.shape
    ndim = data.ndim
    
    # --- 【关键修改】强制 3D 为 TYX 策略 ---
    if ndim == 3:
        # 不管传入的 axes 是 "ZYX" 还是 "CYX"，只要是 3D，
        # 我们默认用户想看所有的切片/帧，所以强制设为 Time 轴。
        # 这样 (N, H, W) -> T=N, C=1, Z=1, Y=H, X=W
        # 结果：GUI 可以播放，Plot 可以画曲线。
        # print(f"[IO Strategy] 3D Data detected {shape}. Enforcing 'TYX' interpretation for visualization.")
        current_axes = "TYX"
    # -----------------------------------

    # 1. 基础校验与自动修正
    if len(current_axes) != ndim:
        if ndim == 2:
             current_axes = "YX"
        else:
             print(f"[IO Warning] Axes '{current_axes}' len != Data ndim {ndim}. Using fallback.")
             return _emergency_expand(data)

    # 2. 建立维度映射
    axis_map = {char: i for i, char in enumerate(current_axes)}
    
    # 3. 确定目标维度的来源索引 (T, C, Z, Y, X)
    present_dims = [c for c in "TCZYX" if c in axis_map]
    permute_order = [axis_map[c] for c in present_dims]
    
    # 执行 Transpose (将存在的维度移到前面)
    if permute_order:
        sorted_data = np.transpose(data, axes=permute_order)
    else:
        sorted_data = data
        
    # 4. 计算 Reshape 形状 (补齐 1)
    final_shape = []
    for char in "TCZYX":
        if char in axis_map:
            final_shape.append(shape[axis_map[char]])
        else:
            final_shape.append(1)
            
    # 执行 Reshape
    try:
        final_data = sorted_data.reshape(tuple(final_shape))
        return final_data
    except Exception as e:
        print(f"[IO Error] Reshape failed: {e}. Fallback to emergency expand.")
        return _emergency_expand(data)


def _emergency_expand(data):
    """当重排失败时的保底策略：假设它是最常见的格式并强行扩展"""
    if data.ndim == 5: return data
    if data.ndim == 2: return data.reshape(1, 1, 1, *data.shape) # YX -> 111YX
    if data.ndim == 3: return data.reshape(data.shape[0], 1, 1, *data.shape[1:]) # TYX -> T11YX (Assume Time)
    if data.ndim == 4: return data.reshape(data.shape[0], data.shape[1], 1, *data.shape[2:]) # TCYX -> TC1YX
    # 兜底
    new_shape = [1] * (5 - data.ndim) + list(data.shape)
    return data.reshape(tuple(new_shape))

# =============================================================================
#  保存逻辑：带 RIA 标签的智能保存 (Fix: TZCYX Order)
# =============================================================================

def save_ria_tiff(filepath, data_5d, channel_names=None, params=None, extra_meta=None):
    """
    保存数据为 RIA 兼容格式。
    关键修复: 将内存中的 TCZYX 转换为 ImageJ 兼容的 TZCYX 顺序再保存。
    """
    # 1. 确保输入是 5D (T, C, Z, Y, X)
    if data_5d.ndim != 5:
        print(f"[Saver Fix] Input not 5D ({data_5d.shape}), expanding...")
        data_5d = _emergency_expand(data_5d)

    T, C, Z, Y, X = data_5d.shape

    # 2. [核心修复] 重排为 TZCYX (ImageJ Hyperstack Standard)
    # 内存: 0:T, 1:C, 2:Z, 3:Y, 4:X
    # 目标: 0:T, 1:Z, 2:C, 3:Y, 4:X (即交换 C 和 Z)
    print(f"[Saver] Transposing TCZYX {data_5d.shape} -> TZCYX for ImageJ compatibility...")
    data_to_save = np.transpose(data_5d, (0, 2, 1, 3, 4)) # Swap C(1) and Z(2)

    # 3. 准备 Metadata
    ij_metadata = {
        'axes': 'TZCYX',  # 明确告诉 ImageJ 这是 TZCYX
        'images': T * Z * C,
        'channels': C,
        'slices': Z,
        'frames': T,
        'hyperstack': True,
        'mode': 'composite',
        'unit': 'um',
    }

    # RIA 专属 Meta (记录这一事实，以便回读时转回来)
    ria_info = {
        "is_ria_processed": True,
        "format_version": "1.1",
        "original_shape": list(data_5d.shape), # 记录原始 TCZYX 形状
        "axes_order": "TZCYX",                 # 记录文件物理存储顺序
        "channel_names": channel_names if channel_names else [f"Ch{i+1}" for i in range(C)],
        "processing_params": params if params else {},
        "extra": extra_meta if extra_meta else {}
    }
    
    try:
        json_str = json.dumps(ria_info, ensure_ascii=False)
    except:
        json_str = '{"is_ria_processed": true, "error": "json_failed"}'

    # 4. 写入
    tiff.imwrite(
        filepath,
        data_to_save, # 使用重排后的数据
        imagej=True,
        metadata=ij_metadata,
        description=json_str,
        compression='zlib'
    )
    print(f"[IO] Saved successfully to {filepath}")



def read_ria_tiff_smart(filepath, user_axes=None): # <--- 新增参数
    """
    智能读取函数。
    1. 优先检查 RIA JSON 标签。
    2. 如果发现是 TZCYX 顺序（RIA Saver 保存的），自动转回 TCZYX。
    3. 如果有 user_axes，强制使用。
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    print(f"[IO] Smart reading: {os.path.basename(filepath)}")
    
    ria_meta = None
    raw_data = None
    
    # --- 阶段 1: 尝试读取 RIA 标签 ---
    # (原有代码保持不变 ...)
    try:
        with tiff.TiffFile(filepath) as tif:
            desc = tif.pages[0].description
            if desc and "is_ria_processed" in desc:
                start = desc.find('{')
                end = desc.rfind('}')
                if start != -1 and end != -1:
                    try: ria_meta = json.loads(desc[start : end+1])
                    except: pass
            raw_data = tif.asarray()
    except Exception as e:
        print(f"[IO] Read error: {e}")
        return None

    # --- 阶段 2: 根据 RIA 标签还原 ---
    # (原有代码保持不变 ...)
    if ria_meta and ria_meta.get("is_ria_processed"):
        # ... (原有代码 ...)
        if raw_data.ndim != 5:
             raw_data = _emergency_expand(raw_data)
        return UnifiedData(
            data=raw_data, 
            axes="TCZYX", 
            channel_names=ria_meta.get("channel_names", []),
            metadata=ria_meta
        )

    # --- 阶段 3: 通用/旧版逻辑 (回退) ---
    print("[IO] Standard Tiff detected. Using heuristics.")
    
    ndim = raw_data.ndim
    current_axes = "?"
    
    # [关键修改]：优先使用传入的 user_axes
    if user_axes and len(user_axes) == ndim:
        print(f"[IO] Applying override axes: {user_axes}")
        current_axes = user_axes
    else:
        # 原有的猜测逻辑
        if ndim == 3: 
            current_axes = "TYX" # 默认 3D 为 Time
        elif ndim == 4: 
            current_axes = "TCYX"
        elif ndim == 5: 
            current_axes = "TCZYX"
    
    data_5d = reorder_to_std_tczyx(raw_data, current_axes)
    return UnifiedData(data=data_5d, axes="TCZYX")

# =============================================================================
#  旧接口兼容层
# =============================================================================

def perform_z_projection(data, axis, method='max'):
    if method == 'max': return np.max(data, axis=axis)
    elif method == 'ave': return np.mean(data, axis=axis).astype(data.dtype)
    return data

# 在 src/io_utils.py 中找到 read_and_split_multichannel 函数

def read_and_split_multichannel(file_path, is_interleaved, n_channels=2, z_projection_method=None, override_axes=None, progress_callback=None, status_callback=None):
    """
    兼容 GUI 的旧接口，内部调用 UnifiedData 逻辑。
    """
    unified_obj = None
    
    # [关键修改]：如果存在 override_axes，跳过 AICSImage，直接使用 smart read
    # 因为 AICSImage 很难强制指定轴序，而 read_ria_tiff_smart 现在支持强制指定
    use_aics = (AICSImage is not None) and (override_axes is None)

    # 1. AICS (Pro)
    if use_aics:
        try:
            if status_callback: status_callback("⏳ Initializing Pro Reader...")
            img = AICSImage(file_path)
            if progress_callback: progress_callback(10, 100)
            raw_data = img.get_image_data("TCZYX")
            unified_obj = UnifiedData(data=raw_data, axes="TCZYX")
        except Exception as e:
            print(f"[IO] AICS failed, fallback: {e}")
            if "newbyteorder" in str(e): raise ValueError("NumPy version error.")

    # 2. Smart Read
    if unified_obj is None:
        if status_callback: status_callback("📥 Reading with TiffFile...")
        try:
            # [关键修改]：将 override_axes 传递给 read_ria_tiff_smart
            unified_obj = read_ria_tiff_smart(file_path, user_axes=override_axes)
        except Exception as e:
             raise ValueError(f"Read failed: {e}")

    if unified_obj is None: raise ValueError("Failed to load data.")

    # ... (后续代码保持不变) ...
    data_5d = unified_obj.data 
    
    # ...
    
    # 3. Z-Projection (Axis=2)
    if z_projection_method and data_5d.shape[2] > 1:
        if status_callback: status_callback(f"📐 Z-Projection ({z_projection_method})...")
        if z_projection_method == 'max':
            data_5d = np.max(data_5d, axis=2, keepdims=True)
        else:
            data_5d = np.mean(data_5d, axis=2, keepdims=True).astype(data_5d.dtype)

    # 4. Split Channels (Axis=1)
    # 返回列表，每个元素 shape 为 (T, Y, X) 或 (T, Z, Y, X)
    final_channels = []
    n_c = data_5d.shape[1]
    
    for i in range(n_c):
        ch = data_5d[:, i, ...] # (T, Z, Y, X)
        # 如果 Z=1，压缩它以适配旧 GUI 逻辑 (T, Y, X)
        if ch.shape[1] == 1:
            ch = np.squeeze(ch, axis=1) 
        final_channels.append(ch)

    if progress_callback: progress_callback(100, 100)
    return final_channels




def read_separate_files(path1, path2):
    if not os.path.exists(path1) or not os.path.exists(path2): 
        raise FileNotFoundError("File not found")
    
    def _read_one(p):
        d = tiff.imread(p)
        # 简单规范化：如果是 2D，扩展为 (1, Y, X) 模拟 Time
        if d.ndim == 2: d = d[np.newaxis, ...] 
        return d
        
    d1 = _read_one(path1)
    d2 = _read_one(path2)
    min_len = min(d1.shape[0], d2.shape[0])
    return d1[:min_len], d2[:min_len]