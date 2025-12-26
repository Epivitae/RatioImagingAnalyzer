import pytest
import numpy as np
import sys
import os

# 确保能导入 src 目录下的模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.processing import calculate_background, process_frame_ratio, smooth_nan_safe

def test_calculate_background():
    """测试背景计算 (百分位数) 是否准确"""
    # 创建一个 0 到 100 的数组
    data = np.arange(101, dtype=float).reshape(1, 101)
    # 第 50 百分位数应该是 50
    bg = calculate_background(data, 50)
    assert bg == 50.0

def test_process_frame_ratio_basic():
    """测试核心比率计算逻辑 R = (C1-Bg)/(C2-Bg)"""
    # 模拟数据 2x2 像素
    ch1 = np.array([[120.0, 220.0], [10.0, 120.0]])
    ch2 = np.array([[ 60.0,  60.0], [60.0,   0.0]]) # 右下角是0，测试除零
    bg = 20.0
    
    # 预期计算过程:
    # 扣背景后 ch1: [[100, 200], [0, 100]]
    # 扣背景后 ch2: [[ 40,  40], [40,   0]]
    # 比值: 
    # (0,0): 100/40 = 2.5
    # (0,1): 200/40 = 5.0
    # (1,0): 0/40 = 0.0 (强度低，但分母不为0)
    # (1,1): 100/0 = NaN (分母为0，应处理为NaN)

    result = process_frame_ratio(
        ch1, ch2, 
        bg1=bg, bg2=bg, 
        int_thresh=0, ratio_thresh=0, 
        smooth_size=0, log_scale=False
    )

    assert result[0, 0] == 2.5
    assert result[0, 1] == 5.0
    assert result[1, 0] == 0.0
    assert np.isnan(result[1, 1])  # 确保除零变成了 NaN 而不是报错

def test_thresholding():
    """测试阈值过滤功能"""
    ch1 = np.array([[100.0]])
    ch2 = np.array([[100.0]])
    # 正常比值是 1.0
    
    # 1. 测试强度阈值 (设为 200，原图100应被过滤)
    res_int = process_frame_ratio(ch1, ch2, 0, 0, int_thresh=200, ratio_thresh=0, smooth_size=0)
    assert np.isnan(res_int[0, 0])

    # 2. 测试比率阈值 (设为 2.0，原比率1.0应被过滤)
    res_ratio = process_frame_ratio(ch1, ch2, 0, 0, int_thresh=0, ratio_thresh=2.0, smooth_size=0)
    assert np.isnan(res_ratio[0, 0])

def test_smooth_nan_safe():
    """测试平滑算法是否能保留数值"""
    # 创建一个中间有值的 3x3 矩阵
    data = np.full((3, 3), 10.0)
    data[1, 1] = np.nan # 中间挖个洞
    
    smoothed = smooth_nan_safe(data, size=3)
    
    # 平滑后，NaN 周围的值应该还在，不会全变成 NaN
    assert not np.isnan(smoothed[0, 0])
    # 纯平滑区域应该接近原值
    assert 9.0 < smoothed[0, 0] < 11.0