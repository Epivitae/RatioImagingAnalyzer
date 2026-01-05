"""
Simplified I/O system without lazy loading.

Simple and clean: Just read files and return NumPy arrays.
"""

import os
import numpy as np
import tifffile as tiff
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from pathlib import Path

try:
    from aicsimageio import AICSImage
    AICS_AVAILABLE = True
except ImportError:
    AICS_AVAILABLE = False
    AICSImage = None


# ============================================================================
# Metadata Container
# ============================================================================

class MetadataInfo:
    """Standardized metadata container."""
    def __init__(
        self,
        shape: Tuple[int, ...],
        dtype: np.dtype,
        axes: str,
        n_channels: int,
        n_z: int,
        n_timepoints: int,
        is_explicit_multichannel: bool,
        physical_pixel_sizes: Optional[dict] = None
    ):
        self.shape = shape
        self.dtype = dtype
        self.axes = axes
        self.n_channels = n_channels
        self.n_z = n_z
        self.n_timepoints = n_timepoints
        self.is_explicit_multichannel = is_explicit_multichannel
        self.physical_pixel_sizes = physical_pixel_sizes or {}

    def __repr__(self):
        return (f"MetadataInfo(shape={self.shape}, axes={self.axes}, "
                f"C={self.n_channels}, Z={self.n_z}, T={self.n_timepoints})")


# ============================================================================
# Abstract Base Reader
# ============================================================================

class BaseReader(ABC):
    """Abstract base class for all file format readers."""

    @staticmethod
    @abstractmethod
    def can_read(filepath: str) -> bool:
        """Check if this reader can handle the given file."""
        pass

    @abstractmethod
    def read_metadata(self, filepath: str) -> MetadataInfo:
        """Read file metadata without loading pixel data."""
        pass

    @abstractmethod
    def read_data(
        self,
        filepath: str,
        z_proj_method: Optional[str] = None,
        user_axes: Optional[str] = None
    ) -> np.ndarray:
        """
        Read file as NumPy array.

        Returns:
            NumPy array in standardized 5D format (T, C, Z, Y, X)
        """
        pass


# ============================================================================
# AICS Reader (OIR, ND2, CZI)
# ============================================================================

class AICSReader(BaseReader):
    """Reader for professional microscopy formats using aicsimageio."""

    SUPPORTED_EXTENSIONS = {'.oir', '.nd2', '.czi', '.lif'}

    @staticmethod
    def can_read(filepath: str) -> bool:
        if not AICS_AVAILABLE:
            return False
        ext = Path(filepath).suffix.lower()
        return ext in AICSReader.SUPPORTED_EXTENSIONS

    def read_metadata(self, filepath: str) -> MetadataInfo:
        """Read metadata using AICS (fast, doesn't load pixels)."""
        print(f"[AICSReader] Opening {os.path.basename(filepath)}...")

        try:
            img = AICSImage(filepath, reconstruct_mosaic=False)
        except TypeError:
            img = AICSImage(filepath)

        print(f"[AICSReader] File opened, reading metadata...")

        axes = img.dims.order
        shape = img.shape
        n_t = img.dims.T
        n_c = img.dims.C
        n_z = img.dims.Z

        is_explicit_multichannel = (n_c > 1)

        try:
            physical_sizes = {
                'X': img.physical_pixel_sizes.X,
                'Y': img.physical_pixel_sizes.Y,
                'Z': img.physical_pixel_sizes.Z
            }
        except:
            physical_sizes = {}

        print(f"[AICSReader] Metadata ready: {axes} {shape}")

        return MetadataInfo(
            shape=shape,
            dtype=img.dtype,
            axes=axes,
            n_channels=n_c,
            n_z=n_z,
            n_timepoints=n_t,
            is_explicit_multichannel=is_explicit_multichannel,
            physical_pixel_sizes=physical_sizes
        )

    def read_data(
        self,
        filepath: str,
        z_proj_method: Optional[str] = None,
        user_axes: Optional[str] = None
    ) -> np.ndarray:
        """Read file as NumPy array (EAGER loading)."""
        print(f"[AICSReader] Loading {os.path.basename(filepath)} into memory...")

        try:
            img = AICSImage(filepath, reconstruct_mosaic=False)
        except TypeError:
            img = AICSImage(filepath)

        # EAGER LOADING: Load entire file
        print(f"[AICSReader] Reading pixel data (this may take 20-60 seconds)...")
        data = img.get_image_data("TCZYX")
        print(f"[AICSReader] ✓ Data loaded: {data.shape}, {data.dtype}")

        # Apply Z-projection if requested
        if z_proj_method and img.dims.Z > 1:
            print(f"[AICSReader] Applying Z-projection ({z_proj_method})...")
            data = self._apply_z_projection(data, z_proj_method)
            print(f"[AICSReader] ✓ Z-projection applied: {data.shape}")

        return data

    def _apply_z_projection(self, data: np.ndarray, method: str) -> np.ndarray:
        """Apply Z-projection on NumPy array."""
        z_axis = 2  # Z is axis 2 in TCZYX

        if method == "max":
            return np.max(data, axis=z_axis, keepdims=True)
        elif method == "ave":
            return np.mean(data, axis=z_axis, keepdims=True)
        else:
            return data


# ============================================================================
# TIFF Reader (Generic)
# ============================================================================

class TiffReader(BaseReader):
    """Reader for generic TIFF files using tifffile."""

    @staticmethod
    def can_read(filepath: str) -> bool:
        ext = Path(filepath).suffix.lower()
        return ext in {'.tif', '.tiff'}

    def read_metadata(self, filepath: str) -> MetadataInfo:
        """
        Read TIFF metadata (ImageJ tags, OME-XML, etc.)

        CRITICAL FIX: Improved axes detection to avoid TYX being misidentified as ZYX.
        """
        with tiff.TiffFile(filepath) as tif:
            series = tif.series[0]
            shape = series.shape
            dtype = series.dtype

            # CRITICAL: Use tifffile's detected axes first (most reliable)
            axes_detected = series.axes

            print(f"[TiffReader] File shape: {shape}")
            print(f"[TiffReader] Tifffile detected axes: {axes_detected}")

            # Try to extract ImageJ metadata
            n_c = 1
            n_z = 1
            n_t = 1
            is_explicit_multichannel = False

            ij_meta = tif.imagej_metadata
            if ij_meta:
                n_c = ij_meta.get('channels', 1)
                n_z = ij_meta.get('slices', 1)
                n_t = ij_meta.get('frames', 1)

                print(f"[TiffReader] ImageJ metadata: T={n_t}, C={n_c}, Z={n_z}")

                if n_c > 1:
                    is_explicit_multichannel = True

                # Use ImageJ metadata to refine axes
                axes = self._infer_axes_from_imagej(shape, n_t, n_c, n_z, axes_detected)
            else:
                # No ImageJ metadata - use tifffile's detection or smart guess
                print(f"[TiffReader] No ImageJ metadata, using smart detection")

                if axes_detected and len(axes_detected) == len(shape):
                    # Trust tifffile's detection
                    axes = axes_detected
                    print(f"[TiffReader] Using tifffile axes: {axes}")

                    # Update n_t, n_c, n_z based on detected axes
                    if 'T' in axes:
                        n_t = shape[axes.index('T')]
                    if 'C' in axes:
                        n_c = shape[axes.index('C')]
                        is_explicit_multichannel = True
                    if 'Z' in axes:
                        n_z = shape[axes.index('Z')]
                else:
                    # Fallback: Smart guess with preference for time series
                    axes = self._guess_axes_from_shape(shape)
                    print(f"[TiffReader] Guessed axes: {axes}")

            print(f"[TiffReader] Final axes: {axes} (T={n_t}, C={n_c}, Z={n_z})")

            return MetadataInfo(
                shape=shape,
                dtype=dtype,
                axes=axes,
                n_channels=n_c,
                n_z=n_z,
                n_timepoints=n_t,
                is_explicit_multichannel=is_explicit_multichannel
            )

    def read_data(
        self,
        filepath: str,
        z_proj_method: Optional[str] = None,
        user_axes: Optional[str] = None
    ) -> np.ndarray:
        """Read TIFF file as NumPy array."""
        # Read entire file
        data = tiff.imread(filepath)

        # Get metadata to determine axes
        meta = self.read_metadata(filepath)
        axes = user_axes if user_axes else meta.axes

        print(f"[TiffReader] Read shape: {data.shape}, axes: {axes}")

        # Expand to 5D (T, C, Z, Y, X)
        data = self._expand_to_5d(data, axes)

        print(f"[TiffReader] Expanded to 5D: {data.shape}")

        # Apply Z-projection if needed
        if z_proj_method and data.shape[2] > 1:
            data = self._apply_z_projection_numpy(data, z_proj_method)

        return data

    def _infer_axes_from_imagej(self, shape, n_t, n_c, n_z, axes_detected=None):
        """
        Infer axes order from ImageJ metadata.

        CRITICAL FIX: Use axes_detected as hint to avoid misidentification.
        """
        ndim = len(shape)

        if ndim == 2:
            return "YX"

        elif ndim == 3:
            # CRITICAL: For 3D data, prefer time series over Z-stack

            # Check axes_detected first (most reliable)
            if axes_detected and len(axes_detected) == 3:
                if 'T' in axes_detected:
                    return "TYX"
                elif 'Z' in axes_detected:
                    return "ZYX"
                elif 'C' in axes_detected:
                    return "CYX"

            # Use ImageJ metadata
            if n_t > 1 and n_z <= 1:
                return "TYX"  # Time series
            elif n_z > 1 and n_t <= 1:
                return "ZYX"  # Z-stack
            elif n_c > 1:
                return "CYX"  # Multi-channel
            else:
                # Default: Assume time series (most common)
                print("[TiffReader] Ambiguous 3D data, defaulting to TYX (time series)")
                return "TYX"

        elif ndim == 4:
            if n_t > 1 and n_c > 1:
                return "TCYX"
            elif n_t > 1 and n_z > 1:
                return "TZYX"
            elif n_c > 1 and n_z > 1:
                return "CZYX"
            else:
                return "TCYX"

        elif ndim == 5:
            return "TZCYX"

        return "?" * ndim + "YX"

    def _guess_axes_from_shape(self, shape):
        """Fallback: Guess axes from shape alone."""
        ndim = len(shape)

        if ndim == 2:
            return "YX"
        elif ndim == 3:
            return "TYX"  # Default to time series
        elif ndim == 4:
            return "TCYX"
        elif ndim == 5:
            return "TCZYX"
        else:
            return "?" * ndim

    def _expand_to_5d(self, data: np.ndarray, axes: str) -> np.ndarray:
        """Expand data to 5D (T, C, Z, Y, X) by adding singleton dimensions."""
        standard = "TCZYX"
        axes = axes.upper()

        # Add missing dimensions
        for ax in standard:
            if ax not in axes:
                data = np.expand_dims(data, axis=0)
                axes = ax + axes

        # Transpose to standard order if needed
        if axes != standard:
            perm = [axes.index(ax) for ax in standard]
            data = np.transpose(data, perm)

        # CRITICAL FIX: Handle pure Z-stacks (T=1, Z>1) by swapping T and Z
        # This allows browsing Z slices as if they were time frames
        if data.shape[0] == 1 and data.shape[2] > 1:
            print(f"[TiffReader] Detected pure Z-stack (T=1, Z={data.shape[2]}), swapping T↔Z axes")
            # Swap T and Z: (1, C, Z, Y, X) → (Z, C, 1, Y, X)
            data = np.swapaxes(data, 0, 2)
            print(f"[TiffReader] New shape after swap: {data.shape}")

        return data

    def _apply_z_projection_numpy(self, data: np.ndarray, method: str) -> np.ndarray:
        """Apply Z-projection on NumPy array."""
        z_axis = 2

        if method == "max":
            return np.max(data, axis=z_axis, keepdims=True)
        elif method == "ave":
            return np.mean(data, axis=z_axis, keepdims=True)
        else:
            return data


# ============================================================================
# Factory Function
# ============================================================================

def get_reader(filepath: str) -> BaseReader:
    """Automatically select the correct reader for a file."""
    readers = [AICSReader(), TiffReader()]

    for reader in readers:
        if reader.can_read(filepath):
            print(f"[IO] Selected reader: {reader.__class__.__name__}")
            return reader

    raise ValueError(f"No reader found for file: {filepath}")


# ============================================================================
# High-Level API (Backward Compatibility)
# ============================================================================

def read_and_split_multichannel(
    filepath: str,
    is_interleaved: bool,
    n_channels: int,
    z_proj_method: Optional[str] = None,
    user_axes: Optional[str] = None,
    progress_callback=None,
    status_callback=None
) -> List[np.ndarray]:
    """
    High-level function to read and split multi-channel data.

    Returns:
        List of NumPy arrays, one per channel (EAGER loading)
    """
    import os
    filename = os.path.basename(filepath)
    filesize_mb = os.path.getsize(filepath) / (1024 * 1024)

    if status_callback:
        status_callback("Detecting file format...")

    reader = get_reader(filepath)

    if progress_callback:
        progress_callback(0, 100)

    if status_callback:
        status_callback(f"Reading {filename} ({filesize_mb:.1f} MB)...")

    # Read metadata
    meta = reader.read_metadata(filepath)

    if progress_callback:
        progress_callback(20, 100)

    if status_callback:
        status_callback(f"Loading pixel data...")

    # Read data (EAGER loading)
    data = reader.read_data(filepath, z_proj_method, user_axes)

    if progress_callback:
        progress_callback(80, 100)

    if status_callback:
        status_callback(f"Splitting {n_channels} channels...")

    # Split channels
    if meta.is_explicit_multichannel or n_channels > 1:
        channels = split_channels(data, n_channels, is_interleaved)
    else:
        channels = [data]

    if progress_callback:
        progress_callback(100, 100)

    if status_callback:
        status_callback("✓ Ready!")

    return channels


def split_channels(
    data: np.ndarray,
    n_channels: int,
    is_interleaved: bool
) -> List[np.ndarray]:
    """
    Split multi-channel data into separate NumPy arrays.

    Args:
        data: Input data (T, C, Z, Y, X)
        n_channels: Number of channels
        is_interleaved: If True, channels are frame-interleaved

    Returns:
        List of NumPy arrays, one per channel
    """
    print(f"[split_channels] Input shape: {data.shape}, n_channels: {n_channels}, interleaved: {is_interleaved}")

    if not is_interleaved:
        # Channels are in C dimension: (T, C, Z, Y, X)
        channels = []

        actual_c = data.shape[1]
        if n_channels > actual_c:
            print(f"[WARNING] Requested {n_channels} channels but data only has {actual_c}. Using {actual_c}.")
            n_channels = actual_c

        for c in range(n_channels):
            ch_data = data[:, c:c+1, :, :, :]
            print(f"[split_channels] Channel {c} shape: {ch_data.shape}")
            channels.append(ch_data)

        return channels
    else:
        # Interleaved mode
        t_total = data.shape[0]
        t_per_channel = t_total // n_channels

        print(f"[split_channels] Interleaved mode: {t_total} total frames → {t_per_channel} frames per channel")

        if t_total < n_channels:
            raise ValueError(f"Cannot split {t_total} frames into {n_channels} channels.")

        channels = []
        for c in range(n_channels):
            ch_data = data[c::n_channels, :, :, :, :]

            if ch_data.shape[0] == 0:
                raise ValueError(f"Channel {c} extracted 0 frames!")

            if ch_data.ndim == 4:
                ch_data = ch_data[:, np.newaxis, :, :, :]

            print(f"[split_channels] Interleaved channel {c} final shape: {ch_data.shape}")
            channels.append(ch_data)

        return channels


def read_separate_files(path1: str, path2: str) -> Tuple[np.ndarray, np.ndarray]:
    """Read two separate files as channel 1 and channel 2."""
    reader1 = get_reader(path1)
    reader2 = get_reader(path2)

    data1 = reader1.read_data(path1)
    data2 = reader2.read_data(path2)

    return data1, data2
