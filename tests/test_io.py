# tests/test_io.py
import numpy as np
# CHANGE THIS LINE: add .ria_gui
from src.ria_gui.io_utils import read_ria_tiff_smart, UnifiedData, save_ria_tiff

def test_read_standard_tiff(temp_tiff_file):
    result = read_ria_tiff_smart(temp_tiff_file)
    assert isinstance(result, UnifiedData)
    assert result.data.ndim == 5
    assert result.data.shape == (5, 2, 1, 100, 100)
    assert result.axes == "TCZYX"

def test_save_and_load_ria_format(tmp_path):
    data = np.random.rand(3, 2, 1, 50, 50).astype(np.float32)
    path = tmp_path / "ria_export.tif"
    params = {"int_thresh": 50, "test_tag": "true"}
    save_ria_tiff(path, data, channel_names=["R", "G"], params=params)
    
    loaded = read_ria_tiff_smart(str(path))
    assert loaded is not None
    assert loaded.metadata['is_ria_processed'] is True
    assert loaded.metadata['processing_params']['int_thresh'] == 50