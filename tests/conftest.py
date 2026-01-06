# tests/conftest.py
import pytest
import numpy as np
import os
import tifffile

@pytest.fixture
def synthetic_data_2ch():
    """
    Creates a synthetic 2-channel time-lapse dataset.
    Shape: (Frames=5, Channels=2, Height=100, Width=100)
    """
    frames, h, w = 5, 100, 100
    # Ch1: Increasing intensity
    ch1 = np.linspace(10, 100, frames * h * w).reshape(frames, h, w)
    # Ch2: Constant intensity
    ch2 = np.ones((frames, h, w)) * 50
    return ch1.astype(np.float32), ch2.astype(np.float32)

@pytest.fixture
def temp_tiff_file(tmp_path, synthetic_data_2ch):
    """
    Saves the synthetic data as a temporary TIFF file for IO testing.
    """
    ch1, ch2 = synthetic_data_2ch
    # Stack to (T, C, Y, X) for saving
    data = np.stack([ch1, ch2], axis=1)
    
    path = tmp_path / "test_image.tif"
    # Save as ImageJ hyperstack order usually (T, Z, C, Y, X) -> we simulate simple TCYX here
    tifffile.imwrite(path, data, imagej=True, metadata={'axes': 'TCYX'})
    return str(path)