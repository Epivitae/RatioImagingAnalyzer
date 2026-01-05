# src/model.py
import numpy as np
import tifffile as tiff
import os
from typing import List, Optional, Tuple

# 尝试导入依赖
try:
    from .io_utils import read_and_split_multichannel, read_separate_files, get_reader
    from .processing import calculate_background, process_frame_ratio
except ImportError:
    from io_utils import read_and_split_multichannel, read_separate_files, get_reader
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

        # Backup raw data
        if self.data1_raw is None:
            self.data1_raw = self.data1.copy()
            if self.data2 is not None: self.data2_raw = self.data2.copy()

        # Prepare data for alignment (need 3D: T,Y,X)
        # Current format: (T, C, Z, Y, X) → squeeze to (T, Y, X)
        data1_3d = np.squeeze(self.data1)  # Remove C=1, Z=1 dimensions

        if self.data2 is not None:
            data2_3d = np.squeeze(self.data2)
        else:
            data2_3d = data1_3d

        # Ensure 3D shape
        if data1_3d.ndim != 3:
            raise ValueError(f"Expected 3D data for alignment, got {data1_3d.ndim}D: {data1_3d.shape}")

        # Perform alignment
        d1_a, d2_a, mats = align_stack_ecc(data1_3d, data2_3d, progress_callback)

        # Restore to 5D format (T, C, Z, Y, X)
        # Add back C and Z dimensions
        self.data1 = d1_a[:, np.newaxis, np.newaxis, :, :]
        if self.data2 is not None:
            self.data2 = d2_a[:, np.newaxis, np.newaxis, :, :]

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

        # Convert to 3D for processing
        data1_3d = np.squeeze(self.data1)
        aligned_1 = apply_alignment_matrices(data1_3d, mats)
        self.data1 = aligned_1[:, np.newaxis, np.newaxis, :, :]

        if self.data2 is not None:
            data2_3d = np.squeeze(self.data2)
            aligned_2 = apply_alignment_matrices(data2_3d, mats)
            self.data2 = aligned_2[:, np.newaxis, np.newaxis, :, :]

        self.alignment_matrices = mats
        self.recalc_background()

    def recalc_background(self):
        """Calculate background from sample of frames."""
        if self.data1 is None:
            return

        print(f"\n[recalc_background] Calculating background...")

        p = self.bg_percent
        n_frames = self.data1.shape[0]
        sample_size = min(10, n_frames)

        # Sample first 10 frames
        sample1 = self.data1[:sample_size]
        self.cached_bg1 = calculate_background(sample1, p)
        print(f"[recalc_background] ✓ bg1 = {self.cached_bg1:.4f}")

        if self.data2 is not None:
            sample2 = self.data2[:sample_size]
            self.cached_bg2 = calculate_background(sample2, p)
            print(f"[recalc_background] ✓ bg2 = {self.cached_bg2:.4f}")
        else:
            self.cached_bg2 = 0.0

        self.cached_bg_aux = []
        for i, aux in enumerate(self.data_aux):
            sample_aux = aux[:sample_size]
            self.cached_bg_aux.append(calculate_background(sample_aux, p))

        print(f"[recalc_background] ✓ Complete!\n")

    def get_processed_frame(self, frame_idx, int_thresh=0, ratio_thresh=0, smooth_size=0, log_scale=False, use_custom_bg=False, swap_channels=False):
        """
        [CRITICAL CHANGE] Extract and process a single frame from lazy arrays.

        This is the key method that makes lazy loading work:
        - Only loads the requested frame into memory
        - All other frames remain on disk
        - GUI stays responsive even with 5GB+ files

        DEFENSIVE CODING: Added extensive debug prints and shape validation.
        """
        if self.data1 is None:
            return None

        print(f"\n[get_processed_frame] === Frame {frame_idx} ===")
        print(f"[get_processed_frame] data1.shape: {self.data1.shape}")
        if self.data2 is not None:
            print(f"[get_processed_frame] data2.shape: {self.data2.shape}")

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
            print(f"[get_processed_frame] ch1 raw shape: {frame.shape}")

            # FORCE SQUEEZE: Remove all singleton dimensions
            frame = np.squeeze(frame)
            print(f"[get_processed_frame] ch1 after squeeze: {frame.shape}")

            # SAFETY CHECK: Must be 2D
            if frame.ndim != 2:
                raise ValueError(
                    f"Expected 2D frame for ch1 view, got {frame.ndim}D: {frame.shape}. "
                    f"Frame index: {frame_idx}, data1 shape: {self.data1.shape}"
                )

            # SAFETY CHECK: No zero dimensions
            if 0 in frame.shape:
                raise ValueError(
                    f"Frame has zero-dimension! Shape: {frame.shape}. "
                    f"Frame index: {frame_idx}, data1 shape: {self.data1.shape}"
                )

            return np.clip(frame.astype(np.float32) - bg1, 0, None)

        elif self.view_mode == "ch2":
            if self.data2 is None:
                return None
            frame = d_den[frame_idx]
            print(f"[get_processed_frame] ch2 raw shape: {frame.shape}")

            frame = np.squeeze(frame)
            print(f"[get_processed_frame] ch2 after squeeze: {frame.shape}")

            if frame.ndim != 2:
                raise ValueError(f"Expected 2D frame for ch2 view, got {frame.ndim}D: {frame.shape}")
            if 0 in frame.shape:
                raise ValueError(f"Frame has zero-dimension! Shape: {frame.shape}")

            return np.clip(frame.astype(np.float32) - bg2, 0, None)

        elif self.view_mode.startswith("aux_"):
            try:
                idx = int(self.view_mode.split("_")[1])
                frame = self.data_aux[idx][frame_idx]
                print(f"[get_processed_frame] aux_{idx} raw shape: {frame.shape}")

                frame = np.squeeze(frame)
                print(f"[get_processed_frame] aux_{idx} after squeeze: {frame.shape}")

                if frame.ndim != 2 or 0 in frame.shape:
                    raise ValueError(f"Invalid aux frame shape: {frame.shape}")

                val = bg_aux[idx] if idx < len(bg_aux) else 0
                return np.clip(frame.astype(np.float32) - val, 0, None)
            except Exception as e:
                print(f"[ERROR] Failed to get aux frame: {e}")
                return None

        # Default: Ratio mode
        # LAZY LOAD: Extract single frame from each channel
        print(f"[get_processed_frame] Extracting frame {frame_idx} from data1...")
        frame_num = d_num[frame_idx]  # Shape: (1, 1, Y, X) or similar
        print(f"[get_processed_frame] frame_num raw shape: {frame_num.shape}, dtype: {frame_num.dtype}")

        # FORCE SQUEEZE: Remove all singleton dimensions
        frame_num = np.squeeze(frame_num)
        print(f"[get_processed_frame] frame_num after squeeze: {frame_num.shape}")

        # SAFETY CHECK: Must be 2D
        if frame_num.ndim != 2:
            raise ValueError(
                f"Expected 2D frame_num, got {frame_num.ndim}D: {frame_num.shape}. "
                f"Frame index: {frame_idx}, data1 shape: {d_num.shape}"
            )

        # SAFETY CHECK: No zero dimensions
        if 0 in frame_num.shape:
            raise ValueError(
                f"frame_num has zero-dimension! Shape: {frame_num.shape}. "
                f"Frame index: {frame_idx}, data1 shape: {d_num.shape}"
            )

        if d_den is not None:
            print(f"[get_processed_frame] Extracting frame {frame_idx} from data2...")
            frame_den = d_den[frame_idx]
            print(f"[get_processed_frame] frame_den raw shape: {frame_den.shape}, dtype: {frame_den.dtype}")

            frame_den = np.squeeze(frame_den)
            print(f"[get_processed_frame] frame_den after squeeze: {frame_den.shape}")

            if frame_den.ndim != 2:
                raise ValueError(
                    f"Expected 2D frame_den, got {frame_den.ndim}D: {frame_den.shape}. "
                    f"Frame index: {frame_idx}, data2 shape: {d_den.shape}"
                )

            if 0 in frame_den.shape:
                raise ValueError(
                    f"frame_den has zero-dimension! Shape: {frame_den.shape}. "
                    f"Frame index: {frame_idx}, data2 shape: {d_den.shape}"
                )

            # SHAPE COMPATIBILITY CHECK
            if frame_num.shape != frame_den.shape:
                raise ValueError(
                    f"Shape mismatch between channels! "
                    f"frame_num: {frame_num.shape}, frame_den: {frame_den.shape}. "
                    f"Frame index: {frame_idx}"
                )
        else:
            frame_den = None

        print(f"[get_processed_frame] Passing to process_frame_ratio: "
              f"frame_num={frame_num.shape}, frame_den={frame_den.shape if frame_den is not None else None}")

        # Delegate to processing module
        result = process_frame_ratio(
            frame_num, frame_den, b_num, b_den,
            int_thresh, ratio_thresh, smooth_size, log_scale
        )

        print(f"[get_processed_frame] Result shape: {result.shape if result is not None else None}")
        return result

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