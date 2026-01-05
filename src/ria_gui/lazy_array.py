"""
Lazy array wrapper for on-demand data loading.
Provides NumPy-like interface over Dask arrays.
"""
import numpy as np
from typing import Union, Tuple, Optional

try:
    import dask.array as da
    DASK_AVAILABLE = True
except ImportError:
    DASK_AVAILABLE = False
    da = None


class LazyArray:
    """
    Wrapper around Dask arrays that provides NumPy-like slicing.

    Key Features:
    - Lazy evaluation: Only computes requested slices
    - NumPy-compatible API: Works with existing GUI code
    - Memory efficient: Doesn't load entire dataset

    Example:
        >>> lazy = LazyArray(dask_array)
        >>> frame = lazy[0]  # Computes only frame 0
        >>> lazy.shape       # (100, 512, 512) - no computation
    """

    def __init__(self, data: Union['da.Array', np.ndarray]):
        if isinstance(data, np.ndarray):
            # Already eager - wrap it anyway for consistency
            if DASK_AVAILABLE:
                self._data = da.from_array(data, chunks='auto')
            else:
                self._data = data
            self._is_eager = True
        else:
            self._data = data
            self._is_eager = False

        self.shape = self._data.shape
        self.dtype = self._data.dtype
        self.ndim = self._data.ndim

    def __getitem__(self, key):
        """
        Slice the array and compute only the requested portion.

        Examples:
            lazy[0]       -> Compute frame 0
            lazy[0:10]    -> Compute frames 0-9
            lazy[:, 0]    -> Compute channel 0 across all frames
        """
        sliced = self._data[key]

        # If result is scalar or small, compute immediately
        if DASK_AVAILABLE and hasattr(sliced, 'compute'):
            return sliced.compute()
        else:
            return sliced

    def __array__(self):
        """
        NumPy compatibility: Allow np.array(lazy) to work.
        WARNING: This loads the entire dataset into memory!
        """
        if DASK_AVAILABLE and hasattr(self._data, 'compute'):
            return self._data.compute()
        return self._data

    def compute(self):
        """Explicitly compute the entire array (use sparingly!)"""
        if DASK_AVAILABLE and hasattr(self._data, 'compute'):
            return self._data.compute()
        return self._data

    def to_numpy(self):
        """Alias for compute()"""
        return self.compute()

    @property
    def is_lazy(self):
        """Check if this is truly lazy (Dask) or eager (NumPy)"""
        return not self._is_eager

    def copy(self):
        """Create a copy of the lazy array"""
        if DASK_AVAILABLE and hasattr(self._data, 'copy'):
            return LazyArray(self._data.copy())
        return LazyArray(self._data.copy())


class MetadataInfo:
    """
    Standardized metadata container returned by all readers.
    """
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
        self.axes = axes  # e.g., "TZCYX"
        self.n_channels = n_channels
        self.n_z = n_z
        self.n_timepoints = n_timepoints
        self.is_explicit_multichannel = is_explicit_multichannel
        self.physical_pixel_sizes = physical_pixel_sizes or {}

    def __repr__(self):
        return (f"MetadataInfo(shape={self.shape}, axes={self.axes}, "
                f"C={self.n_channels}, Z={self.n_z}, T={self.n_timepoints})")
