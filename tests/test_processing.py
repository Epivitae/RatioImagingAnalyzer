# tests/test_processing.py
import numpy as np
import pytest
from ria_gui.processing import calculate_background, process_frame_ratio, smooth_nan_safe

# --- 测试用例开始 ---

def test_calculate_background():
    """测试背景计算功能"""
    data = np.full((10, 100, 100), 100, dtype=np.float32)
    bg = calculate_background(data, percentile=10)
    assert bg == 100.0

    data[0, 0, 0] = np.nan
    bg = calculate_background(data, percentile=50)
    assert bg == 100.0

def test_process_frame_ratio_basic():
    """测试基础的比率计算逻辑"""
    d1 = np.full((2, 2), 100.0, dtype=np.float32)
    d2 = np.full((2, 2), 200.0, dtype=np.float32)
    bg1, bg2 = 0, 0
    ratio = process_frame_ratio(d1, d2, bg1, bg2, int_thresh=0, ratio_thresh=0, smooth_size=0)
    expected = 0.5
    np.testing.assert_allclose(ratio, expected, rtol=1e-5)

def test_process_frame_ratio_thresholds():
    """测试阈值过滤功能"""
    d1 = np.array([[10, 100]], dtype=np.float32)
    d2 = np.array([[20, 200]], dtype=np.float32)
    ratio = process_frame_ratio(d1, d2, bg1=0, bg2=0, int_thresh=50, ratio_thresh=0, smooth_size=0)
    assert np.isnan(ratio[0, 0])
    assert ratio[0, 1] == 0.5

def test_divide_by_zero_protection():
    """测试分母为0的情况"""
    d1 = np.array([[100]], dtype=np.float32)
    d2 = np.array([[0]], dtype=np.float32)
    ratio = process_frame_ratio(d1, d2, bg1=0, bg2=0, int_thresh=0, ratio_thresh=0, smooth_size=0)
    assert np.isnan(ratio[0, 0])

def test_smooth_nan_safe():
    """测试平滑功能 (依赖 OpenCV)"""
    try:
        import cv2
    except ImportError:
        pytest.skip("OpenCV not installed, skipping smoothing test")

    img = np.zeros((10, 10), dtype=np.float32)
    img[5, 5] = 100.0
    smoothed = smooth_nan_safe(img, size=3)
    assert smoothed[5, 5] < 100.0
    assert smoothed[4, 5] > 0.0
    assert smoothed.shape == img.shape