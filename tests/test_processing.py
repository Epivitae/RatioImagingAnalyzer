# tests/test_processing.py
import sys
import os
import numpy as np
import pytest

# --- 路径黑魔法 ---
# 为了让测试代码能找到上一级目录里的 processing.py，我们需要把上级目录加到系统路径里
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# 尝试导入你的模块
try:
    from processing import calculate_background, process_frame_ratio, smooth_nan_safe
except ImportError:
    # 如果你的文件在 src/ 下，可能需要调整这里，或者直接运行 pytest
    from src.processing import calculate_background, process_frame_ratio, smooth_nan_safe

# --- 测试用例开始 ---

def test_calculate_background():
    """测试背景计算功能"""
    # 创建一个 10帧 x 100高 x 100宽 的全 100 的矩阵
    data = np.full((10, 100, 100), 100, dtype=np.float32)
    
    # 既然全是 100，那么任何百分位数算出来都应该是 100
    bg = calculate_background(data, percentile=10)
    assert bg == 100.0

    # 测试含有 NaN 的情况
    data[0, 0, 0] = np.nan
    bg = calculate_background(data, percentile=50)
    assert bg == 100.0  # calculate_background 用的是 nanpercentile，应该忽略 NaN

def test_process_frame_ratio_basic():
    """测试基础的比率计算逻辑"""
    # 创建两个简单的 2x2 图像
    # 通道1: 全是 100
    d1 = np.full((2, 2), 100.0, dtype=np.float32)
    # 通道2: 全是 200
    d2 = np.full((2, 2), 200.0, dtype=np.float32)
    
    bg1 = 0
    bg2 = 0
    
    # 理论比率: 100 / 200 = 0.5
    ratio = process_frame_ratio(d1, d2, bg1, bg2, int_thresh=0, ratio_thresh=0, smooth_size=0)
    
    expected = 0.5
    # 使用 np.testing.assert_allclose 来比较浮点数，允许极其微小的误差
    np.testing.assert_allclose(ratio, expected, rtol=1e-5)

def test_process_frame_ratio_thresholds():
    """测试阈值过滤功能"""
    d1 = np.array([[10, 100]], dtype=np.float32)
    d2 = np.array([[20, 200]], dtype=np.float32)
    
    # 设置强度阈值为 50。
    # 第一个像素 (10, 20) 应该被过滤成 NaN，因为 10 < 50
    # 第二个像素 (100, 200) 应该保留，比值为 0.5
    ratio = process_frame_ratio(d1, d2, bg1=0, bg2=0, int_thresh=50, ratio_thresh=0, smooth_size=0)
    
    assert np.isnan(ratio[0, 0])  # 应该被过滤掉
    assert ratio[0, 1] == 0.5     # 应该保留

def test_divide_by_zero_protection():
    """测试分母为0的情况，不能报错，应该是 NaN"""
    d1 = np.array([[100]], dtype=np.float32)
    d2 = np.array([[0]], dtype=np.float32) # 分母为 0
    
    ratio = process_frame_ratio(d1, d2, bg1=0, bg2=0, int_thresh=0, ratio_thresh=0, smooth_size=0)
    
    assert np.isnan(ratio[0, 0])

def test_smooth_nan_safe():
    """测试平滑功能 (依赖 OpenCV)"""
    try:
        import cv2
    except ImportError:
        pytest.skip("OpenCV not installed, skipping smoothing test")

    # 创建一个中间有一个亮点的图像
    img = np.zeros((10, 10), dtype=np.float32)
    img[5, 5] = 100.0
    
    # 平滑后，中心点的值应该降低，周围点的值应该升高
    smoothed = smooth_nan_safe(img, size=3)
    
    assert smoothed[5, 5] < 100.0
    assert smoothed[4, 5] > 0.0
    assert smoothed.shape == img.shape