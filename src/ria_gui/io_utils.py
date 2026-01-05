# src/io_utils.py
import tifffile as tiff
import numpy as np
import warnings
import os
import sys

# --- AICS 导入检查 ---
AICS_IMPORT_ERROR = None
try:
    from aicsimageio import AICSImage
except ImportError as e:
    AICSImage = None
    AICS_IMPORT_ERROR = str(e)
# ---------------------

def perform_z_projection(data, axis, method='max'):
    if method == 'max': return np.max(data, axis=axis)
    elif method == 'ave': return np.mean(data, axis=axis).astype(data.dtype)
    return data

def reorder_to_std_tczyx(data, current_axes):
    """
    [核心函数] 将任意维度的 data 按照 current_axes 的描述，
    物理搬运（Transpose/Reshape）成标准的 (T, C, Z, Y, X) 5D 格式。
    """
    current_axes = current_axes.upper()
    
    # 1. 补齐缺失的维度到 5D
    # 目标是 TCZYX，缺失的维度补为 1
    # 例如：输入 TYX (3D) -> T=dim0, Y=dim1, X=dim2
    # 我们先把它扩展成 5D，但位置要对
    
    # 建立映射: Axis Char -> Data Index
    axis_map = {char: i for i, char in enumerate(current_axes)}
    
    # 获取各维度大小
    shape = data.shape
    t = shape[axis_map['T']] if 'T' in axis_map else 1
    c = shape[axis_map['C']] if 'C' in axis_map else 1
    z = shape[axis_map['Z']] if 'Z' in axis_map else 1
    y = shape[axis_map['Y']] if 'Y' in axis_map else shape[-2]
    x = shape[axis_map['X']] if 'X' in axis_map else shape[-1]
    
    # 如果数据本身维度不对，先不管，这里只处理维度重排
    # 核心：使用 moveaxis 将 T, C, Z 移到前面
    
    # 策略：先扩展成 (..., 1, 1) 的形式，然后 transpose
    # 但 numpy 的 transpose 需要源下标。
    
    # 简单做法：利用 aicsimageio 的逻辑，手动实现
    # 1. 找到源数据中 T, C, Z, Y, X 的索引位置
    src_indices = []
    target_shape = []
    
    for char in "TCZYX":
        if char in axis_map:
            src_indices.append(axis_map[char])
            target_shape.append(shape[axis_map[char]])
        else:
            src_indices.append(-1) # 标记为缺失
            target_shape.append(1)
            
    # 2. 执行 transpose
    # 这一步比较难，因为 -1 代表需要插入新维度。
    # 更简单的方法：expand_dims 然后 moveaxis
    
    work_data = data
    current_ax_str = list(current_axes)
    
    # 缺少的维度补在最前面 (索引会变，所以要小心)
    # 不，最稳健的方法是：先 transpose 成存在的维度的标准序，再 expand_dims
    
    # 存在的维度排序
    std_order = [c for c in "TCZYX" if c in current_axes]
    # 计算 permutation
    perm = [current_axes.find(c) for c in std_order]
    
    if perm:
        work_data = np.transpose(work_data, axes=perm)
    
    # 现在 work_data 的轴序就是 std_order (例如 T,Z,Y,X)
    # 我们需要把它这就成 T,1,Z,Y,X
    
    final_shape = (t, c, z, y, x)
    # 既然我们已经知道每个维度的大小，且数据是 C-contiguous 的
    # 这里直接 reshape 可能会乱，必须保证 transpose 正确
    
    # 重写逻辑：
    # 1. 把所有维度按 TCZYX 提取出来 (利用 take 或者 moveaxis)
    # moveaxis 是最稳的
    
    temp_data = data
    curr_ax_list = list(current_axes)
    
    # 依次把 T, C, Z 移到 0, 1, 2 位置
    # 注意：每移一次，索引会变，所以要动态查找
    
    dest_idx = 0
    for char in "TCZYX":
        if char in curr_ax_list:
            src_i = curr_ax_list.index(char)
            temp_data = np.moveaxis(temp_data, src_i, dest_idx)
            # 更新 list 状态
            curr_ax_list.pop(src_i)
            curr_ax_list.insert(dest_idx, char)
            dest_idx += 1
            
    # 此时 temp_data 的前几个维度是存在的 T/C/Z，后面是 Y/X
    # 形状可能是 (T, Z, Y, X)
    # 我们需要 reshape 插入 1
    
    # 构建 reshape 参数
    reshape_param = []
    for char in "TCZYX":
        if char in current_axes:
            reshape_param.append(shape[axis_map[char]])
        else:
            reshape_param.append(1)
            
    return temp_data.reshape(tuple(reshape_param))


def read_and_split_multichannel(file_path, is_interleaved, n_channels=2, z_projection_method=None, override_axes=None, progress_callback=None, status_callback=None):
    """
    [修改版] 
    1. 增加维度重排 (Axes Reorder) 逻辑，解决 TZCYX 被读成 TCZYX 的问题。
    2. 信任 AICSImageIO 的标准化能力。
    """
    raw_data = None
    axes = ""
    
    # 1. AICS (Pro) - 它会自动处理 axes 顺序
    if AICSImage is not None:
        try:
            if status_callback: status_callback("⏳ Initializing Pro Reader...")
            img = AICSImage(file_path)
            if progress_callback: progress_callback(5, 100)
            
            # AICS 获取数据时，可以直接指定输出维度顺序！
            # 这样我们就不用自己写 reorder 了，这是最强大的功能
            if status_callback: status_callback("📥 Reading Standardized Data...")
            
            # 获取 5D 数据 (T, C, Z, Y, X)
            # AICS 会自动把文件里的维度搬运到这个位置
            raw_data = img.get_image_data("TCZYX") 
            axes = "TCZYX"
            
            if progress_callback: progress_callback(80, 100)
            
        except Exception as e:
            print(f"[IO] AICS failed: {e}")
            if "newbyteorder" in str(e): raise ValueError("NumPy version error. Downgrade NumPy.")
            raw_data = None

    # 2. TiffFile (Lite) - 需要手动重排
    if raw_data is None:
        try:
            if status_callback: status_callback("📥 Reading with TiffFile...")
            with tiff.TiffFile(file_path) as tif:
                raw_data = tif.asarray()
                
                # A. 确定 Axes
                if override_axes and override_axes != "?":
                    current_axes = override_axes.upper()
                else:
                    # 尝试从 model 层的 inspect 逻辑中获取 (这里简化处理，重新解析一下)
                    ij_meta = tif.imagej_metadata
                    shape = raw_data.shape
                    ndim = raw_data.ndim
                    
                    if ij_meta and ndim > 2:
                        # 简易推断逻辑，必须与 model.py 保持一致或更简单
                        # 如果是 ImageJ 格式，通常是 TZCYX
                        # 只要有 ImageJ 标签，且维度对的上，我们假设它是 TZCYX
                        # (这里为了保险，最好是让用户确认 axes，或者在 model.py 里传进来)
                        # 既然函数签名里有 override_axes，我们假设 GUI 已经填好了正确的
                        
                        # 如果没有 override，我们做一个大胆的假设：如果是 5D，就是 TZCYX (ImageJ 默认)
                        if ndim == 5: current_axes = "TZCYX"
                        elif ndim == 4: current_axes = "TCYX" # 默认 4D
                        elif ndim == 3: current_axes = "TYX"
                    else:
                        if ndim == 3: current_axes = "TYX"
                        elif ndim == 4: current_axes = "TCYX"
                        else: current_axes = "TCZYX" # 默认假设

                print(f"[IO] TiffFile read shape: {raw_data.shape}, interpreting as: {current_axes}")

                # B. [核心修复] 物理重排到 TCZYX
                if current_axes != "TCZYX":
                    print(f"[IO] Reordering axes {current_axes} -> TCZYX")
                    raw_data = reorder_to_std_tczyx(raw_data, current_axes)
                    axes = "TCZYX"
                else:
                    # 已经是标准格式，但需要补齐到 5D 以便统一处理
                    # 这里也可以调用 reorder，它会自动处理 expand_dims
                    raw_data = reorder_to_std_tczyx(raw_data, current_axes)
                    axes = "TCZYX"

        except Exception as e:
            raise ValueError(f"Read failed: {e}")

    # --- 至此，raw_data 必定是 (T, C, Z, Y, X) 的 5D 数组 ---
    
    # 3. Z-Projection (在 Axis=2)
    # 因为已经是标准 5D，Z 轴固定在 index 2
    if z_projection_method and raw_data.shape[2] > 1:
        if status_callback: status_callback(f"📐 Z-Projection ({z_projection_method})...")
        # 投影后 Z 变为 1
        if z_projection_method == 'max':
            raw_data = np.max(raw_data, axis=2, keepdims=True)
        else:
            raw_data = np.mean(raw_data, axis=2, keepdims=True).astype(raw_data.dtype)

    # 4. 拆分通道 (在 Axis=1)
    # 因为已经是标准 5D，C 轴固定在 index 1
    n_c = raw_data.shape[1]
    channels = []
    
    if n_c > 1:
        for i in range(n_c):
            # 提取第 i 个通道，结果为 (T, 1, Z, Y, X) -> Squeeze -> (T, Y, X)
            ch_data = raw_data[:, i, ...] # (T, Z, Y, X)
            # 再次 Squeeze Z (如果 Z=1)
            ch_data = np.squeeze(ch_data) 
            channels.append(ch_data)
    else:
        # 单通道
        channels.append(np.squeeze(raw_data))

    # 5. 最终清理
    final_channels = []
    for ch in channels:
        # 确保是 (Frames, H, W)
        if ch.ndim == 2: ch = ch[np.newaxis, ...]
        final_channels.append(ch)
        
    min_len = min(len(c) for c in final_channels)
    if progress_callback: progress_callback(100, 100)
    
    return [c[:min_len] for c in final_channels]

def read_separate_files(path1, path2):
    if not os.path.exists(path1) or not os.path.exists(path2): raise FileNotFoundError("File not found")
    d1 = tiff.imread(path1); d2 = tiff.imread(path2)
    # RGB 检查
    if d1.ndim > 2 and d1.shape[-1] in [3, 4]: d1 = np.mean(d1, axis=-1).astype(d1.dtype)
    if d2.ndim > 2 and d2.shape[-1] in [3, 4]: d2 = np.mean(d2, axis=-1).astype(d2.dtype)
    d1 = np.squeeze(d1); d2 = np.squeeze(d2)
    if d1.ndim == 2: d1 = d1[np.newaxis, ...]
    if d2.ndim == 2: d2 = d2[np.newaxis, ...]
    min_len = min(d1.shape[0], d2.shape[0])
    return d1[:min_len], d2[:min_len]