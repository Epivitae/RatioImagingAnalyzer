import sys
import os
import tkinter as tk
import ctypes

def print_welcome_art():
    """
    Prints the startup ASCII art banner for RIA (Liya).
    """
    # 修正：使用 r''' (三个单引号) 包裹，因为字符画内部含有 """ (三个双引号)
    banner = r'''
         _,addba,
         _,adP"'\  "Y,                       _____
       ,P"  d"Y,  \  8                  ,adP"""""""Yba,_
     ,d" /,d' `Yb, ,P'              ,adP"'           `""Yba,
     d'   d'    `"""         _,aadP"""""""Ya,             `"Ya,_
     8  | 8              _,adP"'                              `"Ya,
     8    I,           ,dP"           __              "baa,       "Yb,
     I,   Ya         ,db___           `"Yb,      a       `"         `"b,
     `Y, \ Y,      ,d8888888baa8a,_      `"      `"b,                 `"b,
      `Ya, `b,    d8888888888888888b,               "ba,                `8,
        "Ya,`b  ,d8888888888888888888,   d,           `"Ya,_             `Y,
          `Ybd8d8888888888888888888888b, `"Ya,            `""Yba,         `8,
             "Y8888888888888888888888888,   `Yb,               `"Ya        `b
              d8888888888888888888888888b,    `"'            ,    "b,       8,
              888888888888888888888888888b,                  b      "b      `b
              8888888888888888888888888888b    b,_           8       "       8
              I8888888888888888888888888888,    `"Yb,_       `b,             8
               Y888888888888888888888888888I        `Yb,       8,            8
                `Y8888888888888888888888888(          `8,       "b     a    ,P
                  "8888""Y88888888888888888I           `b,       `b    8    d'
                    "Y8b,  "Y888PPY8888888P'            `8,       P    8    8
                        `b   "'  __ `"Y88P'    b,        `Y       "    8    8
                       ""|      =""Y'   d'     `b,                     8    8
                        /         "' |  I       b             ,       ,P   ,P
                       (          _,"  d'       Y,           ,P       "    d'
                        |              I        `b,          d'            8
                        |              I          "         d,d'           8
                        |          ;   `b                  dP"          __,8_
                        |          |    `b                d"     _,,add8888888
                        ",       ,"      `b              d' _,ad88888888888888
                          \,__,a"          ",          _,add888888888888888888
                         _,aa888b           I       ,ad88888888888888888888888
                     _,ad88888888a___,,,gggd8,   ,ad88888888888888888888888888
                  ,ad888888888888b88PP""''  Y  ,dd8888888888888888888888888888
               ,ad8888888888888888'         `bd8888888888888888888888888888888
             ,d88888888888888888P'         ,d888888888888888888888888888888888
           ,d888888888888888888"         ,d88888888888888888888888888888888888
         ,d8888888888888888888P        ,d8888888888888888888888888888888888888
       ,d888888888888888888888b,     ,d888888888888888888888888888888888888888
      ,8888888888888888888888888888=888888888888888888888888888888888888888888
     d888888888888888888888888888=88888888888888888888888888888888888888888888
    d88888888888888888888888888=8888888888888888888888888888888888888888888888
   d8888888888888888888888888=888888888888888888888888888888888888888888888888
  d888888888888888888888888=88888888888888888888888888888888888888888888888888
 ,888888888888888888888888=888888888888888888888888888888888888888888888888888
 d8888888888888888888888=88888888888888888888888888888888888888888888888888888
,8888888888888888888888=888888888888888888888888888888888888888888888888888888
d888888888888888888888=88888888888888888888888888888888888888888 RIA (Liya) 88
888888888888888888888=888888888888888888888888888888888888888888 by Dr.Wang 88
888888888888888888888=88888888888888888888888888888888888888888888888888888888
    '''
    print(banner)
    print("                   RIA (Liya) says: Welcome!")
    print("----------------------------------------------------------------------\n")

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
    # 1. Print the welcome banner first
    print_welcome_art()    
    print(f"Starting Ratio Imaging Analyzer {__version__}...")
    
    # Tell Windows this is a distinct application (fixes Taskbar icon issue)
    try:
        # Unique AppID format: Company.Product.SubProduct.Version
        myappid = f'epivitae.ratioimaginganalyzer.ria.{__version__}.v3'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        print(f"Warning: Could not set AppUserModelID: {e}")

    root = tk.Tk()

    # [修改重点] 1. 增强的文件检测逻辑
    startup_file = None
    if len(sys.argv) > 1:
        # 获取传入的参数
        candidate = sys.argv[1]
        
        # 处理可能存在的引号包裹 (虽然 shell 通常会处理，但为了保险)
        candidate = candidate.strip('"').strip("'")
        
        # 转换为绝对路径，防止工作目录不一致导致找不到文件
        candidate = os.path.abspath(candidate)
        
        if os.path.exists(candidate):
            startup_file = candidate
            print(f"Startup file detected: {startup_file}")
        else:
            print(f"Warning: Argument passed but file not found: {candidate}")

    # [修改重点] 2. 将 startup_file 传给 App
    app = RatioAnalyzerApp(root, startup_file=startup_file)
    root.mainloop()

if __name__ == "__main__":
    main()