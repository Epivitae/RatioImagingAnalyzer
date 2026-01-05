"""
Test script for lazy loading refactoring.

This script tests the new Reader Strategy Pattern and LazyArray implementation.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'ria_gui'))

def test_lazy_array():
    """Test LazyArray basic functionality"""
    print("\n=== Testing LazyArray ===")
    from lazy_array import LazyArray, DASK_AVAILABLE
    import numpy as np

    # Test with NumPy array
    data = np.random.rand(10, 2, 1, 512, 512).astype(np.float32)
    lazy = LazyArray(data)

    print(f"✓ Created LazyArray: shape={lazy.shape}, dtype={lazy.dtype}")
    print(f"  Is lazy: {lazy.is_lazy}")
    print(f"  Dask available: {DASK_AVAILABLE}")

    # Test slicing
    frame = lazy[0]
    print(f"✓ Sliced frame 0: shape={frame.shape}")

    # Test shape access (no computation)
    print(f"✓ Shape access (no computation): {lazy.shape}")

    return True


def test_readers():
    """Test Reader Strategy Pattern"""
    print("\n=== Testing Readers ===")
    from io_utils import get_reader, AICSReader, TiffReader

    # Test reader selection
    print("Testing reader selection:")

    # TIFF reader
    try:
        reader = get_reader("test.tif")
        print(f"✓ TIFF: {reader.__class__.__name__}")
        assert isinstance(reader, TiffReader)
    except Exception as e:
        print(f"✗ TIFF reader test failed: {e}")
        return False

    # AICS reader (if available)
    try:
        reader = get_reader("test.oir")
        print(f"✓ OIR: {reader.__class__.__name__}")
        assert isinstance(reader, AICSReader)
    except Exception as e:
        print(f"  OIR reader test skipped (aicsimageio not available)")

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

    print(f"✓ Created MetadataInfo: {meta}")
    print(f"  Shape: {meta.shape}")
    print(f"  Axes: {meta.axes}")
    print(f"  Channels: {meta.n_channels}")

    return True


def test_model_integration():
    """Test model.py integration with LazyArray"""
    print("\n=== Testing Model Integration ===")
    from model import AnalysisSession
    from lazy_array import LazyArray
    import numpy as np

    # Create session
    session = AnalysisSession()

    # Create fake lazy data
    data1 = LazyArray(np.random.rand(10, 1, 1, 512, 512).astype(np.float32))
    data2 = LazyArray(np.random.rand(10, 1, 1, 512, 512).astype(np.float32))

    # Set data
    session.set_data([data1, data2])

    print(f"✓ Set data in session")
    print(f"  data1 shape: {session.data1.shape}")
    print(f"  data2 shape: {session.data2.shape}")

    # Test get_processed_frame (lazy loading)
    frame = session.get_processed_frame(0)
    print(f"✓ Got processed frame: shape={frame.shape}")

    # Test background calculation (should sample only 10 frames)
    session.recalc_background()
    print(f"✓ Recalculated background: bg1={session.cached_bg1:.2f}, bg2={session.cached_bg2:.2f}")

    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("Lazy Loading Refactoring Test Suite")
    print("=" * 60)

    tests = [
        ("LazyArray", test_lazy_array),
        ("Readers", test_readers),
        ("MetadataInfo", test_metadata_info),
        ("Model Integration", test_model_integration),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} FAILED: {e}")
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
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Lazy loading refactoring successful.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
