import sys
import os
import pytest

# --- Path Configuration ---
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, '..', 'src')
sys.path.insert(0, src_path)

# Attempt to import version string and main application class
from _version import __version__
from gui import RatioAnalyzerApp

def test_version_exists():
    """Verify that the version string exists and is valid."""
    assert isinstance(__version__, str)
    assert len(__version__) > 0

def test_gui_class_importable():
    """
    Verify that the GUI class is importable.
    This checks for syntax errors and dependency issues without instantiating the UI.
    """
    # We do not instantiate RatioAnalyzerApp(root) here because it requires 
    # an active Tkinter window/display, which might fail in headless CI/CD environments.
    # Successful import implies no basic syntax errors in gui.py.
    assert RatioAnalyzerApp is not None