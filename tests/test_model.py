# tests/test_model.py
import numpy as np
# CHANGE THIS LINE: add .ria_gui
from src.ria_gui.model import AnalysisSession

def test_session_workflow(synthetic_data_2ch):
    d1, d2 = synthetic_data_2ch
    session = AnalysisSession()
    session.set_data([d1, d2], roles={"num": 0, "den": 1})
    
    assert session.data1 is not None
    assert session.data1.shape[0] == 5
    
    session.bg_percent = 10
    session.recalc_background()
    assert session.cached_bg1 > 0
    
    processed = session.get_processed_frame(0, 0, 0, 0, False)
    assert processed.shape == (100, 100)
    assert processed.dtype == np.float32
    
    session.set_data([d1])
    assert session.view_mode == "ratio"
    frame_single = session.get_processed_frame(0)
    assert not np.any(np.isnan(frame_single))