# src/model.py
import numpy as np
import tifffile as tiff
import os
import warnings
from typing import List, Optional, Tuple, Any, Union

# 尝试相对导入 (作为包运行)，失败则尝试绝对导入 (直接运行脚本)
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
    """
    Model 层：管理 RIA 应用程序的核心数据状态和业务逻辑。
    """

    def __init__(self):
        # --- 核心图像数据 ---
        self.data1: Optional[np.ndarray] = None      # 分子 (Ch1 / Numerator)
        self.data2: Optional[np.ndarray] = None      # 分母 (Ch2 / Denominator)
        self.data_aux: List[np.ndarray] = []         # 辅助通道列表 (Ch3, Ch4...)
        
        # --- 原始数据备份 (用于撤销配准) ---
        self.data1_raw: Optional[np.ndarray] = None
        self.data2_raw: Optional[np.ndarray] = None 

        # --- 背景值缓存 ---
        self.cached_bg1: float = 0.0
        self.cached_bg2: float = 0.0
        self.cached_bg_aux: List[float] = [] 

        # --- 文件路径信息 ---
        self.c1_path: Optional[str] = None
        self.c2_path: Optional[str] = None
        self.dual_path: Optional[str] = None
        
        # --- 计算参数 ---
        self.bg_percent: float = 5.0  # 默认背景扣除百分比
        
        # --- 自定义背景 ROI 状态 ---
        self.custom_bg1: float = 0.0
        self.custom_bg2: float = 0.0
        
        self.fps: int = 10 
        self.is_playing: bool = False
        self.view_mode: str = "ratio" 
        self.alignment_matrices = [] 
        self.current_roles = None


    def inspect_file_metadata(self, filepath: str) -> Tuple[bool, int, int, str]:
        """
        [Lite 兼容版] 检查文件元数据，识别通道数、Z层数和轴序。
        支持在无 aicsimageio 的环境下运行。
        """
        detected_channels = 1
        detected_z = 1
        detected_axes = "?"
        is_explicit_multichannel = False

        # 1. 预检查：特殊格式拦截
        is_special = filepath.lower().endswith(('.oir', '.nd2', '.czi', '.lif'))
        if is_special and AICSImage is None:
            # 如果是轻量版打开 OIR，直接返回基础信息，交由后续 io_utils 报错或在此处直接提示
            print("[Metadata] Lite version detected special format. AICSImageIO is missing.")
            return False, 1, 1, "?"

        # 2. 尝试使用 AICSImageIO (Pro 版逻辑)
        if AICSImage is not None:
            try:
                img = AICSImage(filepath)
                detected_channels = img.dims.C
                detected_z = img.dims.Z
                detected_axes = img.dims.order  # 例如 "TCZYX"
                
                # 如果 C > 1，标记为明确的多通道文件
                if detected_channels > 1:
                    is_explicit_multichannel = True
                
                print(f"[Metadata] AICS detected: {detected_axes} (C:{detected_channels}, Z:{detected_z})")
                return is_explicit_multichannel, detected_channels, detected_z, detected_axes
            except Exception as e:
                print(f"[Metadata] AICS inspection failed: {e}")

        # 3. 回退到标准 TiffFile (Lite 版核心逻辑)
        try:
            with tiff.TiffFile(filepath) as tif:
                series = tif.series[0]
                shape = series.shape
                detected_axes = series.axes.upper()
                
                # 从 Tiff 轴序中提取 C 和 Z
                if 'C' in detected_axes:
                    detected_channels = shape[detected_axes.find('C')]
                if 'Z' in detected_axes:
                    detected_z = shape[detected_axes.find('Z')]
                
                if detected_channels > 1:
                    is_explicit_multichannel = True
                    
                print(f"[Metadata] TiffFile detected: {detected_axes} (C:{detected_channels}, Z:{detected_z})")
        except Exception as e:
            print(f"[Metadata] Standard inspection failed: {e}")

        return is_explicit_multichannel, detected_channels, detected_z, detected_axes

    def load_channels_from_file(self, 
                                filepath: str, 
                                is_interleaved: bool, 
                                n_channels: int, 
                                z_proj_method: Optional[str] = None,
                                user_axes: Optional[str] = None,
                                progress_callback=None,
                                status_callback=None): # [新增参数]
        """
        Model 层的单一文件读取入口。
        """
        raw_channels = read_and_split_multichannel(
            file_path=filepath,
            is_interleaved=is_interleaved,
            n_channels=n_channels,
            z_projection_method=z_proj_method,
            override_axes=user_axes,
            progress_callback=progress_callback,
            status_callback=status_callback # [透传]
        )
        return raw_channels

    def load_separate_channels(self, path1: str, path2: str) -> List[np.ndarray]:
        if not path1 or not path2:
            raise ValueError("Both file paths must be provided.")
        d1, d2 = read_separate_files(path1, path2)
        return [d1, d2]

    def set_data(self, data_list: List[np.ndarray], roles: Optional[dict] = None) -> None:
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
        self.alignment_matrices = []


    def align_data(self, progress_callback=None) -> None:
        try:
            from processing import align_stack_ecc
        except ImportError:
            try:
                from .processing import align_stack_ecc
            except ImportError:
                raise ImportError("OpenCV (cv2) is required for alignment.")

        if self.data1 is None: raise ValueError("No data to align.")

        if self.data1_raw is None:
            self.data1_raw = self.data1.copy()
            if self.data2 is not None:
                self.data2_raw = self.data2.copy()

        target_data2 = self.data2 if self.data2 is not None else self.data1
        d1_aligned, d2_aligned, matrices = align_stack_ecc(self.data1, target_data2, progress_callback=progress_callback)

        self.data1 = d1_aligned
        if self.data2 is not None: self.data2 = d2_aligned
        self.alignment_matrices = matrices
        self.recalc_background()


    def undo_alignment(self) -> bool:
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
        try:
            from processing import apply_alignment_matrices
        except: return
        if self.data1 is None: return
        matrices = [np.array(m, dtype=np.float32) for m in matrices_data]
        if self.data1_raw is None:
            self.data1_raw = self.data1.copy()
            if self.data2 is not None: self.data2_raw = self.data2.copy()
        self.data1 = apply_alignment_matrices(self.data1, matrices)
        if self.data2 is not None: self.data2 = apply_alignment_matrices(self.data2, matrices)
        self.alignment_matrices = matrices
        self.recalc_background()

    def recalc_background(self) -> None:
        if self.data1 is None: return
        p = self.bg_percent
        self.cached_bg1 = calculate_background(self.data1, p)
        if self.data2 is not None: self.cached_bg2 = calculate_background(self.data2, p)
        else: self.cached_bg2 = 0.0
        self.cached_bg_aux = []
        for aux in self.data_aux:
            self.cached_bg_aux.append(calculate_background(aux, p))

    def get_processed_frame(self, frame_idx, int_thresh=0, ratio_thresh=0, smooth_size=0, log_scale=False, use_custom_bg=False, swap_channels=False) -> Optional[np.ndarray]:
        if self.data1 is None: return None
        
        if use_custom_bg:
            bg1 = self.custom_bg1
            bg2 = self.custom_bg2
            bg_aux_list = self.cached_bg_aux 
        else:
            bg1 = self.cached_bg1
            bg2 = self.cached_bg2
            bg_aux_list = self.cached_bg_aux

        d_num = self.data1
        d_den = self.data2
        bg_num = bg1
        bg_den = bg2

        if swap_channels and self.data2 is not None:
            d_num = self.data2
            d_den = self.data1
            bg_num = bg2
            bg_den = bg1

        if self.view_mode == "ch1":
            try:
                raw = self.data1[frame_idx].astype(np.float32) - bg1
                return np.clip(raw, 0, None)
            except IndexError: return None
            
        elif self.view_mode == "ch2":
            if self.data2 is None: return None
            try:
                raw = self.data2[frame_idx].astype(np.float32) - bg2
                return np.clip(raw, 0, None)
            except IndexError: return None
            
        elif self.view_mode.startswith("aux_"):
            try:
                idx = int(self.view_mode.split("_")[1])
                if idx < len(self.data_aux):
                    bg_val = bg_aux_list[idx] if idx < len(bg_aux_list) else 0
                    raw = self.data_aux[idx][frame_idx].astype(np.float32) - bg_val
                    return np.clip(raw, 0, None)
            except: return None
            return None

        return process_frame_ratio(
            d_num[frame_idx], 
            d_den[frame_idx] if d_den is not None else None,
            bg_num, bg_den,
            int_thresh, ratio_thresh, smooth_size, log_scale
        )
    
    def export_processed_stack(self, filepath, params, progress_callback=None) -> None:
        if self.data1 is None: raise ValueError("No data to save.")
        n_frames = self.data1.shape[0]
        with tiff.TiffWriter(filepath, bigtiff=True) as tif:
            for i in range(n_frames):
                frame_data = self.get_processed_frame(
                    frame_idx=i,
                    int_thresh=params.get("int_thresh", 0),
                    ratio_thresh=params.get("ratio_thresh", 0),
                    smooth_size=params.get("smooth", 0),
                    log_scale=params.get("log_scale", False),
                    use_custom_bg=params.get("use_custom_bg", False)
                )
                if frame_data is not None: tif.write(frame_data.astype(np.float32), contiguous=True)
                if progress_callback and i % 5 == 0: progress_callback(i, n_frames)
        if progress_callback: progress_callback(n_frames, n_frames)

    def export_raw_ratio_stack(self, filepath, int_thresh, ratio_thresh, progress_callback=None) -> None:
        if self.data1 is None: raise ValueError("No data to save.")
        n_frames = self.data1.shape[0]
        with tiff.TiffWriter(filepath, bigtiff=True) as tif:
            for i in range(n_frames):
                frame_data = self.get_processed_frame(
                    frame_idx=i, int_thresh=int_thresh, ratio_thresh=ratio_thresh,
                    smooth_size=0, log_scale=False, use_custom_bg=False
                )
                if frame_data is not None: tif.write(frame_data.astype(np.float32), contiguous=True)
                if progress_callback and i % 5 == 0: progress_callback(i, n_frames)
        if progress_callback: progress_callback(n_frames, n_frames)

    def export_current_frame(self, filepath, frame_idx, params) -> None:
        img = self.get_processed_frame(
            frame_idx=frame_idx,
            int_thresh=params.get("int_thresh", 0),
            ratio_thresh=params.get("ratio_thresh", 0),
            smooth_size=params.get("smooth", 0),
            log_scale=params.get("log_scale", False),
            use_custom_bg=params.get("use_custom_bg", False)
        )
        if img is not None: tiff.imwrite(filepath, img)


    # src/model.py

    def export_input_data(self, filepath: str) -> None:
        """
        [新增] 将当前内存中的原始数据 (Ch1, Ch2, Aux) 打包保存为多通道 TIFF。
        这保存的是经过了 Z-Proj 和 Alignment 之后的数据。
        """
        if self.data1 is None:
            raise ValueError("No data to save.")

        # 1. 收集所有通道数据
        channels_to_save = [self.data1]
        
        if self.data2 is not None:
            channels_to_save.append(self.data2)
            
        if self.data_aux:
            channels_to_save.extend(self.data_aux)
            
        # 2. 堆叠为一个大数组
        # 假设每个通道都是 (T, Y, X)
        # 堆叠后变成 (C, T, Y, X)
        try:
            stack = np.stack(channels_to_save, axis=0)
        except ValueError:
            # 如果通道间尺寸不一致（极少见），可能需要处理
            raise ValueError("Channels have different dimensions, cannot save as single file.")

        # 3. 调整维度顺序以符合 ImageJ 习惯 (T, Z, C, Y, X) 
        # 我们这里通常是 2D time-lapse，所以是 (T, C, Y, X)
        # stack 目前是 (C, T, Y, X) -> 转置为 (T, C, Y, X)
        # transpose(1, 0, 2, 3) 
        stack_tcyx = np.transpose(stack, (1, 0, 2, 3))
        
        # 4. 写入文件
        # imagej=True 会自动写入 ImageJ 元数据，使得 ImageJ 能识别为 Hyperstack
        tiff.imwrite(filepath, stack_tcyx, imagej=True, metadata={'axes': 'TCYX'})
        print(f"[Export] Saved input data to {filepath}, Shape={stack_tcyx.shape}")