"""
Modular I/O system with lazy loading support.

Architecture:
    BaseReader (ABC)
        ├── AICSReader (OIR, ND2, CZI) - Uses Dask for lazy loading
        ├── TiffReader (Generic TIFF) - Uses tifffile
        └── Future: Add more readers as needed

Factory function get_reader() automatically selects the correct reader.
"""

import os
import numpy as np
import tifffile as tiff
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from pathlib import Path

try:
    from .lazy_array import LazyArray, MetadataInfo, DASK_AVAILABLE
except ImportError:
    from lazy_array import LazyArray, MetadataInfo, DASK_AVAILABLE

try:
    from aicsimageio import AICSImage
    AICS_AVAILABLE = True
except ImportError:
    AICS_AVAILABLE = False
    AICSImage = None

try:
    import dask.array as da
except ImportError:
    da = None


# ============================================================================
# Abstract Base Reader
# ============================================================================

class BaseReader(ABC):
    """
    Abstract base class for all file format readers.

    All readers must implement:
    1. can_read(path) - Check if this reader can handle the file
    2. read_metadata(path) - Extract metadata without loading pixels
    3. read_lazy(path, **kwargs) - Return lazy-loaded data
    """

    @staticmethod
    @abstractmethod
    def can_read(filepath: str) -> bool:
        """Check if this reader can handle the given file."""
        pass

    @abstractmethod
    def read_metadata(self, filepath: str) -> MetadataInfo:
        """
        Read file metadata without loading pixel data.

        Returns:
            MetadataInfo object with shape, axes, channels, etc.
        """
        pass

    @abstractmethod
    def read_lazy(
        self,
        filepath: str,
        z_proj_method: Optional[str] = None,
        user_axes: Optional[str] = None
    ) -> LazyArray:
        """
        Read file as a lazy array (Dask-backed).

        Args:
            filepath: Path to file
            z_proj_method: "max", "ave", or None
            user_axes: User-specified axes order (e.g., "TZCYX")

        Returns:
            LazyArray in standardized 5D format (T, C, Z, Y, X)
        """
        pass


# ============================================================================
# AICS Reader (OIR, ND2, CZI)
# ============================================================================

class AICSReader(BaseReader):
    """
    Reader for professional microscopy formats using aicsimageio.

    Supported formats:
    - Olympus OIR
    - Nikon ND2
    - Zeiss CZI
    - Leica LIF

    Key feature: Uses Dask for lazy loading (no memory spike on open).
    """

    SUPPORTED_EXTENSIONS = {'.oir', '.nd2', '.czi', '.lif'}

    @staticmethod
    def can_read(filepath: str) -> bool:
        if not AICS_AVAILABLE:
            return False
        ext = Path(filepath).suffix.lower()
        return ext in AICSReader.SUPPORTED_EXTENSIONS

    def read_metadata(self, filepath: str) -> MetadataInfo:
        """
        Read metadata using AICS (fast, doesn't load pixels).
        """
        img = AICSImage(filepath)

        # AICS standardizes to TCZYX
        axes = img.dims.order  # e.g., "TCZYX"
        shape = img.shape

        n_t = img.dims.T
        n_c = img.dims.C
        n_z = img.dims.Z

        is_explicit_multichannel = (n_c > 1)

        # Physical pixel sizes (for calibration)
        physical_sizes = {
            'X': img.physical_pixel_sizes.X,
            'Y': img.physical_pixel_sizes.Y,
            'Z': img.physical_pixel_sizes.Z
        }

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

    def read_lazy(
        self,
        filepath: str,
        z_proj_method: Optional[str] = None,
        user_axes: Optional[str] = None
    ) -> LazyArray:
        """
        Read file as Dask array (lazy loading).

        CRITICAL: Uses img.dask_data instead of img.data to avoid
        loading the entire file into memory.
        """
        img = AICSImage(filepath)

        # Get Dask array (lazy, no memory allocation yet)
        if DASK_AVAILABLE:
            # Use dask_data for lazy loading
            dask_data = img.dask_data  # Shape: (T, C, Z, Y, X)
            print(f"[AICSReader] Lazy loading enabled: {dask_data.shape}")
        else:
            # Fallback to eager loading if Dask not available
            print("WARNING: Dask not available, falling back to eager loading")
            dask_data = img.get_image_data("TCZYX")

        # Apply Z-projection if requested
        if z_proj_method and img.dims.Z > 1:
            dask_data = self._apply_z_projection(dask_data, z_proj_method)

        # AICS already outputs TCZYX, which matches our standard
        # If user specified different axes, transpose accordingly
        if user_axes and user_axes != img.dims.order:
            dask_data = self._transpose_to_standard(dask_data, user_axes)

        return LazyArray(dask_data)

    def _apply_z_projection(self, dask_data, method: str):
        """
        Apply Z-projection on Dask array (lazy operation).

        Args:
            dask_data: Shape (T, C, Z, Y, X)
            method: "max" or "ave"

        Returns:
            Projected array with shape (T, C, 1, Y, X)
        """
        z_axis = 2  # Z is axis 2 in TCZYX

        if DASK_AVAILABLE and hasattr(dask_data, 'max'):
            if method == "max":
                projected = da.max(dask_data, axis=z_axis, keepdims=True)
            elif method == "ave":
                projected = da.mean(dask_data, axis=z_axis, keepdims=True)
            else:
                return dask_data
        else:
            # Fallback to NumPy
            if method == "max":
                projected = np.max(dask_data, axis=z_axis, keepdims=True)
            elif method == "ave":
                projected = np.mean(dask_data, axis=z_axis, keepdims=True)
            else:
                return dask_data

        return projected

    def _transpose_to_standard(self, dask_data, user_axes: str):
        """
        Transpose data to standard TCZYX order.

        Example:
            If user_axes = "TZCYX", transpose to "TCZYX"
        """
        standard = "TCZYX"
        if user_axes == standard:
            return dask_data

        # Build permutation mapping
        perm = [user_axes.index(ax) for ax in standard if ax in user_axes]

        if DASK_AVAILABLE and hasattr(dask_data, 'transpose'):
            return da.transpose(dask_data, perm)
        else:
            return np.transpose(dask_data, perm)


# ============================================================================
# TIFF Reader (Generic)
# ============================================================================

class TiffReader(BaseReader):
    """
    Reader for generic TIFF files using tifffile.

    Handles:
    - ImageJ hyperstacks
    - OME-TIFF
    - Plain multi-page TIFFs

    Note: Currently uses eager loading (loads entire file).
    Future: Could use tifffile's zarr backend for lazy loading.
    """

    @staticmethod
    def can_read(filepath: str) -> bool:
        ext = Path(filepath).suffix.lower()
        return ext in {'.tif', '.tiff'}

    def read_metadata(self, filepath: str) -> MetadataInfo:
        """
        Read TIFF metadata (ImageJ tags, OME-XML, etc.)
        """
        with tiff.TiffFile(filepath) as tif:
            series = tif.series[0]
            shape = series.shape
            dtype = series.dtype
            axes = series.axes  # e.g., "TYX" or "TCYX"

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

                if n_c > 1:
                    is_explicit_multichannel = True

                # Infer axes order from metadata
                axes = self._infer_axes_from_imagej(shape, n_t, n_c, n_z)
            else:
                # Fallback: Guess from shape
                axes = self._guess_axes_from_shape(shape)

            return MetadataInfo(
                shape=shape,
                dtype=dtype,
                axes=axes,
                n_channels=n_c,
                n_z=n_z,
                n_timepoints=n_t,
                is_explicit_multichannel=is_explicit_multichannel
            )

    def read_lazy(
        self,
        filepath: str,
        z_proj_method: Optional[str] = None,
        user_axes: Optional[str] = None
    ) -> LazyArray:
        """
        Read TIFF file.

        TODO: Implement true lazy loading using tifffile's zarr backend.
        Currently loads entire file (eager).
        """
        # Read entire file (eager loading)
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

        return LazyArray(data)

    def _infer_axes_from_imagej(self, shape, n_t, n_c, n_z):
        """
        Infer axes order from ImageJ metadata.

        ImageJ typically stores as TZCYX or TCZYX.
        """
        ndim = len(shape)

        if ndim == 2:
            return "YX"
        elif ndim == 3:
            if n_t > 1:
                return "TYX"
            elif n_z > 1:
                return "ZYX"
            elif n_c > 1:
                return "CYX"
            else:
                return "TYX"  # Default to time
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
            # ImageJ default is TZCYX
            return "TZCYX"

        return "?" * ndim + "YX"

    def _guess_axes_from_shape(self, shape):
        """Fallback: Guess axes from shape alone."""
        ndim = len(shape)

        if ndim == 2:
            return "YX"
        elif ndim == 3:
            return "TYX"
        elif ndim == 4:
            return "TCYX"
        elif ndim == 5:
            return "TCZYX"
        else:
            return "?" * ndim

    def _expand_to_5d(self, data: np.ndarray, axes: str) -> np.ndarray:
        """
        Expand data to 5D (T, C, Z, Y, X) by adding singleton dimensions.

        Example:
            Input: (100, 512, 512) with axes "TYX"
            Output: (100, 1, 1, 512, 512) with axes "TCZYX"
        """
        standard = "TCZYX"
        axes = axes.upper()

        # Build axis mapping
        axis_map = {char: i for i, char in enumerate(axes)}

        # Add missing dimensions
        for ax in standard:
            if ax not in axes:
                # Insert new axis at the beginning
                data = np.expand_dims(data, axis=0)
                axes = ax + axes
                # Update axis_map
                axis_map = {char: i+1 if i >= 0 else i for char, i in axis_map.items()}
                axis_map[ax] = 0

        # Transpose to standard order if needed
        if axes != standard:
            perm = [axes.index(ax) for ax in standard]
            data = np.transpose(data, perm)

        return data

    def _apply_z_projection_numpy(self, data: np.ndarray, method: str) -> np.ndarray:
        """
        Apply Z-projection on NumPy array.

        Args:
            data: Shape (T, C, Z, Y, X)
            method: "max" or "ave"
        """
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
    """
    Automatically select the correct reader for a file.

    Priority:
    1. AICSReader (for OIR, ND2, CZI)
    2. TiffReader (for TIFF)
    3. Raise error if no reader found

    Example:
        >>> reader = get_reader("data/sample.oir")
        >>> meta = reader.read_metadata("data/sample.oir")
        >>> lazy_data = reader.read_lazy("data/sample.oir")
    """
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
) -> List[LazyArray]:
    """
    High-level function to read and split multi-channel data.

    This maintains backward compatibility with existing GUI code.

    Args:
        filepath: Path to file
        is_interleaved: Whether channels are interleaved (frame-by-frame)
        n_channels: Number of channels to split
        z_proj_method: "max", "ave", or None
        user_axes: User-specified axes order
        progress_callback: Function(current, total) for progress updates
        status_callback: Function(message) for status updates

    Returns:
        List of LazyArray objects, one per channel
    """
    if status_callback:
        status_callback("Detecting file format...")

    # Get appropriate reader
    reader = get_reader(filepath)

    if status_callback:
        status_callback(f"Reading with {reader.__class__.__name__}...")

    # Read metadata first (fast)
    meta = reader.read_metadata(filepath)

    if progress_callback:
        progress_callback(1, 3)

    # Read lazy data
    lazy_data = reader.read_lazy(filepath, z_proj_method, user_axes)

    if progress_callback:
        progress_callback(2, 3)

    # Split channels
    if meta.is_explicit_multichannel or n_channels > 1:
        channels = split_channels(lazy_data, n_channels, is_interleaved)
    else:
        channels = [lazy_data]

    if progress_callback:
        progress_callback(3, 3)

    if status_callback:
        status_callback("Ready")

    return channels


def split_channels(
    lazy_data: LazyArray,
    n_channels: int,
    is_interleaved: bool
) -> List[LazyArray]:
    """
    Split multi-channel data into separate LazyArray objects.

    Args:
        lazy_data: Input data (T, C, Z, Y, X)
        n_channels: Number of channels
        is_interleaved: If True, channels are frame-interleaved (TTTCCC)
                       If False, channels are in C dimension

    Returns:
        List of LazyArray objects, one per channel
    """
    if not is_interleaved:
        # Channels are in C dimension: (T, C, Z, Y, X)
        # Split along axis 1
        channels = []
        for c in range(n_channels):
            # Slice channel (lazy operation, no computation)
            ch_data = lazy_data._data[:, c:c+1, :, :, :]
            channels.append(LazyArray(ch_data))
        return channels
    else:
        # Interleaved: Every n_channels frames belong to different channels
        # Example: [T0_C0, T0_C1, T1_C0, T1_C1, ...]
        # Reshape to (T//n_channels, n_channels, Z, Y, X)
        data = lazy_data._data
        t_total = data.shape[0]
        t_per_channel = t_total // n_channels

        channels = []
        for c in range(n_channels):
            # Extract every n_channels-th frame starting from c
            ch_data = data[c::n_channels, :, :, :, :]
            # Expand C dimension if needed
            if ch_data.ndim == 4:
                ch_data = ch_data[:, np.newaxis, :, :, :]
            channels.append(LazyArray(ch_data))

        return channels


def read_separate_files(path1: str, path2: str) -> Tuple[LazyArray, LazyArray]:
    """
    Read two separate files as channel 1 and channel 2.

    Maintains backward compatibility with existing GUI code.
    """
    reader1 = get_reader(path1)
    reader2 = get_reader(path2)

    data1 = reader1.read_lazy(path1)
    data2 = reader2.read_lazy(path2)

    return data1, data2
