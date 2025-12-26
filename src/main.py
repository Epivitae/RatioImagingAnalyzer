import tkinter as tk

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