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
        [修改版 V2] 修复 C/Z 颠倒问题。
        优先级调整：
        1. ImageJ Metadata (最准，ImageJ 写的 Tiff 必须优先信这个)
        2. AICSImage (对非 ImageJ 格式通用性好，但容易猜错 Tiff 的 C/Z)
        3. 纯形状推断 (兜底)
        """
        detected_channels = 1
        detected_z = 1
        detected_axes = "?"
        is_explicit_multichannel = False
        
        # --- 0. 预检查：TiffFile ImageJ Metadata (优先级最高) ---
        # 专门解决：ImageJ 保存的 Hyperstack (T, Z, C) 被 AICS 误读为 (T, C, Z) 的问题
        try:
            with tiff.TiffFile(filepath) as tif:
                # 检查是否为 ImageJ 格式
                ij_meta = tif.imagej_metadata
                
                # 如果有 ImageJ 标签，绝对信任它
                if ij_meta:
                    # 获取真实计数
                    n_c = ij_meta.get('channels', 1)
                    n_z = ij_meta.get('slices', 1)
                    n_t = ij_meta.get('frames', 1)
                    
                    detected_channels = n_c
                    detected_z = n_z
                    
                    if n_c > 1: is_explicit_multichannel = True
                    
                    # [推断 Axes]
                    if len(tif.series) > 0:
                        shape = tif.series[0].shape
                        ndim = len(shape)
                        
                        # 移除 XY
                        dims_to_map = list(shape[:-2]) 
                        mapped_axes = ""
                        pool = {'T': n_t, 'Z': n_z, 'C': n_c}
                        
                        # 贪婪匹配：根据维度大小去对应 T/Z/C
                        for d_len in dims_to_map:
                            found = False
                            # 优先匹配大数 (防止 1 和 1 混淆，但 T=81, Z=41, C=2 通常都不一样)
                            # 这里做一个简单策略：先匹配 T，再 Z，再 C
                            for key in ['T', 'Z', 'C']:
                                val = pool[key]
                                if val == d_len: # 这是一个强匹配
                                    mapped_axes += key
                                    pool[key] = -1 # 标记已用
                                    found = True
                                    break
                            if not found:
                                # 尝试模糊匹配 (比如维度是1的情况)
                                mapped_axes += "?"
                        
                        mapped_axes += "YX"
                        
                        # 修正缺失维度
                        final_axes = ""
                        for char in mapped_axes:
                            if char != '?': final_axes += char
                            
                        # 如果拼出来的轴数不对，或者包含问号，回退到标准推测
                        if len(final_axes) != ndim:
                            if ndim == 5: detected_axes = "TZCYX" # ImageJ 默认通常是 TZCYX
                            else: detected_axes = mapped_axes.replace("?", "")
                        else:
                            detected_axes = final_axes
                            
                        print(f"[Metadata] ImageJ Priority: C={n_c}, Z={n_z}, T={n_t} -> Axes: {detected_axes}")
                        return is_explicit_multichannel, detected_channels, detected_z, detected_axes

        except Exception as e:
            print(f"[Metadata] ImageJ check skipped: {e}")


        # --- 1. 原有的 3D 强制检查 ---
        try:
            with tiff.TiffFile(filepath) as tif:
                if len(tif.series) > 0:
                    ndim = tif.series[0].ndim
                    if ndim == 3:
                        print(f"[Metadata] Raw 3D detected (ndim=3). Enforcing TYX (Time Series).")
                        return False, 1, 1, "TYX"
        except Exception:
            pass

        # --- 2. AICSImage (优先级降低) ---
        if AICSImage is not None:
            try:
                img = AICSImage(filepath)
                # 只有当上面 ImageJ 解析失败时，才走这里
                detected_channels = img.dims.C
                detected_z = img.dims.Z
                detected_axes = img.dims.order
                if detected_channels > 1:
                    is_explicit_multichannel = True
                print(f"[Metadata] AICS Fallback: {detected_axes} (C:{detected_channels}, Z:{detected_z})")
                return is_explicit_multichannel, detected_channels, detected_z, detected_axes
            except Exception:
                pass

        # --- 3. 最后的兜底 (纯猜) ---
        # 如果到了这里，说明既不是 ImageJ Tiff，AICS 也读不了
        if detected_axes == "?" or detected_axes == "TCZYX":
             # ... (保留你原有的兜底代码，如果有的话) ...
             pass

        # 最终清洗
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

    # src/model.py -> AnalysisSession 类中

    # src/model.py -> AnalysisSession 类中

    def export_processed_stack(self, filepath, params, progress_callback=None):
        """
        [修复版] 保存处理后的伪彩视频。
        """
        if self.data1 is None: raise ValueError("No data")
        
        n_frames = self.data1.shape[0]
        processed_frames = []
        
        for i in range(n_frames):
            # 获取帧数据 (Y, X)
            fr = self.get_processed_frame(
                i, 
                params.get("int_thresh", 0), 
                params.get("ratio_thresh", 0), 
                params.get("smooth", 0), 
                params.get("log_scale", False), 
                params.get("use_custom_bg", False),
                swap_channels=(self.view_mode == "c2_c1" or self.current_roles.get("num") == 1)
            )
            if fr is None:
                h, w = self.data1.shape[-2], self.data1.shape[-1]
                fr = np.zeros((h, w), dtype=np.float32)
            processed_frames.append(fr)
            
            if progress_callback and i % 5 == 0: progress_callback(i, n_frames)

        # 堆叠为 (T, Y, X)
        stack_3d = np.array(processed_frames, dtype=np.float32)
        
        # [关键步骤] 升维到 5D -> (T, 1, 1, Y, X)
        # 这确保了它被识别为 Time Series，而不是 Z-Stack
        stack_5d = stack_3d[:, np.newaxis, np.newaxis, :, :]
        
        meta_params = params.copy()
        meta_params["content_type"] = "Processed_Video"

        # 调用 io_utils 的智能保存 (它内部会自动处理 TZCYX 顺序问题)
        from io_utils import save_ria_tiff
        save_ria_tiff(filepath, stack_5d, channel_names=["RatioVideo"], params=meta_params)

        if progress_callback: progress_callback(n_frames, n_frames)


    def export_raw_ratio_stack(self, filepath, int_thresh, ratio_thresh, progress_callback=None):
        """
        [修复版] 保存原始比率数据。
        """
        if self.data1 is None: raise ValueError("No data")
        
        n_frames = self.data1.shape[0]
        frames_list = []
        
        for i in range(n_frames):
            # 强制提取原始比率
            fr = self.get_processed_frame(
                i, int_thresh, ratio_thresh, smooth_size=0, log_scale=False, use_custom_bg=False,
                swap_channels=(self.current_roles.get("num") == 1)
            )
            if fr is None:
                h, w = self.data1.shape[-2], self.data1.shape[-1]
                fr = np.zeros((h, w), dtype=np.float32)
            frames_list.append(fr)
            
            if progress_callback and i % 5 == 0: progress_callback(i, n_frames)

        stack_3d = np.array(frames_list, dtype=np.float32)
        
        # [关键步骤] 升维到 (T, 1, 1, Y, X)
        stack_5d = stack_3d[:, np.newaxis, np.newaxis, :, :]
        
        meta_params = {"int_thresh": int_thresh, "ratio_thresh": ratio_thresh, "content_type": "Raw_Ratio"}
        
        from io_utils import save_ria_tiff
        save_ria_tiff(filepath, stack_5d, channel_names=["RawRatio"], params=meta_params)

        if progress_callback: progress_callback(n_frames, n_frames)


    def export_current_frame(self, filepath, frame_idx, params):
        img = self.get_processed_frame(frame_idx, params.get("int_thresh",0), params.get("ratio_thresh",0), params.get("smooth",0), params.get("log_scale",False), params.get("use_custom_bg",False))
        if img is not None: tiff.imwrite(filepath, img)

    def export_input_data(self, filepath):
        if self.data1 is None: raise ValueError("No data")
        
        # 1. 组装回 5D 格式 (T, C, Z, Y, X)
        # 假设当前内存里的 data1 已经是 (T, Y, X) 或者 (T, Z, Y, X)
        
        channels = [self.data1]
        if self.data2 is not None: channels.append(self.data2)
        channels.extend(self.data_aux)
        
        # Stack 到 C 维度 (axis=0 for now) -> (C, T, [Z], Y, X)
        stack = np.stack(channels, axis=0)
        
        # 检查是否缺少 Z 维
        if stack.ndim == 4: # (C, T, Y, X)
            stack = stack[:, :, np.newaxis, :, :] # -> (C, T, 1, Y, X)
        
        # Transpose 到 (T, C, Z, Y, X)
        # 目前 stack 是 (C, T, Z, Y, X) -> permute (1, 0, 2, 3, 4)
        data_5d = np.transpose(stack, (1, 0, 2, 3, 4))
        
        # 2. 准备元数据
        chn_names = ["Ch1", "Ch2"] if self.data2 is not None else ["Ch1"]
        chn_names.extend([f"Aux{i+1}" for i in range(len(self.data_aux))])
        
        params = {
            "processed_by": "RIA_Export_Input",
            "alignment_done": len(self.alignment_matrices) > 0
        }
        
        # 3. 调用新 IO
        from io_utils import save_ria_tiff
        save_ria_tiff(filepath, data_5d, channel_names=chn_names, params=params)