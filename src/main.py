import tkinter as tk
# 确保在 src 目录下运行时能找到 gui
try:
    from gui import RatioAnalyzerApp
except ImportError:
    from .gui import RatioAnalyzerApp

def main():
    root = tk.Tk()
    app = RatioAnalyzerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()