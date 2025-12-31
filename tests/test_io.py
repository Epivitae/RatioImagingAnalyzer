# tests/test_io.py
import numpy as np
import tifffile
import pytest
from ria_gui.io_utils import read_and_split_dual_channel, read_separate_files

def test_read_interleaved(tmp_path):
    """测试读取交错堆栈"""
    data = np.zeros((10, 64, 64), dtype=np.uint16)
    data[0::2] = 1 # Ch1
    data[1::2] = 2 # Ch2
    
    fake_file = tmp_path / "test_interleaved.tif"
    tifffile.imwrite(fake_file, data)
    
    d1, d2 = read_and_split_dual_channel(str(fake_file), is_interleaved=True)
    
    assert d1.shape == (5, 64, 64)
    assert d2.shape == (5, 64, 64)
    assert np.all(d1 == 1)
    assert np.all(d2 == 2)

def test_read_hyperstack(tmp_path):
    """测试读取 Hyperstack (T, C, Y, X)"""
    data = np.zeros((5, 2, 32, 32), dtype=np.uint16)
    data[:, 0, :, :] = 10 # Ch1
    data[:, 1, :, :] = 20 # Ch2
    
    fake_file = tmp_path / "test_hyperstack.tif"
    tifffile.imwrite(fake_file, data, metadata={'axes': 'TCYX'})
    
    d1, d2 = read_and_split_dual_channel(str(fake_file), is_interleaved=False)
    
    assert d1.shape == (5, 32, 32)
    assert d2.shape == (5, 32, 32)
    assert d1[0, 0, 0] == 10
    assert d2[0, 0, 0] == 20