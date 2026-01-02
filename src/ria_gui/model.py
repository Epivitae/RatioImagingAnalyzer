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

class AnalysisSession:
    """
    Model 层：管理 RIA 应用程序的核心数据状态和业务逻辑。
    
    职责:
    1. 存储图像数据 (data1, data2, aux)
    2. 管理计算参数 (阈值, 背景百分比等)
    3. 执行 I/O 操作 (读取文件, 解析元数据)
    4. 执行核心计算 (背景计算, 帧处理)
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
        # 注意：UI相关的 BooleanVar (如 use_custom_bg_var) 留在 GUI 里

        # --- 播放器与显示状态 ---
        self.fps: int = 10 
        self.is_playing: bool = False
        self.view_mode: str = "ratio" # ratio, ch1, ch2, aux_0...

    def inspect_file_metadata(self, filepath: str) -> Tuple[bool, int]:
        """
        检查文件的元数据，判断是否为明确的多通道 Tiff 文件。
        
        该方法不会读取整个图像数据，仅读取头信息，因此速度很快。
        
        Args:
            filepath (str): 目标文件的完整路径。
            
        Returns:
            Tuple[bool, int]: 
                - is_multichannel (bool): 如果检测到明确的多通道标记，返回 True。
                - channel_count (int): 检测到的通道数量。如果未检测到，默认为 0。
        """
        # 初始化默认返回值
        is_explicit_multichannel = False
        detected_channels = 0

        try:
            # 使用 tifffile 上下文管理器打开文件
            with tiff.TiffFile(filepath) as tif:
                
                # --- 检测逻辑 A: ImageJ Metadata ---
                # ImageJ 格式通常在 metadata 中包含 'channels' 字段
                if tif.imagej_metadata:
                    # 获取通道数，默认为 1
                    detected_channels = tif.imagej_metadata.get('channels', 1)
                    
                    if detected_channels > 1:
                        is_explicit_multichannel = True
                        return is_explicit_multichannel, detected_channels

                # --- 检测逻辑 B: OME-XML 或 维度分析 ---
                # 检查 Series 0 的维度信息
                if len(tif.series) > 0:
                    series = tif.series[0]
                    
                    # 检查 axes 属性 (例如 'TZCYX')
                    if hasattr(series, 'axes'):
                        axes_str = series.axes
                        
                        if 'C' in axes_str:
                            c_index = axes_str.find('C')
                            # 获取 C 维度的长度
                            c_dim = series.shape[c_index]
                            
                            if c_dim > 1:
                                is_explicit_multichannel = True
                                detected_channels = c_dim
                                
        except Exception as e:
            # 记录错误但不中断程序
            print(f"[Model Warning] Metadata inspection failed for {filepath}: {e}")
            
        return is_explicit_multichannel, detected_channels

    def load_channels_from_file(self, 
                                filepath: str, 
                                is_interleaved: bool, 
                                expected_channels: int) -> List[np.ndarray]:
        """
        从单个文件中读取并分离通道数据。
        
        Args:
            filepath (str): 文件路径。
            is_interleaved (bool): 是否为交错堆栈 (Ch1, Ch2, Ch1, Ch2...)。
            expected_channels (int): 如果是交错模式，指定的通道数量。
            
        Returns:
            List[np.ndarray]: 包含各个通道图像矩阵的列表。
            
        Raises:
            ValueError: 当文件无法读取或通道分离失败时抛出。
        """
        if not filepath or not os.path.exists(filepath):
            raise ValueError(f"File not found: {filepath}")
            
        # 调用 io_utils 中的底层函数
        channels = read_and_split_multichannel(
            filepath, 
            is_interleaved, 
            expected_channels
        )
        
        return channels

    def load_separate_channels(self, path1: str, path2: str) -> List[np.ndarray]:
        """
        从两个独立的文件分别读取 Ch1 和 Ch2。
        
        Args:
            path1 (str): Ch1 文件路径。
            path2 (str): Ch2 文件路径。
            
        Returns:
            List[np.ndarray]: [data_ch1, data_ch2]
        """
        if not path1 or not path2:
            raise ValueError("Both file paths must be provided.")
            
        # 调用底层工具
        d1, d2 = read_separate_files(path1, path2)
        
        return [d1, d2]

    def set_data(self, 
                 data_list: List[np.ndarray], 
                 roles: Optional[dict] = None) -> None:
        """
        将读取到的原始通道数据分配给 model 的属性 (data1, data2, data_aux)。
        
        Args:
            data_list (List[np.ndarray]): 原始通道数据列表。
            roles (dict, optional): 指定通道角色的字典。
                                    格式如 {'num': 0, 'den': 1}。
                                    如果不传，则根据列表长度自动分配。
        """
        count = len(data_list)
        
        # 重置当前数据
        self.data1 = None
        self.data2 = None
        self.data_aux = []
        
        # --- 情况 1: 单通道 ---
        if count == 1:
            self.data1 = data_list[0]
            self.data2 = None
            
        # --- 情况 2: 双通道 (最常见) ---
        elif count == 2:
            # 如果指定了 roles，即使只有2个通道也遵从 roles
            if roles:
                idx_num = roles.get("num", 0)
                idx_den = roles.get("den", 1)
                self.data1 = data_list[idx_num]
                self.data2 = data_list[idx_den]
            else:
                # 默认顺序
                self.data1 = data_list[0]
                self.data2 = data_list[1]
                
        # --- 情况 3: 多通道 (>2) ---
        else:
            if roles is None:
                # 默认分配：前两个为 Ratio 通道，其余为 Aux
                self.data1 = data_list[0]
                self.data2 = data_list[1]
                self.data_aux = data_list[2:]
            else:
                idx_num = roles["num"]
                idx_den = roles["den"]
                
                self.data1 = data_list[idx_num]
                self.data2 = data_list[idx_den]
                
                # 剩下的全部归入 Aux
                for i, d in enumerate(data_list):
                    if i != idx_num and i != idx_den:
                        self.data_aux.append(d)

        # 只要数据更新了，就清理掉旧的 Raw 备份 (用于对齐撤销的)
        self.data1_raw = None
        self.data2_raw = None
        
        # 自动重新计算背景
        self.recalc_background()


    def align_data(self, progress_callback=None) -> None:
        """
        执行图像配准 (ECC 算法)。
        
        Args:
            progress_callback (callable, optional): 
                回调函数，签名需为 (current_frame, total_frames)。
                用于向 UI 报告进度。
                
        Raises:
            ImportError: 如果没有安装 OpenCV。
            ValueError: 如果数据为空。
        """
        # 延迟导入，防止循环依赖或 OpenCV 未安装导致的崩溃
        # 这样只有在用户真正点击“配准”时，才会检查 cv2
        try:
            from processing import align_stack_ecc
        except ImportError:
            try:
                from .processing import align_stack_ecc
            except ImportError:
                raise ImportError("OpenCV (cv2) is required for alignment.")

        if self.data1 is None:
            raise ValueError("No data to align.")

        # 1. 备份原始数据 (用于 Undo)
        # 只有在第一次配准时备份；如果已经在配准状态，就不覆盖原始备份了
        if self.data1_raw is None:
            self.data1_raw = self.data1.copy()
            # 如果是双通道，也备份 data2
            if self.data2 is not None:
                self.data2_raw = self.data2.copy()

        # 2. 准备配准目标
        # 如果是单通道(data2 is None)，就用 data1 自己对自己配准(虽然少见，但逻辑上通顺)
        # 如果是双通道，根据 processing.py 的逻辑，通常是用一个参考另一个
        target_data2 = self.data2 if self.data2 is not None else self.data1
        
        # 3. 调用纯算法 (耗时操作)
        d1_aligned, d2_aligned = align_stack_ecc(
            self.data1, 
            target_data2, 
            progress_callback=progress_callback
        )

        # 4. 更新 Model 状态
        self.data1 = d1_aligned
        if self.data2 is not None:
            self.data2 = d2_aligned
            
        # 5. 配准后像素位置变了，必须重新计算背景值，否则背景扣除会错位
        self.recalc_background()

    def undo_alignment(self) -> bool:
        """
        撤销配准操作，恢复原始数据。
        
        Returns:
            bool: 如果成功恢复返回 True，如果没有备份数据(说明没配准过)返回 False。
        """
        if self.data1_raw is not None:
            # 恢复数据
            self.data1 = self.data1_raw.copy()
            if self.data2_raw is not None:
                self.data2 = self.data2_raw.copy()
            
            # 清空备份 (表示回到了原始状态)
            self.data1_raw = None
            self.data2_raw = None
            
            # 数据变了，重新计算背景
            self.recalc_background()
            return True
            
        return False


    def recalc_background(self) -> None:
        """
        根据当前的 bg_percent 参数，重新计算所有通道的背景值。
        """
        if self.data1 is None:
            return
        
        p = self.bg_percent
        
        # 计算 Data1 背景
        self.cached_bg1 = calculate_background(self.data1, p)
        
        # 计算 Data2 背景
        if self.data2 is not None:
            self.cached_bg2 = calculate_background(self.data2, p)
        else:
            self.cached_bg2 = 0.0
            
        # 计算 Aux 背景
        self.cached_bg_aux = []
        for aux in self.data_aux:
            val = calculate_background(aux, p)
            self.cached_bg_aux.append(val)

    def get_processed_frame(self, 
                            frame_idx: int, 
                            int_thresh: float = 0, 
                            ratio_thresh: float = 0,
                            smooth_size: int = 0,
                            log_scale: bool = False,
                            use_custom_bg: bool = False) -> Optional[np.ndarray]:
        """
        [Pipeline] 获取处理后的一帧图像 (Intensity 或 Ratio)。
        
        Args:
            frame_idx (int): 帧索引。
            int_thresh (float): 强度阈值。
            ratio_thresh (float): 比率阈值。
            smooth_size (int): 平滑内核大小。
            log_scale (bool): 是否进行对数变换。
            use_custom_bg (bool): 是否使用自定义 ROI 背景 (而非全局百分位)。
        
        Returns:
            Optional[np.ndarray]: 处理后的图像矩阵 (2D)。
        """
        if self.data1 is None:
            return None
        
        # 1. 确定背景值
        if use_custom_bg:
            bg1 = self.custom_bg1
            bg2 = self.custom_bg2
            # Aux 背景暂不支持自定义 ROI，仍使用全局
            bg_aux_list = self.cached_bg_aux 
        else:
            bg1 = self.cached_bg1
            bg2 = self.cached_bg2
            bg_aux_list = self.cached_bg_aux

        # 2. 根据 view_mode 决定返回什么
        
        # --- Case A: 查看原始通道 (Ch1) ---
        if self.view_mode == "ch1":
            # 返回：(数据 - 背景)，并 Clip 掉负值
            try:
                raw = self.data1[frame_idx].astype(np.float32) - bg1
                return np.clip(raw, 0, None)
            except IndexError:
                return None
            
        # --- Case B: 查看原始通道 (Ch2) ---
        elif self.view_mode == "ch2":
            if self.data2 is None: return None
            try:
                raw = self.data2[frame_idx].astype(np.float32) - bg2
                return np.clip(raw, 0, None)
            except IndexError:
                return None
            
        # --- Case C: 查看辅助通道 (Aux) ---
        elif self.view_mode.startswith("aux_"):
            try:
                idx = int(self.view_mode.split("_")[1])
                if idx < len(self.data_aux):
                    bg_val = bg_aux_list[idx] if idx < len(bg_aux_list) else 0
                    raw = self.data_aux[idx][frame_idx].astype(np.float32) - bg_val
                    return np.clip(raw, 0, None)
            except: 
                return None
            return None

        # --- Case D: Ratio / Intensity 模式 (默认) ---
        # 调用 processing 模块的核心算法
        return process_frame_ratio(
            self.data1[frame_idx], 
            self.data2[frame_idx] if self.data2 is not None else None,
            bg1, bg2,
            int_thresh, 
            ratio_thresh,
            smooth_size, 
            log_scale
        )
    
    # =========================================================================
    # Export / Save Logic
    # =========================================================================

    def export_processed_stack(self, 
                               filepath: str, 
                               params: dict, 
                               progress_callback=None) -> None:
        """
        将当前参数处理后的所有帧保存为多页 Tiff 文件。
        这个方法结合了 Processing (计算) 和 I/O (写入)，属于业务逻辑层。
        
        Args:
            filepath (str): 保存路径。
            params (dict): 处理参数 (int_thresh, ratio_thresh, smooth, log_scale 等)。
            progress_callback (callable, optional): 进度回调 (current, total)。
        """
        if self.data1 is None:
            raise ValueError("No data to save.")
            
        n_frames = self.data1.shape[0]
        
        # 使用 tifffile 的 Writer 来流式写入，节省内存
        # bigtiff=True 允许保存超过 4GB 的文件，适合长序列成像
        with tiff.TiffWriter(filepath, bigtiff=True) as tif:
            for i in range(n_frames):
                # 1. 核心：调用 Model 自身的处理管道获取图像
                frame_data = self.get_processed_frame(
                    frame_idx=i,
                    int_thresh=params.get("int_thresh", 0),
                    ratio_thresh=params.get("ratio_thresh", 0),
                    smooth_size=params.get("smooth", 0),
                    log_scale=params.get("log_scale", False),
                    use_custom_bg=params.get("use_custom_bg", False)
                )
                
                # 2. 写入文件
                if frame_data is not None:
                    tif.write(frame_data.astype(np.float32), contiguous=True)
                
                # 3. 报告进度
                if progress_callback and i % 5 == 0:
                    progress_callback(i, n_frames)
        
        # 最后报告一次完成
        if progress_callback:
            progress_callback(n_frames, n_frames)

    def export_raw_ratio_stack(self, 
                               filepath: str, 
                               int_thresh: float, 
                               ratio_thresh: float, 
                               progress_callback=None) -> None:
        """
        导出“纯净”的比率堆栈 (不含 Log 变换，不含平滑，仅做基础阈值过滤)。
        这通常用于需要将数据导入其他软件(如 ImageJ)进行进一步量化分析的场景。
        """
        if self.data1 is None:
            raise ValueError("No data to save.")

        n_frames = self.data1.shape[0]
        
        with tiff.TiffWriter(filepath, bigtiff=True) as tif:
            for i in range(n_frames):
                # 强制 smooth=0, log=False, use_custom_bg=False
                # 仅保留最基础的阈值过滤，保留数据的原始性
                frame_data = self.get_processed_frame(
                    frame_idx=i,
                    int_thresh=int_thresh,
                    ratio_thresh=ratio_thresh,
                    smooth_size=0, 
                    log_scale=False,
                    use_custom_bg=False
                )
                
                if frame_data is not None:
                    tif.write(frame_data.astype(np.float32), contiguous=True)

                if progress_callback and i % 5 == 0:
                    progress_callback(i, n_frames)
        
        if progress_callback:
            progress_callback(n_frames, n_frames)

    def export_current_frame(self, filepath: str, frame_idx: int, params: dict) -> None:
        """保存单帧图像"""
        img = self.get_processed_frame(
            frame_idx=frame_idx,
            int_thresh=params.get("int_thresh", 0),
            ratio_thresh=params.get("ratio_thresh", 0),
            smooth_size=params.get("smooth", 0),
            log_scale=params.get("log_scale", False),
            use_custom_bg=params.get("use_custom_bg", False)
        )
        if img is not None:
            tiff.imwrite(filepath, img)
