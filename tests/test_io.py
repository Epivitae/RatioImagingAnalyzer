# tests/test_io.py
import sys
import os
import numpy as np
import tifffile
import pytest

# --- 路径设置 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from io_utils import read_and_split_dual_channel, read_separate_files
except ImportError:
    from src.io_utils import read_and_split_dual_channel, read_separate_files

def test_read_interleaved(tmp_path):
    """
    测试读取交错堆栈 (Frame1=Ch1, Frame2=Ch2...)
    tmp_path 是 pytest 提供的一个临时文件夹，测试完会自动删除，非常方便。
    """
    # 1. 制造假数据: 10帧 (5个Ch1, 5个Ch2), 64x64像素
    # 偶数帧全为 1，奇数帧全为 2
    data = np.zeros((10, 64, 64), dtype=np.uint16)
    data[0::2] = 1 # Ch1
    data[1::2] = 2 # Ch2
    
    # 2. 保存成临时文件
    fake_file = tmp_path / "test_interleaved.tif"
    tifffile.imwrite(fake_file, data)
    
    # 3. 用你的函数读取
    d1, d2 = read_and_split_dual_channel(str(fake_file), is_interleaved=True)
    
    # 4. 验证结果
    # 形状应该是 (5, 64, 64)
    assert d1.shape == (5, 64, 64)
    assert d2.shape == (5, 64, 64)
    
    # 数值应该没变
    assert np.all(d1 == 1)
    assert np.all(d2 == 2)

def test_read_hyperstack(tmp_path):
    """测试读取 Hyperstack (T, C, Y, X)"""
    # 制造数据: 5个时间点, 2个通道
    data = np.zeros((5, 2, 32, 32), dtype=np.uint16)
    data[:, 0, :, :] = 10 # Ch1
    data[:, 1, :, :] = 20 # Ch2
    
    fake_file = tmp_path / "test_hyperstack.tif"
    tifffile.imwrite(fake_file, data, metadata={'axes': 'TCYX'})
    
    # 非交错模式读取
    d1, d2 = read_and_split_dual_channel(str(fake_file), is_interleaved=False)
    
    assert d1.shape == (5, 32, 32)
    assert d2.shape == (5, 32, 32)
    assert d1[0, 0, 0] == 10
    assert d2[0, 0, 0] == 20