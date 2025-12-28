import sys
import os
import numpy as np
import pytest

# --- Path Configuration ---
# Ensure the test script can locate modules in the 'src' directory
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, '..', 'src')
sys.path.insert(0, src_path)

# Import core algorithms
from processing import calculate_background, smooth_nan_safe, process_frame_ratio

# --- Test 1: Background Calculation ---
def test_calculate_background():
    """Verify that background subtraction correctly calculates the percentile."""
    # Create a 10x10x10 stack with all values set to 100
    stack = np.ones((10, 10, 10)) * 100
    # Place a 0 at a specific location to test robustness
    stack[0, 0, 0] = 0
    
    # 50th percentile (Median) should still be 100
    bg = calculate_background(stack, percentile=50)
    assert bg == 100.0
    
    # Test handling of empty/None input
    assert calculate_background(None, 50) == 0

# --- Test 2: NaN-safe Smoothing Algorithm (Core Feature) ---
def test_smooth_nan_safe():
    """
    Verify if the normalized convolution algorithm is truly 'NaN-safe'.
    Standard smoothing propagates NaNs; this algorithm should ignore NaNs 
    and calculate the average using only valid neighbors.
    """
    # Create a 3x3 matrix
    # 1  1  1
    # 1 NaN 1
    # 1  1  1
    arr = np.ones((3, 3))
    arr[1, 1] = np.nan
    
    # Apply smoothing with a 3x3 kernel
    smoothed = smooth_nan_safe(arr, size=3)
    
    # Key Checkpoints:
    # 1. Edge pixel (0,0) should not become NaN (standard convolution often fails at boundaries).
    assert not np.isnan(smoothed[0, 0])
    
    # 2. The central NaN position should be filled by the average of valid neighbors.
    # Logic: result = sum_data / sum_mask. 
    # Center sum_mask=8 (8 neighbors are 1), sum_data=8. Result should be 1.0.
    assert smoothed[1, 1] == 1.0 
    
    # 3. Ensure normal values remain unaffected (should be 1.0).
    assert smoothed[0, 1] == 1.0

# --- Test 3: Ratio Calculation Workflow ---
def test_process_frame_ratio():
    """Verify the complete ratio processing workflow: BG Subtract -> Ratio -> Threshold."""
    # Simulate two 10x10 images
    # Channel 1: Intensity 200, Background 10
    d1 = np.full((10, 10), 200.0)
    bg1 = 10.0
    
    # Channel 2: Intensity 100, Background 10
    d2 = np.full((10, 10), 100.0)
    bg2 = 10.0
    
    # Expected Ratio: (200-10) / (100-10) = 190 / 90 ≈ 2.111
    
    # Run function
    # int_thresh=0 (no intensity filtering), ratio_thresh=0, smooth=0
    ratio = process_frame_ratio(d1, d2, bg1, bg2, int_thresh=0, ratio_thresh=0, smooth_size=0)
    
    # Verify calculation precision
    expected_val = 190.0 / 90.0
    assert np.allclose(ratio, expected_val, atol=1e-4)

def test_ratio_zero_division():
    """Test behavior when division by zero occurs."""
    d1 = np.ones((5, 5)) * 100
    d2 = np.zeros((5, 5)) # Denominator is 0
    
    ratio = process_frame_ratio(d1, d2, 0, 0, 0, 0, 0)
    
    # Division by zero should result in NaN (or be masked)
    assert np.all(np.isnan(ratio))

def test_intensity_threshold():
    """Test intensity threshold filtering."""
    d1 = np.ones((5, 5)) * 10 # Very low intensity
    d2 = np.ones((5, 5)) * 100
    
    # Set threshold to 20; d1 is below threshold, so the result should be filtered to NaN
    ratio = process_frame_ratio(d1, d2, 0, 0, int_thresh=20, ratio_thresh=0, smooth_size=0)
    
    assert np.all(np.isnan(ratio))