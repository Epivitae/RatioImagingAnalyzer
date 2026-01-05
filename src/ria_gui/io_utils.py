# src/io_utils.py
import tifffile as tiff
import numpy as np
import warnings
import os
import sys

AICS_IMPORT_ERROR = None

# 打印调试信息，确保环境正确
print(f"--- DEBUG INFO ---")
print(f"Python: {sys.executable}")
print(f"Tifffile: {tiff.__version__}")
try:
    import imagecodecs
    print(f"Imagecodecs: Installed ({imagecodecs.__version__})")
except ImportError:
    print(f"Imagecodecs: NOT INSTALLED (Critical for OIR)")
print(f"------------------")

try:
    from aicsimageio import AICSImage
except ImportError as e:
    AICSImage = None
    # [关键] 把具体的错误（比如 "No module named fsspec"）存下来
    AICS_IMPORT_ERROR = str(e)
    print(f"DEBUG: AICSImageIO import failed: {e}")


def perform_z_projection(data, axis, method='max'):
    print(f"Applying Z-Projection ({method}) on axis {axis}, original shape: {data.shape}")
    if method == 'max':
        return np.max(data, axis=axis)
    elif method == 'ave':
        return np.mean(data, axis=axis).astype(data.dtype)
    return data



def read_and_split_multichannel(file_path, is_interleaved, n_channels=2, z_projection_method=None, override_axes=None, progress_callback=None, status_callback=None):
    """
    [Lite 兼容版] 核心读取函数。
    支持在没有 aicsimageio 环境下运行，并能正确处理 Lite 版的逻辑分流。
    """
    raw_data = None
    axes = ""
    
    # 1. 预检查：如果是特殊格式且没有 AICSImage 库，直接拦截并报错
    # 这样可以防止程序进入复杂的 AICS 逻辑导致的潜在崩溃
    is_special_format = file_path.lower().endswith(('.oir', '.nd2', '.czi', '.lif'))
    if is_special_format and AICSImage is None:
        raise ValueError("Lite 版仅支持标准 TIFF。如需直接读取 OIR/ND2 等格式，请使用 Pro 版。")

    # --- 2. 尝试使用 TiffFile 读取 (Lite 版的核心) ---
    try:
        if status_callback: status_callback("📥 Reading with TiffFile...")
        with tiff.TiffFile(file_path) as tif:
            raw_data = tif.asarray()
            if len(tif.series) > 0 and hasattr(tif.series[0], 'axes'):
                axes = tif.series[0].axes
    except Exception as e:
        print(f"[IO] TiffFile failed or skipped: {e}")

    # --- 3. 只有在 Pro 环境下且 TiffFile 失败时，才进入 AICS 逻辑 ---
    if raw_data is None and AICSImage is not None:
        try:
            if status_callback: status_callback("⏳ Initializing Pro Reader (AICS)...")
            
            # 初始化 Reader
            img = AICSImage(file_path)
            
            if progress_callback: progress_callback(5, 100)
            if status_callback: status_callback("📄 Parsing Pro Metadata...")

            t_size, c_size, z_size = img.dims.T, img.dims.C, img.dims.Z
            y_size, x_size = img.dims.Y, img.dims.X
            
            # 预分配内存
            raw_data = np.empty((t_size, c_size, z_size, y_size, x_size), dtype=img.dtype)
            axes = "TCZYX"
            
            if status_callback: status_callback("📥 Extracting Image Chunks...")
            for t in range(t_size):
                chunk = img.get_image_data("TCZYX", T=t)
                raw_data[t] = chunk[0]
                if progress_callback:
                    percent = 5 + int((t + 1) / t_size * 90)
                    progress_callback(percent, 100)
                    
        except Exception as e_aics:
            print(f"[IO] AICS Pro Reader failed: {e_aics}")

    # --- 4. 安全检查：如果最终未获得数据 ---
    if raw_data is None:
        # 根据当前环境给出准确的报错提示
        if AICSImage is None:
            raise ValueError("无法读取文件。轻量版仅支持标准 TIFF 格式。")
        else:
            raise ValueError("所有读取引擎均失败。文件可能损坏或格式不受支持。")

    # --- 5. 通用处理 (Z-Proj & 通道分离) ---
    # 这部分逻辑仅依赖 numpy，在 Lite/Pro 下均可正常运行
    
    if override_axes and override_axes != "?":
        axes = override_axes
    elif not axes:
        ndim = raw_data.ndim
        if ndim == 5: axes = "TCZYX"
        elif ndim == 4: axes = "TCYX"
        elif ndim == 3: axes = "TYX"

    # Z-Projection
    if z_projection_method and 'Z' in axes:
        z_idx = axes.find('Z')
        if z_idx < raw_data.ndim and raw_data.shape[z_idx] > 1:
            if status_callback: status_callback(f"📐 Applying {z_projection_method} Projection...")
            raw_data = np.max(raw_data, axis=z_idx) if z_projection_method == 'max' else np.mean(raw_data, axis=z_idx).astype(raw_data.dtype)
            axes = axes.replace('Z', '')

    # 通道分离
    if status_callback: status_callback("✂️ Finalizing Channels...")
    channels = []
    if 'C' in axes:
        c_idx = axes.find('C')
        data_c_first = np.moveaxis(raw_data, c_idx, 0)
        for i in range(raw_data.shape[c_idx]):
            channels.append(np.squeeze(data_c_first[i]))
    else:
        channels.append(np.squeeze(raw_data))

    final_channels = []
    for ch in channels:
        if ch.ndim == 2: ch = ch[np.newaxis, ...]
        final_channels.append(ch)
        
    min_len = min(len(c) for c in final_channels)
    if progress_callback: progress_callback(100, 100)
    if status_callback: status_callback("")
    
    return [c[:min_len] for c in final_channels]

def read_separate_files(path1, path2):
    if not os.path.exists(path1) or not os.path.exists(path2):
        raise FileNotFoundError("One or both files not found.")
    
    # 这里的读取也应该具备同样的强壮性，简单起见我们直接复用上面的逻辑或 imread
    # 为了一致性，这里简单用 imread，如果需要也可改为二进制读取
    d1 = tiff.imread(path1)
    d2 = tiff.imread(path2)

    if d1.ndim == 2: d1 = d1[np.newaxis, ...]
    if d2.ndim == 2: d2 = d2[np.newaxis, ...]
    min_len = min(d1.shape[0], d2.shape[0])
    return d1[:min_len], d2[:min_len]