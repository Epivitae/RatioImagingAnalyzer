# src/model.py
import numpy as np
import tifffile as tiff
import os
from typing import List, Optional, Tuple

# 尝试导入依赖
try:
    from .io_utils import read_and_split_multichannel, read_separate_files
    from .processing import calculate_background, process_frame_ratio
except ImportError:
    from io_utils import read_and_split_multichannel, read_separate_files
    from processing import calculate_background, process_frame_ratio

try:
    from aicsimageio import AICSImage
except ImportError:
    AICSImage = None

class AnalysisSession:
    def __init__(self):
        self.data1 = None
        self.data2 = None
        self.data_aux = []
        self.data1_raw = None
        self.data2_raw = None 
        self.cached_bg1 = 0.0
        self.cached_bg2 = 0.0
        self.cached_bg_aux = [] 
        self.c1_path = None
        self.c2_path = None
        self.dual_path = None
        self.bg_percent = 5.0
        self.custom_bg1 = 0.0
        self.custom_bg2 = 0.0
        self.fps = 10 
        self.is_playing = False
        self.view_mode = "ratio" 
        self.alignment_matrices = [] 
        self.current_roles = None
        self.cached_z_count = 1 # 新增：缓存Z层数

    def inspect_file_metadata(self, filepath: str) -> Tuple[bool, int, int, str]:
        """
        [修改版] 智能元数据检测。
        能够识别 ImageJ 的 TZCYX 等复杂顺序，并返回正确的 Axes 字符串。
        """
        detected_channels = 1
        detected_z = 1
        detected_axes = "?"
        is_explicit_multichannel = False

        # 1. 优先尝试 AICS (Pro 格式 OIR/ND2)
        if AICSImage is not None:
            try:
                img = AICSImage(filepath)
                # AICS 会自动标准化为 TCZYX，所以我们相信它
                detected_channels = img.dims.C
                detected_z = img.dims.Z
                detected_axes = img.dims.order
                if detected_channels > 1:
                    is_explicit_multichannel = True
                print(f"[Metadata] AICS: {detected_axes} (C:{detected_channels}, Z:{detected_z})")
                return is_explicit_multichannel, detected_channels, detected_z, detected_axes
            except Exception:
                pass

        # 2. TiffFile 深度解析 (Lite 格式)
        if detected_axes == "?" or detected_axes == "TCZYX":
            try:
                with tiff.TiffFile(filepath) as tif:
                    if len(tif.series) > 0:
                        series = tif.series[0]
                        shape = series.shape
                        ndim = len(shape)
                        
                        # --- ImageJ Metadata 解析 (最关键的一步) ---
                        ij_meta = tif.imagej_metadata
                        if ij_meta:
                            # 获取真实计数
                            n_c = ij_meta.get('channels', 1)
                            n_z = ij_meta.get('slices', 1)
                            n_t = ij_meta.get('frames', 1)
                            
                            detected_channels = n_c
                            detected_z = n_z
                            if n_c > 1: is_explicit_multichannel = True

                            # [核心算法] 推断物理 Axes 顺序
                            # ImageJ 默认存储顺序通常是: Time -> Z -> Channel (TZCYX)
                            # 或者是: Time -> Channel -> Z (TCZYX)
                            # 我们根据 shape 来匹配
                            
                            # 移除 XY (最后两维)
                            dims_to_map = list(shape[:-2]) 
                            mapped_axes = ""
                            
                            # 简单的匹配逻辑：根据维度大小去猜
                            # 注意：如果 T=81, Z=41, C=2，而 shape=(81, 41, 2) -> 就能完美匹配
                            # 如果 shape=(81, 2, 41) -> 也能匹配
                            
                            # 这里我们构建一个简单的映射池
                            pool = {'T': n_t, 'Z': n_z, 'C': n_c}
                            
                            # 从 shape 前面开始匹配
                            for d_len in dims_to_map:
                                found = False
                                for key, val in pool.items():
                                    if val == d_len and val > 1:
                                        mapped_axes += key
                                        pool[key] = -1 # 标记已用
                                        found = True
                                        break
                                if not found:
                                    # 如果有维度为1或者没匹配上，通常TiffFile会省略，或者它是冗余维
                                    # 此时我们暂时标记为 '?'，后面处理
                                    mapped_axes += "?"
                            
                            mapped_axes += "YX"
                            
                            # 修正：如果推断出的轴包含 ?，或者顺序不对，给一个默认值
                            if '?' in mapped_axes or len(mapped_axes) != ndim:
                                # 默认 ImageJ 顺序
                                if ndim == 5: detected_axes = "TZCYX"
                                elif ndim == 4: 
                                    if n_t > 1 and n_z > 1: detected_axes = "TZYX"
                                    elif n_t > 1 and n_c > 1: detected_axes = "TCYX"
                                    elif n_z > 1 and n_c > 1: detected_axes = "ZCYX"
                                else: detected_axes = "TYX"
                            else:
                                detected_axes = mapped_axes
                                
                            print(f"[Metadata] ImageJ Meta: T={n_t}, Z={n_z}, C={n_c} -> Inferred Axes: {detected_axes}")

                        else:
                            # 无 Metadata，尝试纯猜
                            if ndim == 3: detected_axes = "TYX" # 3D 默认为 Time
                            elif ndim == 4: detected_axes = "TCYX"
                            elif ndim == 5: detected_axes = "TCZYX"

            except Exception as e:
                print(f"[Metadata] Inspection failed: {e}")

        # 3. 最终清洗
        if detected_channels == 1:
            detected_axes = detected_axes.replace("C", "")
            is_explicit_multichannel = False

        return is_explicit_multichannel, detected_channels, detected_z, detected_axes

    def load_channels_from_file(self, filepath, is_interleaved, n_channels, z_proj_method=None, user_axes=None, progress_callback=None, status_callback=None):
        return read_and_split_multichannel(
            filepath, is_interleaved, n_channels, z_proj_method, user_axes, progress_callback, status_callback
        )

    def load_separate_channels(self, path1, path2):
        d1, d2 = read_separate_files(path1, path2)
        return [d1, d2]

    def set_data(self, data_list, roles=None):
        count = len(data_list)
        if roles:
            self.current_roles = roles
        else:
            self.current_roles = {"num": 0, "den": 1} if count >= 2 else {"num": 0, "den": None}
        
        self.data1 = None
        self.data2 = None
        self.data_aux = []
        self.alignment_matrices = []
        
        if count == 1:
            self.data1 = data_list[0]
            self.data2 = None
        elif count == 2:
            if roles:
                idx_num = roles.get("num", 0)
                idx_den = roles.get("den", 1)
                self.data1 = data_list[idx_num]
                self.data2 = data_list[idx_den]
            else:
                self.data1 = data_list[0]
                self.data2 = data_list[1]
        else:
            if roles is None:
                self.data1 = data_list[0]
                self.data2 = data_list[1]
                self.data_aux = data_list[2:]
            else:
                idx_num = roles["num"]
                idx_den = roles["den"]
                self.data1 = data_list[idx_num]
                self.data2 = data_list[idx_den]
                for i, d in enumerate(data_list):
                    if i != idx_num and i != idx_den:
                        self.data_aux.append(d)

        self.data1_raw = None
        self.data2_raw = None
        self.recalc_background()

    def align_data(self, progress_callback=None):
        try: from processing import align_stack_ecc
        except ImportError: raise ImportError("OpenCV required")
        if self.data1 is None: return
        if self.data1_raw is None:
            self.data1_raw = self.data1.copy()
            if self.data2 is not None: self.data2_raw = self.data2.copy()
        target = self.data2 if self.data2 is not None else self.data1
        d1_a, d2_a, mats = align_stack_ecc(self.data1, target, progress_callback)
        self.data1 = d1_a
        if self.data2 is not None: self.data2 = d2_a
        self.alignment_matrices = mats
        self.recalc_background()

    def undo_alignment(self):
        if self.data1_raw is not None:
            self.data1 = self.data1_raw.copy()
            if self.data2_raw is not None: self.data2 = self.data2_raw.copy()
            self.data1_raw = None
            self.data2_raw = None
            self.alignment_matrices = []
            self.recalc_background()
            return True
        return False

    def apply_existing_alignment(self, matrices_data):
        try: from processing import apply_alignment_matrices
        except: return
        if self.data1 is None: return
        mats = [np.array(m, dtype=np.float32) for m in matrices_data]
        if self.data1_raw is None:
            self.data1_raw = self.data1.copy()
            if self.data2 is not None: self.data2_raw = self.data2.copy()
        self.data1 = apply_alignment_matrices(self.data1, mats)
        if self.data2 is not None: self.data2 = apply_alignment_matrices(self.data2, mats)
        self.alignment_matrices = mats
        self.recalc_background()

    def recalc_background(self):
        if self.data1 is None: return
        p = self.bg_percent
        self.cached_bg1 = calculate_background(self.data1, p)
        if self.data2 is not None: self.cached_bg2 = calculate_background(self.data2, p)
        else: self.cached_bg2 = 0.0
        self.cached_bg_aux = []
        for aux in self.data_aux:
            self.cached_bg_aux.append(calculate_background(aux, p))

    def get_processed_frame(self, frame_idx, int_thresh=0, ratio_thresh=0, smooth_size=0, log_scale=False, use_custom_bg=False, swap_channels=False):
        if self.data1 is None: return None
        if use_custom_bg:
            bg1, bg2 = self.custom_bg1, self.custom_bg2
            bg_aux = self.cached_bg_aux
        else:
            bg1, bg2 = self.cached_bg1, self.cached_bg2
            bg_aux = self.cached_bg_aux
            
        d_num, d_den = self.data1, self.data2
        b_num, b_den = bg1, bg2
        if swap_channels and self.data2 is not None:
            d_num, d_den = d_den, d_num
            b_num, b_den = b_den, b_num
            
        if self.view_mode == "ch1":
            return np.clip(self.data1[frame_idx].astype(np.float32)-bg1, 0, None)
        elif self.view_mode == "ch2":
            if self.data2 is None: return None
            return np.clip(self.data2[frame_idx].astype(np.float32)-bg2, 0, None)
        elif self.view_mode.startswith("aux_"):
            try:
                idx = int(self.view_mode.split("_")[1])
                val = bg_aux[idx] if idx < len(bg_aux) else 0
                return np.clip(self.data_aux[idx][frame_idx].astype(np.float32)-val, 0, None)
            except: return None
            
        return process_frame_ratio(d_num[frame_idx], d_den[frame_idx] if d_den is not None else None, b_num, b_den, int_thresh, ratio_thresh, smooth_size, log_scale)

    def export_processed_stack(self, filepath, params, progress_callback=None):
        if self.data1 is None: raise ValueError("No data")
        n = self.data1.shape[0]
        with tiff.TiffWriter(filepath, bigtiff=True) as tw:
            for i in range(n):
                fr = self.get_processed_frame(i, params.get("int_thresh",0), params.get("ratio_thresh",0), params.get("smooth",0), params.get("log_scale",False), params.get("use_custom_bg",False))
                if fr is not None: tw.write(fr.astype(np.float32), contiguous=True)
                if progress_callback and i%5==0: progress_callback(i, n)
        if progress_callback: progress_callback(n, n)

    def export_raw_ratio_stack(self, filepath, int_thresh, ratio_thresh, progress_callback=None):
        if self.data1 is None: raise ValueError("No data")
        n = self.data1.shape[0]
        with tiff.TiffWriter(filepath, bigtiff=True) as tw:
            for i in range(n):
                fr = self.get_processed_frame(i, int_thresh, ratio_thresh, 0, False, False)
                if fr is not None: tw.write(fr.astype(np.float32), contiguous=True)
                if progress_callback and i%5==0: progress_callback(i, n)
        if progress_callback: progress_callback(n, n)

    def export_current_frame(self, filepath, frame_idx, params):
        img = self.get_processed_frame(frame_idx, params.get("int_thresh",0), params.get("ratio_thresh",0), params.get("smooth",0), params.get("log_scale",False), params.get("use_custom_bg",False))
        if img is not None: tiff.imwrite(filepath, img)

    def export_input_data(self, filepath):
        if self.data1 is None: raise ValueError("No data")
        channels = [self.data1]
        if self.data2 is not None: channels.append(self.data2)
        channels.extend(self.data_aux)
        stack = np.stack(channels, axis=0)
        stack = np.transpose(stack, (1, 0, 2, 3))
        tiff.imwrite(filepath, stack, imagej=True, metadata={'axes': 'TCYX'})