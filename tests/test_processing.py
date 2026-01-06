# tests/test_processing.py
import numpy as np
import pytest
# CHANGE THIS LINE: add .ria_gui
from src.ria_gui.processing import process_frame_ratio, calculate_background

def test_calculate_background():
    img = np.arange(100).reshape(10, 10).astype(np.float32)
    bg = calculate_background(img, percentile=50)
    assert bg == 49.5

def test_process_frame_ratio_basic():
    d1 = np.ones((10, 10)) * 100
    d2 = np.ones((10, 10)) * 50
    bg1, bg2 = 0, 0
    result = process_frame_ratio(d1, d2, bg1, bg2, int_thresh=0, ratio_thresh=0, smooth_size=0)
    assert np.allclose(result, 2.0)

def test_division_by_zero_handling():
    d1 = np.ones((10, 10)) * 100
    d2 = np.zeros((10, 10))
    result = process_frame_ratio(d1, d2, 0, 0, 0, 0, 0)
    assert np.all(np.isnan(result))

def test_thresholding():
    d1 = np.array([[10, 100], [100, 100]])
    d2 = np.ones((2, 2)) * 50
    result = process_frame_ratio(d1, d2, 0, 0, int_thresh=20, ratio_thresh=0, smooth_size=0)
    assert np.isnan(result[0, 0])
    assert not np.isnan(result[0, 1])