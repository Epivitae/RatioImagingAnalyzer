import tkinter as tk
import sys
import os

# 确保能找到当前目录下的模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from gui import RatioAnalyzerApp
except ImportError:
    from .gui import RatioAnalyzerApp

def main():
    root = tk.Tk()
    # 可以设置默认图标等
    # root.iconbitmap('icon.ico') 
    app = RatioAnalyzerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()