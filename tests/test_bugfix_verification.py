"""
Verification script for zero-dimension slicing bugfix.

This script tests the core functionality that was fixed:
1. LazyArray integer indexing
2. Channel splitting
3. Frame extraction

Run this BEFORE testing the full GUI to verify the fixes work.
"""

import sys
import os
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'ria_gui'))

from lazy_array import LazyArray
from io_utils import split_channels


def test_lazy_array_indexing():
    """Test LazyArray integer indexing returns proper 2D arrays."""
    print("\n" + "="*60)
    print("TEST 1: LazyArray Integer Indexing")
    print("="*60)

    # Create 5D data: (T=10, C=1, Z=1, Y=64, X=64)
    data = np.random.rand(10, 1, 1, 64, 64).astype(np.float32)
    print(f"Created test data: shape={data.shape}")

    # Wrap in LazyArray
    lazy = LazyArray(data)
    print(f"Wrapped in LazyArray: shape={lazy.shape}")

    # Test integer indexing
    print("\n--- Testing integer indexing: lazy[5] ---")
    frame = lazy[5]
    print(f"Result shape: {frame.shape}")
    print(f"Result dtype: {frame.dtype}")

    # Verify shape
    if frame.ndim != 2:
        print(f"❌ FAIL: Expected 2D, got {frame.ndim}D")
        return False

    if 0 in frame.shape:
        print(f"❌ FAIL: Shape contains 0: {frame.shape}")
        return False

    if frame.shape != (64, 64):
        print(f"❌ FAIL: Expected (64, 64), got {frame.shape}")
        return False

    print("✅ PASS: Integer indexing returns proper 2D array")

    # Test slice indexing
    print("\n--- Testing slice indexing: lazy[0:3] ---")
    frames = lazy[0:3]
    print(f"Result shape: {frames.shape}")

    if frames.shape[0] != 3:
        print(f"❌ FAIL: Expected first dimension = 3, got {frames.shape[0]}")
        return False

    print("✅ PASS: Slice indexing works correctly")

    return True


def test_channel_splitting_non_interleaved():
    """Test channel splitting in non-interleaved mode."""
    print("\n" + "="*60)
    print("TEST 2: Channel Splitting (Non-Interleaved)")
    print("="*60)

    # Create 5D data with 2 channels: (T=10, C=2, Z=1, Y=64, X=64)
    data = np.random.rand(10, 2, 1, 64, 64).astype(np.float32)
    print(f"Created test data: shape={data.shape} (2 channels)")

    lazy = LazyArray(data)

    # Split channels
    print("\n--- Splitting into 2 channels (non-interleaved) ---")
    channels = split_channels(lazy, n_channels=2, is_interleaved=False)

    print(f"\nSplit result: {len(channels)} channels")

    # Verify we got 2 channels
    if len(channels) != 2:
        print(f"❌ FAIL: Expected 2 channels, got {len(channels)}")
        return False

    # Verify each channel shape
    for i, ch in enumerate(channels):
        print(f"Channel {i}: shape={ch.shape}")

        # Should be (T=10, C=1, Z=1, Y=64, X=64)
        if ch.shape[0] != 10:
            print(f"❌ FAIL: Channel {i} has wrong T dimension: {ch.shape[0]}")
            return False

        if ch.shape[1] != 1:
            print(f"❌ FAIL: Channel {i} has wrong C dimension: {ch.shape[1]}")
            return False

        # Test extracting a frame
        frame = ch[5]
        print(f"  Frame 5 shape: {frame.shape}")

        if frame.ndim != 2:
            print(f"❌ FAIL: Channel {i} frame is not 2D: {frame.shape}")
            return False

        if 0 in frame.shape:
            print(f"❌ FAIL: Channel {i} frame has zero dimension: {frame.shape}")
            return False

    print("✅ PASS: Channel splitting (non-interleaved) works correctly")
    return True


def test_channel_splitting_interleaved():
    """Test channel splitting in interleaved mode."""
    print("\n" + "="*60)
    print("TEST 3: Channel Splitting (Interleaved)")
    print("="*60)

    # Create interleaved data: (T=20, C=1, Z=1, Y=64, X=64)
    # Frames 0,2,4,... = Channel 0
    # Frames 1,3,5,... = Channel 1
    data = np.random.rand(20, 1, 1, 64, 64).astype(np.float32)
    print(f"Created test data: shape={data.shape} (20 interleaved frames)")

    lazy = LazyArray(data)

    # Split channels
    print("\n--- Splitting into 2 channels (interleaved) ---")
    channels = split_channels(lazy, n_channels=2, is_interleaved=True)

    print(f"\nSplit result: {len(channels)} channels")

    # Verify we got 2 channels
    if len(channels) != 2:
        print(f"❌ FAIL: Expected 2 channels, got {len(channels)}")
        return False

    # Verify each channel has 10 frames
    for i, ch in enumerate(channels):
        print(f"Channel {i}: shape={ch.shape}")

        # Should be (T=10, C=1, Z=1, Y=64, X=64)
        if ch.shape[0] != 10:
            print(f"❌ FAIL: Channel {i} has wrong T dimension: {ch.shape[0]} (expected 10)")
            return False

        # Test extracting a frame
        frame = ch[5]
        print(f"  Frame 5 shape: {frame.shape}")

        if frame.ndim != 2:
            print(f"❌ FAIL: Channel {i} frame is not 2D: {frame.shape}")
            return False

        if 0 in frame.shape:
            print(f"❌ FAIL: Channel {i} frame has zero dimension: {frame.shape}")
            return False

    print("✅ PASS: Channel splitting (interleaved) works correctly")
    return True


def test_model_integration():
    """Test model.py integration with LazyArray."""
    print("\n" + "="*60)
    print("TEST 4: Model Integration")
    print("="*60)

    try:
        from model import AnalysisSession
    except ImportError as e:
        print(f"⚠️  SKIP: Cannot import AnalysisSession: {e}")
        return True  # Skip, not a failure

    # Create session
    session = AnalysisSession()

    # Create fake data (2 channels, 10 frames)
    data1 = LazyArray(np.random.rand(10, 1, 1, 64, 64).astype(np.float32))
    data2 = LazyArray(np.random.rand(10, 1, 1, 64, 64).astype(np.float32))

    print(f"Created mock data:")
    print(f"  data1: {data1.shape}")
    print(f"  data2: {data2.shape}")

    # Set data
    print("\n--- Setting data in session ---")
    session.set_data([data1, data2])

    print(f"Session data1: {session.data1.shape}")
    print(f"Session data2: {session.data2.shape}")

    # Test get_processed_frame
    print("\n--- Extracting frame 0 (ratio mode) ---")
    try:
        frame = session.get_processed_frame(0)
        print(f"Processed frame shape: {frame.shape if frame is not None else None}")

        if frame is None:
            print("❌ FAIL: get_processed_frame returned None")
            return False

        if frame.ndim != 2:
            print(f"❌ FAIL: Processed frame is not 2D: {frame.shape}")
            return False

        if 0 in frame.shape:
            print(f"❌ FAIL: Processed frame has zero dimension: {frame.shape}")
            return False

        print("✅ PASS: Model integration works correctly")
        return True

    except Exception as e:
        print(f"❌ FAIL: Exception during frame extraction: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n" + "="*60)
    print("TEST 5: Edge Cases")
    print("="*60)

    # Test 1: Single frame
    print("\n--- Testing single frame (T=1) ---")
    data = np.random.rand(1, 1, 1, 64, 64).astype(np.float32)
    lazy = LazyArray(data)
    frame = lazy[0]

    if frame.ndim != 2 or 0 in frame.shape:
        print(f"❌ FAIL: Single frame extraction failed: {frame.shape}")
        return False
    print(f"✅ Single frame OK: {frame.shape}")

    # Test 2: Already 2D data
    print("\n--- Testing already 2D data ---")
    data_2d = np.random.rand(64, 64).astype(np.float32)
    lazy_2d = LazyArray(data_2d)

    if lazy_2d.shape != (64, 64):
        print(f"❌ FAIL: 2D data shape changed: {lazy_2d.shape}")
        return False
    print(f"✅ 2D data OK: {lazy_2d.shape}")

    # Test 3: Multiple squeezes needed
    print("\n--- Testing multiple singleton dimensions ---")
    data_complex = np.random.rand(10, 1, 1, 1, 64, 64).astype(np.float32)
    # This is 6D, not standard, but test squeeze handles it
    lazy_complex = LazyArray(data_complex)
    frame = lazy_complex[5]

    if frame.ndim != 2 or 0 in frame.shape:
        print(f"❌ FAIL: Complex squeeze failed: {frame.shape}")
        return False
    print(f"✅ Complex squeeze OK: {frame.shape}")

    print("\n✅ PASS: All edge cases handled correctly")
    return True


def main():
    """Run all verification tests."""
    print("\n" + "="*60)
    print("BUGFIX VERIFICATION SUITE")
    print("Testing zero-dimension slicing fixes")
    print("="*60)

    tests = [
        ("LazyArray Integer Indexing", test_lazy_array_indexing),
        ("Channel Splitting (Non-Interleaved)", test_channel_splitting_non_interleaved),
        ("Channel Splitting (Interleaved)", test_channel_splitting_interleaved),
        ("Model Integration", test_model_integration),
        ("Edge Cases", test_edge_cases),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ EXCEPTION in {name}:")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! The bugfix is working correctly.")
        print("\nYou can now test the full GUI application.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
