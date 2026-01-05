# src/model.py
import numpy as np
import tifffile as tiff
import os
from typing import List, Optional, Tuple

# 尝试导入依赖
try:
    from .io_utils import read_and_split_multichannel, read_separate_files, get_reader
    from .processing import calculate_background, process_frame_ratio
    from .lazy_array import LazyArray
except ImportError:
    from io_utils import read_and_split_multichannel, read_separate_files, get_reader
    from processing import calculate_background, process_frame_ratio
    from lazy_array import LazyArray

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
        [REFACTORED] Use new reader system for metadata inspection.

        Returns:
            (is_explicit_multichannel, n_channels, n_z, axes)
        """
        try:
            reader = get_reader(filepath)
            meta = reader.read_metadata(filepath)

            print(f"[Metadata] {reader.__class__.__name__}: {meta.axes} (C:{meta.n_channels}, Z:{meta.n_z})")

            return (
                meta.is_explicit_multichannel,
                meta.n_channels,
                meta.n_z,
                meta.axes
            )
        except Exception as e:
            print(f"[Metadata] Inspection failed: {e}")
            # Fallback to defaults
            return False, 1, 1, "?"

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
        """
        [CRITICAL CHANGE] Background calculation on lazy arrays.

        Strategy: Compute background from a sample of frames (e.g., first 10)
        instead of entire stack to avoid loading everything.
        """
        if self.data1 is None:
            return

        p = self.bg_percent

        # OPTIMIZATION: Sample first 10 frames instead of entire stack
        n_frames = self.data1.shape[0]
        sample_size = min(10, n_frames)

        # Compute sample (this loads only 10 frames into memory)
        # LazyArray.__getitem__ will call .compute() automatically
        sample1 = self.data1[:sample_size]

        # If it's a LazyArray, it's already computed by __getitem__
        # If it's already NumPy, this is a no-op
        if hasattr(sample1, 'compute'):
            sample1 = sample1.compute()

        self.cached_bg1 = calculate_background(sample1, p)

        if self.data2 is not None:
            sample2 = self.data2[:sample_size]
            if hasattr(sample2, 'compute'):
                sample2 = sample2.compute()
            self.cached_bg2 = calculate_background(sample2, p)
        else:
            self.cached_bg2 = 0.0

        self.cached_bg_aux = []
        for aux in self.data_aux:
            sample_aux = aux[:sample_size]
            if hasattr(sample_aux, 'compute'):
                sample_aux = sample_aux.compute()
            self.cached_bg_aux.append(calculate_background(sample_aux, p))

    def get_processed_frame(self, frame_idx, int_thresh=0, ratio_thresh=0, smooth_size=0, log_scale=False, use_custom_bg=False, swap_channels=False):
        """
        [CRITICAL CHANGE] Extract and process a single frame from lazy arrays.

        This is the key method that makes lazy loading work:
        - Only loads the requested frame into memory
        - All other frames remain on disk
        - GUI stays responsive even with 5GB+ files
        """
        if self.data1 is None:
            return None

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

        # Handle view mode (raw channel viewing)
        if self.view_mode == "ch1":
            # LAZY LOAD: Only frame_idx is loaded here
            frame = d_num[frame_idx]  # LazyArray.__getitem__ calls .compute()

            # Squeeze out singleton dimensions (C, Z)
            # Shape: (1, 1, Y, X) -> (Y, X)
            if frame.ndim > 2:
                frame = np.squeeze(frame)

            return np.clip(frame.astype(np.float32) - bg1, 0, None)

        elif self.view_mode == "ch2":
            if self.data2 is None:
                return None
            frame = d_den[frame_idx]
            if frame.ndim > 2:
                frame = np.squeeze(frame)
            return np.clip(frame.astype(np.float32) - bg2, 0, None)

        elif self.view_mode.startswith("aux_"):
            try:
                idx = int(self.view_mode.split("_")[1])
                frame = self.data_aux[idx][frame_idx]
                if frame.ndim > 2:
                    frame = np.squeeze(frame)
                val = bg_aux[idx] if idx < len(bg_aux) else 0
                return np.clip(frame.astype(np.float32) - val, 0, None)
            except:
                return None

        # Default: Ratio mode
        # LAZY LOAD: Extract single frame from each channel
        frame_num = d_num[frame_idx]  # Shape: (1, 1, Y, X) or similar

        # Squeeze to 2D
        if frame_num.ndim > 2:
            frame_num = np.squeeze(frame_num)

        if d_den is not None:
            frame_den = d_den[frame_idx]
            if frame_den.ndim > 2:
                frame_den = np.squeeze(frame_den)
        else:
            frame_den = None

        # Delegate to processing module
        return process_frame_ratio(
            frame_num, frame_den, b_num, b_den,
            int_thresh, ratio_thresh, smooth_size, log_scale
        )

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
        """
        [CRITICAL CHANGE] Export preprocessed input data (streaming).

        This is used to save Z-projected or aligned data for faster reloading.
        Must stream to avoid loading entire stack.
        """
        if self.data1 is None:
            raise ValueError("No data")

        # Collect all channels
        channels = [self.data1]
        if self.data2 is not None:
            channels.append(self.data2)
        channels.extend(self.data_aux)

        n_channels = len(channels)
        n_frames = self.data1.shape[0]

        # Get frame shape (Y, X) from first frame
        sample_frame = channels[0][0]
        if sample_frame.ndim > 2:
            sample_frame = np.squeeze(sample_frame)
        h, w = sample_frame.shape

        # Write frame-by-frame in TCYX order
        with tiff.TiffWriter(filepath, bigtiff=True) as tw:
            for t in range(n_frames):
                # Stack all channels for this timepoint
                frame_stack = []
                for ch in channels:
                    frame = ch[t]  # Lazy load single frame
                    if frame.ndim > 2:
                        frame = np.squeeze(frame)
                    frame_stack.append(frame)

                # Stack channels: (C, Y, X)
                multi_ch_frame = np.stack(frame_stack, axis=0)

                # Write to TIFF
                tw.write(multi_ch_frame, contiguous=True)

        print(f"[Export] Saved {n_frames} frames with {n_channels} channels to {filepath}")