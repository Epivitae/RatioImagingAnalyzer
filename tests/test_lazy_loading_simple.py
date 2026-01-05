"""
Simple test script for lazy loading refactoring (without Dask dependency).

This script tests the basic functionality without requiring Dask to be installed.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'ria_gui'))

def test_lazy_array_basic():
    """Test LazyArray basic functionality without Dask"""
    print("\n=== Testing LazyArray (Basic) ===")
    from lazy_array import LazyArray
    import numpy as np

    # Test with NumPy array (eager mode)
    data = np.random.rand(10, 2, 1, 512, 512).astype(np.float32)
    lazy = LazyArray(data)

    print(f"[OK] Created LazyArray: shape={lazy.shape}, dtype={lazy.dtype}")
    print(f"     Is lazy: {lazy.is_lazy}")

    # Test slicing
    frame = lazy[0]
    print(f"[OK] Sliced frame 0: shape={frame.shape}")

    # Test shape access (no computation)
    print(f"[OK] Shape access (no computation): {lazy.shape}")

    return True


def test_readers_basic():
    """Test Reader Strategy Pattern"""
    print("\n=== Testing Readers ===")
    from io_utils import get_reader, TiffReader

    # Test reader selection for TIFF
    try:
        reader = get_reader("test.tif")
        print(f"[OK] TIFF reader selected: {reader.__class__.__name__}")
        assert isinstance(reader, TiffReader)
    except Exception as e:
        print(f"[FAIL] TIFF reader test failed: {e}")
        return False

    return True


def test_metadata_info():
    """Test MetadataInfo class"""
    print("\n=== Testing MetadataInfo ===")
    from lazy_array import MetadataInfo
    import numpy as np

    meta = MetadataInfo(
        shape=(100, 2, 1, 512, 512),
        dtype=np.float32,
        axes="TCZYX",
        n_channels=2,
        n_z=1,
        n_timepoints=100,
        is_explicit_multichannel=True
    )

    print(f"[OK] Created MetadataInfo: {meta}")
    print(f"     Shape: {meta.shape}")
    print(f"     Axes: {meta.axes}")
    print(f"     Channels: {meta.n_channels}")

    return True


def test_model_integration():
    """Test model.py integration with LazyArray"""
    print("\n=== Testing Model Integration ===")
    from model import AnalysisSession
    from lazy_array import LazyArray
    import numpy as np

    # Create session
    session = AnalysisSession()

    # Create fake lazy data (small size for testing)
    data1 = LazyArray(np.random.rand(10, 1, 1, 64, 64).astype(np.float32))
    data2 = LazyArray(np.random.rand(10, 1, 1, 64, 64).astype(np.float32))

    # Set data
    session.set_data([data1, data2])

    print(f"[OK] Set data in session")
    print(f"     data1 shape: {session.data1.shape}")
    print(f"     data2 shape: {session.data2.shape}")

    # Test get_processed_frame (lazy loading)
    frame = session.get_processed_frame(0)
    print(f"[OK] Got processed frame: shape={frame.shape}")

    # Test background calculation (should sample only 10 frames)
    session.recalc_background()
    print(f"[OK] Recalculated background: bg1={session.cached_bg1:.2f}, bg2={session.cached_bg2:.2f}")

    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("Lazy Loading Refactoring Test Suite (Basic)")
    print("=" * 60)

    tests = [
        ("LazyArray", test_lazy_array_basic),
        ("Readers", test_readers_basic),
        ("MetadataInfo", test_metadata_info),
        ("Model Integration", test_model_integration),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\nAll tests passed! Lazy loading refactoring successful.")
        return 0
    else:
        print("\nSome tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
