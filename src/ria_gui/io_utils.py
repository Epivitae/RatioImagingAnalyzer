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
    data: np.ndarray 
    axes: str = "TCZYX"
    channel_names: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.data.ndim != 5:
            self.data = _emergency_expand(self.data)
            if self.data.ndim != 5:
                raise ValueError(f"UnifiedData must be 5D, got {self.data.ndim}D.")

# =============================================================================
#  核心工具函数
# =============================================================================

def reorder_to_std_tczyx(data: np.ndarray, current_axes: str) -> np.ndarray:
    current_axes = current_axes.upper()
    shape = data.shape
    ndim = data.ndim
    
    if ndim == 3: current_axes = "TYX"

    if len(current_axes) != ndim:
        if ndim == 2: current_axes = "YX"
        else: return _emergency_expand(data)

    axis_map = {char: i for i, char in enumerate(current_axes)}
    present_dims = [c for c in "TCZYX" if c in axis_map]
    permute_order = [axis_map[c] for c in present_dims]
    
    if permute_order: sorted_data = np.transpose(data, axes=permute_order)
    else: sorted_data = data
        
    final_shape = []
    for char in "TCZYX":
        if char in axis_map: final_shape.append(shape[axis_map[char]])
        else: final_shape.append(1)
            
    try: return sorted_data.reshape(tuple(final_shape))
    except: return _emergency_expand(data)

def _emergency_expand(data):
    if data.ndim == 5: return data
    if data.ndim == 2: return data.reshape(1, 1, 1, *data.shape)
    if data.ndim == 3: return data.reshape(data.shape[0], 1, 1, *data.shape[1:])
    if data.ndim == 4: return data.reshape(data.shape[0], data.shape[1], 1, *data.shape[2:])
    new_shape = [1] * (5 - data.ndim) + list(data.shape)
    return data.reshape(tuple(new_shape))

# =============================================================================
#  ImageJ LUT 生成器
# =============================================================================

def _create_ij_luts(n_channels):
    """
    生成 ImageJ 兼容的 LUTs (颜色表)。
    """
    # Green, Magenta, Cyan, Yellow, Red, Blue, Gray
    colors = [
        (0, 1, 0), (1, 0, 1), (0, 1, 1), (1, 1, 0), (1, 0, 0), (0, 0, 1), (1, 1, 1)
    ]
    
    luts = []
    for i in range(n_channels):
        c_idx = i % len(colors)
        r_w, g_w, b_w = colors[c_idx]
        
        ramp = np.arange(256, dtype=np.uint8)
        lut = np.zeros((3, 256), dtype=np.uint8)
        if r_w: lut[0] = ramp
        if g_w: lut[1] = ramp
        if b_w: lut[2] = ramp
        
        luts.append(lut)
        
    return luts

# =============================================================================
#  保存逻辑 (移除 Range 后的版本)
# =============================================================================

def save_ria_tiff(filepath, data_5d, channel_names=None, params=None, extra_meta=None):
    """
    保存数据为 RIA 兼容格式，支持 ImageJ Hyperstack 颜色显示。
    [修改] 移除了 display_ranges 参数，防止类型错误。
    """
    if data_5d.ndim != 5: data_5d = _emergency_expand(data_5d)

    T, C, Z, Y, X = data_5d.shape

    # 1. 重排为 TZCYX
    data_to_save = np.transpose(data_5d, (0, 2, 1, 3, 4)) 

    # 2. 生成 LUTs
    ij_luts = _create_ij_luts(C)

    # 3. 准备 Metadata
    ij_metadata = {
        'axes': 'TZCYX',
        'images': T * Z * C,
        'channels': C,
        'slices': Z,
        'frames': T,
        'hyperstack': True,
        'mode': 'composite', 
        'unit': 'um',
        'loop': False,
        'LUTs': ij_luts, 
    }
    
    # [已移除] Ranges 写入逻辑
    # [已移除] Labels 写入逻辑 (因为现在只有一个通道，Ratio，写不写都行，为了稳健先移除)
    if channel_names and len(channel_names) == C:
        ij_metadata['Labels'] = channel_names

    # 4. RIA 专属 Meta
    ria_info = {
        "is_ria_processed": True,
        "format_version": "1.4",
        "original_shape": list(data_5d.shape), 
        "axes_order": "TZCYX",                 
        "channel_names": channel_names if channel_names else [f"Ch{i+1}" for i in range(C)],
        "processing_params": params if params else {},
        "extra": extra_meta if extra_meta else {}
    }
    
    try: json_str = json.dumps(ria_info, ensure_ascii=False)
    except: json_str = '{"is_ria_processed": true, "error": "json_failed"}'

    # 5. 写入
    tiff.imwrite(
        filepath,
        data_to_save,
        imagej=True,
        metadata=ij_metadata,
        software=json_str,
        compression='zlib'
    )
    print(f"[IO] Saved to {filepath} (ImageJ Compatible + LUTs)")

# =============================================================================
#  读取逻辑 (保持不变)
# =============================================================================

def read_raw_bioformats(filepath):
    if AICS_IMPORT_ERROR: raise ImportError(f"AICSImageIO error: {AICS_IMPORT_ERROR}")
    print(f"[IO-Raw] AICS: {filepath}")
    img = AICSImage(filepath)
    return UnifiedData(data=img.get_image_data("TCZYX"), axes="TCZYX")

def read_standard_tiff(filepath, user_axes=None):
    if not os.path.exists(filepath): raise FileNotFoundError(f"Not found: {filepath}")
    print(f"[IO-Tiff] TiffFile: {filepath}")

    ria_meta = None
    ij_meta = None
    raw_data = None
    
    try:
        with tiff.TiffFile(filepath) as tif:
            page0 = tif.pages[0]
            desc = page0.description
            target_json = desc if (desc and "is_ria_processed" in desc) else getattr(page0, 'software', "")
            
            if target_json and "is_ria_processed" in target_json:
                s = target_json.find('{'); e = target_json.rfind('}')
                if s!=-1 and e!=-1: 
                    try: ria_meta = json.loads(target_json[s:e+1])
                    except: pass

            ij_meta = tif.imagej_metadata
            raw_data = tif.asarray()
    except Exception as e: raise ValueError(f"Read error: {e}")

    if ria_meta and ria_meta.get("is_ria_processed"):
        print("[IO-Tiff] RIA tag found.")
        if raw_data.ndim != 5: raw_data = _emergency_expand(raw_data)
        return UnifiedData(raw_data, "TCZYX", ria_meta.get("channel_names", []), ria_meta)

    detected_axes = "?"
    ndim = raw_data.ndim

    if user_axes and len(user_axes) == ndim:
        detected_axes = user_axes
    elif ij_meta:
        n_c = ij_meta.get('channels', 1); n_z = ij_meta.get('slices', 1); n_t = ij_meta.get('frames', 1)
        if ndim == 3:
            detected_axes = "TYX" if (n_t > 1 and n_z == 1) else ("ZYX" if n_z > 1 else "TYX")

    if detected_axes == "?":
        detected_axes = {3:"TYX", 4:"TCYX", 5:"TCZYX"}.get(ndim, "TCZYX")

    return UnifiedData(reorder_to_std_tczyx(raw_data, detected_axes), "TCZYX")

def read_separate_files_list(file_paths: List[str]):
    if not file_paths: raise ValueError("No files.")
    print(f"[IO-Sep] Loading {len(file_paths)} files...")
    loaded_arrays = []
    base_shape = None 
    for i, p in enumerate(file_paths):
        if not os.path.exists(p): raise FileNotFoundError(p)
        d = tiff.imread(p)
        if d.ndim == 2: d = d[np.newaxis, np.newaxis, :, :]
        elif d.ndim == 3: d = d[:, np.newaxis, :, :]
        elif d.ndim > 4: 
            nt = np.prod(d.shape[:-2])
            d = d.reshape(nt, 1, d.shape[-2], d.shape[-1])
        
        if base_shape is None: base_shape = d.shape[-2:]
        else: 
            if d.shape[-2:] != base_shape: raise ValueError(f"Size mismatch: {os.path.basename(p)}")
        loaded_arrays.append(d)

    try: stack = np.stack(loaded_arrays, axis=0)
    except: raise ValueError("Stacking failed.")
    return UnifiedData(np.transpose(stack, (1, 0, 2, 3, 4)), "TCZYX")