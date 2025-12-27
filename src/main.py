import sys
import os
import tkinter as tk

# 将当前目录添加到系统路径，确保能找到同级模块
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# 尝试直接导入
try:
    from gui import RatioAnalyzerApp
except ImportError:
    # 如果失败，尝试作为包导入（通常在打包环境下不应该走到这里，但为了保险）
    try:
        from src.gui import RatioAnalyzerApp
    except ImportError as e:
        # 如果还不行，打印详细错误并抛出
        print(f"Error importing GUI: {e}")
        raise

def main():
    root = tk.Tk()
    app = RatioAnalyzerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()