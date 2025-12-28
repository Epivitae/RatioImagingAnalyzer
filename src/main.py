import sys
import os
import tkinter as tk
import ctypes

# Add current directory to system path to ensure sibling modules are found
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Attempt to import core modules
try:
    # Try sibling import first
    from gui import RatioAnalyzerApp
    from _version import __version__
except ImportError:
    # Fallback for package context
    try:
        from src.gui import RatioAnalyzerApp
        from src._version import __version__
    except ImportError as e:
        print(f"Error importing core modules: {e}")
        raise

def main():
    print(f"Starting Ratio Imaging Analyzer {__version__}...")
    
    # Tell Windows this is a distinct application (fixes Taskbar icon issue)
    try:
        # Unique AppID format: Company.Product.SubProduct.Version
        myappid = f'epivitae.ratioimaginganalyzer.ria.{__version__}.v3'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        print(f"Warning: Could not set AppUserModelID: {e}")

    root = tk.Tk()
    app = RatioAnalyzerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()