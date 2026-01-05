"""
OIR to TIFF Converter Module

Provides fast conversion from slow-loading formats (OIR, ND2, CZI)
to optimized TIFF format for instant loading.
"""

import os
import numpy as np
import tifffile as tiff
from pathlib import Path
from typing import Optional, Callable

try:
    from aicsimageio import AICSImage
    AICS_AVAILABLE = True
except ImportError:
    AICS_AVAILABLE = False
    AICSImage = None


class OIRConverter:
    """
    Converter for microscopy formats to optimized TIFF.

    Supported input formats: OIR, ND2, CZI, LIF
    Output: Multi-page TIFF with ImageJ metadata
    """

    SUPPORTED_FORMATS = {'.oir', '.nd2', '.czi', '.lif'}

    @staticmethod
    def can_convert(filepath: str) -> bool:
        """Check if file can be converted."""
        if not AICS_AVAILABLE:
            return False
        ext = Path(filepath).suffix.lower()
        return ext in OIRConverter.SUPPORTED_FORMATS

    @staticmethod
    def get_output_path(input_path: str, suffix: str = "_converted") -> str:
        """
        Generate output TIFF path from input path.

        Args:
            input_path: Path to input OIR file
            suffix: Suffix to add before .tif

        Returns:
            Path to output TIFF file

        Example:
            "/data/sample.oir" -> "/data/sample_converted.tif"
        """
        p = Path(input_path)
        return str(p.parent / f"{p.stem}{suffix}.tif")

    @staticmethod
    def check_converted_exists(input_path: str) -> Optional[str]:
        """
        Check if a converted TIFF already exists for this OIR file.

        Returns:
            Path to converted TIFF if exists, None otherwise
        """
        tiff_path = OIRConverter.get_output_path(input_path)
        if os.path.exists(tiff_path):
            # Check if it's newer than the source
            tiff_mtime = os.path.getmtime(tiff_path)
            oir_mtime = os.path.getmtime(input_path)

            if tiff_mtime >= oir_mtime:
                return tiff_path

        return None

    @staticmethod
    def convert(
        input_path: str,
        output_path: Optional[str] = None,
        z_proj_method: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        fast_mode: bool = True
    ) -> str:
        """
        Convert OIR/ND2/CZI file to optimized TIFF.

        Args:
            input_path: Path to input file
            output_path: Path to output TIFF (auto-generated if None)
            z_proj_method: "max", "ave", or None
            progress_callback: Function(current, total) for progress
            status_callback: Function(message) for status updates
            fast_mode: Use eager loading (faster but more memory)

        Returns:
            Path to output TIFF file

        Raises:
            ImportError: If aicsimageio not available
            ValueError: If file format not supported
        """
        if not AICS_AVAILABLE:
            raise ImportError("aicsimageio is required for OIR conversion")

        if not OIRConverter.can_convert(input_path):
            raise ValueError(f"File format not supported: {input_path}")

        # Generate output path if not provided
        if output_path is None:
            output_path = OIRConverter.get_output_path(input_path)

        filename = os.path.basename(input_path)
        filesize_mb = os.path.getsize(input_path) / (1024 * 1024)

        if status_callback:
            status_callback(f"Opening {filename} ({filesize_mb:.1f} MB)...")

        if progress_callback:
            progress_callback(0, 100)

        # Open with AICSImage
        print(f"[OIRConverter] Opening {filename}...")
        img = AICSImage(input_path, reconstruct_mosaic=False)

        if progress_callback:
            progress_callback(10, 100)

        # Get dimensions
        shape = img.shape
        axes = img.dims.order
        n_t = img.dims.T
        n_c = img.dims.C
        n_z = img.dims.Z

        print(f"[OIRConverter] Shape: {shape}, Axes: {axes}")
        print(f"[OIRConverter] T={n_t}, C={n_c}, Z={n_z}")

        if status_callback:
            status_callback(f"Converting {n_t} frames × {n_c} channels...")

        # Strategy: Use eager loading for better performance
        # Fast mode: Direct read without Dask overhead
        if fast_mode:
            if status_callback:
                status_callback(f"Reading data (fast mode)...")

            print(f"[OIRConverter] Using FAST MODE (eager loading)")
            print(f"[OIRConverter] Reading all data at once (20-40s)...")

            # Direct eager loading - skip Dask entirely
            data = img.get_image_data("TCZYX")
            print(f"[OIRConverter] ✓ Data loaded: {data.shape}")

            if progress_callback:
                progress_callback(60, 100)
        else:
            # Original Dask-based method
            try:
                data = img.dask_data
                print(f"[OIRConverter] Using Dask array (lazy loading)")
            except:
                data = img.get_image_data("TCZYX")
                print(f"[OIRConverter] Using eager loading")

            if progress_callback:
                progress_callback(20, 100)

            # Compute if it's a Dask array
            if hasattr(data, 'compute'):
                if status_callback:
                    status_callback("Loading data (Dask compute)...")

                print(f"[OIRConverter] Computing Dask array (30-60 seconds)...")
                data = data.compute()
                print(f"[OIRConverter] ✓ Dask compute complete!")

            if progress_callback:
                progress_callback(60, 100)

        # Ensure data is in TCZYX format
        # data should be (T, C, Z, Y, X)
        print(f"[OIRConverter] Data shape: {data.shape}")

        if status_callback:
            status_callback(f"Writing TIFF file...")

        # Write to TIFF with ImageJ metadata
        # ImageJ format: TZCYX order
        # Need to transpose from TCZYX to TZCYX
        if len(data.shape) == 5:
            # TCZYX -> TZCYX
            data_tzcyx = np.transpose(data, (0, 2, 1, 3, 4))
        else:
            data_tzcyx = data

        print(f"[OIRConverter] Transposed to TZCYX: {data_tzcyx.shape}")

        # Create ImageJ metadata
        imagej_metadata = {
            'axes': 'TZCYX',
            'frames': n_t,
            'slices': n_z,
            'channels': n_c,
        }

        if status_callback:
            status_callback(f"Saving to {os.path.basename(output_path)}...")

        print(f"[OIRConverter] Writing to {output_path}...")

        # Write TIFF file
        tiff.imwrite(
            output_path,
            data_tzcyx,
            imagej=True,
            metadata=imagej_metadata,
            compression='none',  # No compression for speed
            bigtiff=True,  # Support large files
        )

        if progress_callback:
            progress_callback(100, 100)

        if status_callback:
            status_callback(f"✓ Conversion complete!")

        print(f"[OIRConverter] ✓ Saved to {output_path}")

        # Report size savings
        output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"[OIRConverter] Input: {filesize_mb:.1f} MB → Output: {output_size_mb:.1f} MB")

        return output_path


def convert_oir_to_tiff(
    input_path: str,
    output_path: Optional[str] = None,
    z_proj_method: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
    status_callback: Optional[Callable] = None
) -> str:
    """
    Convenience function to convert OIR to TIFF.

    Args:
        input_path: Path to OIR/ND2/CZI file
        output_path: Path to output TIFF (auto if None)
        z_proj_method: "max", "ave", or None
        progress_callback: Progress callback function
        status_callback: Status callback function

    Returns:
        Path to output TIFF file
    """
    converter = OIRConverter()
    return converter.convert(
        input_path,
        output_path,
        z_proj_method,
        progress_callback,
        status_callback
    )
