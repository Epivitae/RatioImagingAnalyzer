# src/model.py
import numpy as np
import tifffile as tiff
import os
from typing import List, Optional, Tuple

# [清理后] 只保留 processing 的导入，IO 操作我们在函数内部按需导入
try:
    from .processing import calculate_background, process_frame_ratio
except ImportError:
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


    #def load_channels_from_file(self, filepath, is_interleaved, n_channels, z_proj_method=None, user_axes=None, progress_callback=None, status_callback=None):
    #    return read_and_split_multichannel(
    #        filepath, is_interleaved, n_channels, z_proj_method, user_axes, progress_callback, status_callback
    #    )

    #def load_separate_channels(self, path1, path2):
    #    d1, d2 = read_separate_files(path1, path2)
    #    return [d1, d2]

    # src/model.py

# ... (Imports, AnalysisSession __init__ 等保持不变) ...

    # [删除] load_channels_from_file (旧接口)
    

    def load_raw_data(self, filepath, z_method=None):
        from io_utils import read_raw_bioformats
        unified = read_raw_bioformats(filepath)
        return self._split_5d_to_channels(unified.data, z_method)

    # [修改] 增加 user_axes 和 z_method 参数
    def load_tiff_data(self, filepath, user_axes=None, z_method=None):
        from io_utils import read_standard_tiff
        # 将 user_axes 传给 IO 层
        unified = read_standard_tiff(filepath, user_axes=user_axes) 
        return self._split_5d_to_channels(unified.data, z_method)

    # [修改] 增加 z_method 参数
    def load_separate_files_list(self, file_paths, z_method=None):
        from io_utils import read_separate_files_list
        unified = read_separate_files_list(file_paths)
        return self._split_5d_to_channels(unified.data, z_method)

    # [修改] 核心拆分逻辑：响应 Z-Proj 选择
    def _split_5d_to_channels(self, data_5d, z_method=None):
        channels = []
        n_c = data_5d.shape[1]
        n_z = data_5d.shape[2]
        
        # --- 核心修复：Z轴处理逻辑 ---
        if n_z > 1:
            # 情况 A: 用户明确选了 Max
            if z_method == 'max':
                print(f"[Model] Z-Projection: MAX (MIP)")
                data_5d = np.max(data_5d, axis=2, keepdims=True)
                
            # 情况 B: 用户明确选了 Ave
            elif z_method == 'ave':
                print(f"[Model] Z-Projection: AVE (AIP)")
                data_5d = np.mean(data_5d, axis=2, keepdims=True)
                
            # 情况 C: 用户没选 (None)，或者选了 None
            # 【关键修改】为了防止 GUI 崩溃，如果没有专门的 3D 查看器，默认强制做 Max 投影
            else:
                print(f"[Model] Z-Stack detected ({n_z} slices) but no projection method selected.")
                print(f"[Model] Auto-applying MAX projection to ensure visualization.")
                data_5d = np.max(data_5d, axis=2, keepdims=True)

        # ---------------------------

        for i in range(n_c):
            ch = data_5d[:, i, ...] # (T, Z, Y, X)
            
            # 此时 Z 应该已经是 1 了 (除非未来支持 3D 播放)
            if ch.shape[1] == 1:
                ch = np.squeeze(ch, axis=1) # -> (T, Y, X)
                
            channels.append(ch)
            
        return channels



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


    def export_results_data(self, filepath, params, progress_callback=None):
        """
        [精简版] 仅保存 Ratio 结果堆栈。
        结构: (Time, 1, 1, Y, X)
        Channels: [Ratio]
        数据类型: float32
        """
        if self.data1 is None: raise ValueError("No data")
        
        n_frames = self.data1.shape[0]
        h, w = self.data1.shape[-2], self.data1.shape[-1]
        
        # 1. 准备容器 (只存 1 个通道)
        ratio_stack = np.zeros((n_frames, 1, h, w), dtype=np.float32)
        channel_names = ["Ratio"]

        # 提取参数
        int_th = params.get("int_thresh", 0)
        ratio_th = params.get("ratio_thresh", 0)
        sm = params.get("smooth", 0)
        log_sc = params.get("log_scale", False)
        use_bg = params.get("use_custom_bg", False)
        
        swap = (self.view_mode == "c2_c1" or self.current_roles.get("num") == 1)

        # 2. 逐帧计算 Ratio
        for i in range(n_frames):
            fr = self.get_processed_frame(
                i, int_th, ratio_th, sm, log_sc, use_bg, swap
            )
            if fr is None: 
                fr = np.zeros((h, w), dtype=np.float32)
            
            ratio_stack[i, 0] = fr
            
            if progress_callback and i % 5 == 0: progress_callback(i, n_frames)

        # [已移除] 自动计算 Display Range 的逻辑
        
        # 3. 升维并保存
        # (T, 1, Y, X) -> (T, 1, 1, Y, X)
        final_5d = ratio_stack[:, :, np.newaxis, :, :] 
        
        meta_params = params.copy()
        meta_params["content_type"] = "Ratio_Stack_Only"
        meta_params["description"] = "Generated by RIA (Ratio Channel)"
        
        from io_utils import save_ria_tiff
        save_ria_tiff(
            filepath, 
            final_5d, 
            channel_names=channel_names, 
            params=meta_params
            # [已移除] display_ranges 参数
        )
        
        if progress_callback: progress_callback(n_frames, n_frames)

    def export_current_frame(self, filepath, frame_idx, params):
        img = self.get_processed_frame(
            frame_idx, 
            params.get("int_thresh",0), 
            params.get("ratio_thresh",0), 
            params.get("smooth",0), 
            params.get("log_scale",False), 
            params.get("use_custom_bg",False),
            swap_channels=(self.view_mode == "c2_c1")
        )
        if img is not None: 
            # 保存单帧时，我们尽量保存为 ImageJ 兼容格式
            # 虽然只是单帧，但 tifffile.imwrite 直接存 numpy array 效果最好
            tiff.imwrite(filepath, img)

    def export_input_data(self, filepath):
        """保存预处理后的原始数据 (Aligned Raw)"""
        if self.data1 is None: raise ValueError("No data")
        
        channels = [self.data1]
        if self.data2 is not None: channels.append(self.data2)
        channels.extend(self.data_aux)
        
        stack = np.stack(channels, axis=0)
        if stack.ndim == 4: stack = stack[:, :, np.newaxis, :, :]
        
        # (C, T, Z, Y, X) -> (T, C, Z, Y, X)
        data_5d = np.transpose(stack, (1, 0, 2, 3, 4))
        
        chn_names = ["Ch1", "Ch2"] if self.data2 is not None else ["Ch1"]
        chn_names.extend([f"Aux{i+1}" for i in range(len(self.data_aux))])
        
        params = {
            "processed_by": "RIA_Export_Input",
            "alignment_done": len(self.alignment_matrices) > 0
        }
        
        from io_utils import save_ria_tiff
        save_ria_tiff(filepath, data_5d, channel_names=chn_names, params=params)