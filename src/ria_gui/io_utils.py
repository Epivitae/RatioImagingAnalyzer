# src/io_utils.py
import tifffile as tiff
import numpy as np
import warnings

def read_and_split_multichannel(file_path, is_interleaved, n_channels=2):
    """
    Universal reading function supporting arbitrary channel counts.
    Returns: List [ch0, ch1, ch2, ...]
    """
    try:
        # Read raw data without forcing type conversion to save memory
        raw_data = tiff.imread(file_path)
    except Exception as e:
        raise ValueError(f"Could not read file: {e}")

    channels = []

    # Logic 1: Interleaved Stack (e.g., Ch1, Ch2, Ch3, Ch1...)
    if is_interleaved:
        if raw_data.ndim != 3:
             raise ValueError(f"Interleaved mode requires 3D stack (T, Y, X). Current shape: {raw_data.shape}")
        
        n_frames = raw_data.shape[0]
        # Truncate extra frames that don't fit the cycle
        remainder = n_frames % n_channels
        if remainder != 0:
            raw_data = raw_data[:-remainder]
            
        # Slice to separate channels without extra memory copy
        for c in range(n_channels):
            # start=c, step=n_channels
            channels.append(raw_data[c::n_channels])

    # Logic 2: Hyperstack (4D) - e.g., (T, C, Y, X)
    else:
        if raw_data.ndim == 4:
            # Case A: Standard (T, C, Y, X) -> shape[1] is channel
            if raw_data.shape[1] >= 2 and raw_data.shape[1] <= 10: 
                for c in range(raw_data.shape[1]):
                    channels.append(raw_data[:, c, :, :])
            
            # Case B: ImageJ format (C, T, Y, X) -> shape[0] is channel
            # Heuristic: Channels usually <10, Time frames usually >10
            elif raw_data.shape[0] >= 2 and raw_data.shape[0] <= 10 and raw_data.shape[1] > 10:
                 for c in range(raw_data.shape[0]):
                     channels.append(raw_data[c, :, :, :])
            else:
                raise ValueError(f"Cannot identify channel dimension (T,C,Y,X or C,T,Y,X). Current shape: {raw_data.shape}")
                    
        elif raw_data.ndim == 3:
             raise ValueError("3D data detected. If this is an interleaved multichannel stack, please check 'Mixed Stacks' and set the correct Channel Count.")
        else:
            raise ValueError(f"Unsupported dimensions: {raw_data.shape}")

    # Check for empty result
    if not channels:
        raise ValueError("No channel data extracted.")
        
    # Ensure consistent lengths
    min_len = min(len(c) for c in channels)
    channels = [c[:min_len] for c in channels]

    return channels

def read_and_split_dual_channel(file_path, is_interleaved):
    """Wrapper for backward compatibility, defaults to 2 channels."""
    res = read_and_split_multichannel(file_path, is_interleaved, n_channels=2)
    if len(res) < 2:
        raise ValueError("File contains fewer than 2 channels.")
    return res[0], res[1]

def read_separate_files(path1, path2):
    """Reads two separate files."""
    d1 = tiff.imread(path1)
    d2 = tiff.imread(path2)
    
    if d1.shape != d2.shape:
        # Attempt to auto-fix frame mismatch
        if d1.ndim == d2.ndim and d1.ndim == 3:
             min_frames = min(d1.shape[0], d2.shape[0])
             if min_frames > 0:
                 warnings.warn(f"Frame count mismatch ({d1.shape[0]} vs {d2.shape[0]}). Automatically truncated to {min_frames} frames.")
                 d1 = d1[:min_frames]
                 d2 = d2[:min_frames]
             else:
                 raise ValueError("Severe frame count mismatch between Ch1 and Ch2.")
        else:
            raise ValueError(f"Image dimension mismatch: {d1.shape} vs {d2.shape}")
        
    return d1, d2