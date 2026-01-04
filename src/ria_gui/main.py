import sys
import os
import tkinter as tk
import ctypes
import argparse
import platform
import tifffile
import json       # [新增] 用于处理配置文件
import logging    # [新增] 用于调试日志

def print_welcome_art():
    """
    Prints the startup ASCII art banner for RIA (Liya).
    """
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

# Add current directory to system path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Import core modules
try:
    from gui import RatioAnalyzerApp
    from _version import __version__
except ImportError:
    try:
        from src.gui import RatioAnalyzerApp
        from src._version import __version__
    except ImportError as e:
        print(f"Error importing core modules: {e}")
        raise

# ==========================================
# [新增] 功能处理函数
# ==========================================

def handle_init_config():
    """
    生成默认配置文件 ria_config.json。
    这允许用户在不修改代码的情况下自定义启动参数。
    """
    config_path = os.path.join(os.getcwd(), "ria_config.json")
    
    if os.path.exists(config_path):
        print(f"ℹ️  Config file already exists: {config_path}")
        print("   (Delete it first if you want to regenerate defaults)")
        sys.exit(0)

    # 定义默认配置结构
    default_config = {
        "version": __version__,
        "processing": {
            "default_int_threshold": 0,
            "default_ratio_threshold": 0.0,
            "default_smooth_size": 0,
            "bg_subtraction_percent": 5.0
        },
        "display": {
            "default_colormap": "coolwarm",
            "default_bg_color": "Trans",
            "default_fps": 10
        },
        "paths": {
            "auto_load_last_project": False,
            "default_export_dir": "./output"
        }
    }

    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)
        print(f"✅ Generated default config file: {config_path}")
        print("   You can now edit this file to customize RIA startup behavior.")
    except Exception as e:
        print(f"❌ Failed to create config file: {e}")
    
    sys.exit(0)

def handle_sysinfo():
    """打印系统环境信息，用于调试"""
    print("\n=== RIA System Info ===")
    print(f"RIA Version:   {__version__}")
    print(f"Python:        {sys.version.split()[0]} ({platform.architecture()[0]})")
    print(f"OS:            {platform.system()} {platform.release()}")
    
    try:
        import numpy
        print(f"NumPy:         {numpy.__version__}")
    except ImportError:
        print("NumPy:         Not Installed")
        
    try:
        import cv2
        print(f"OpenCV:        {cv2.__version__}")
    except ImportError:
        print("OpenCV:        Not Installed (Alignment disabled)")

    try:
        import matplotlib
        print(f"Matplotlib:    {matplotlib.__version__}")
    except ImportError:
        print("Matplotlib:    Not Installed")
        
    print("=======================\n")
    sys.exit(0)

def handle_file_info(filepath):
    """快速读取 Tiff 文件头信息而不加载整个文件"""
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    print(f"\nScanning: {filepath} ...")
    try:
        with tifffile.TiffFile(filepath) as tif:
            series = tif.series[0]
            shape = series.shape
            dtype = series.dtype
            axes = series.axes
            
            ij_meta = tif.imagej_metadata
            channels = 1
            frames = 1
            slices = 1
            if ij_meta:
                channels = ij_meta.get('channels', 1)
                slices = ij_meta.get('slices', 1)
                frames = ij_meta.get('frames', 1)
            
            print(f"--- File Metadata ---")
            print(f"Dimensions:         {shape}")
            print(f"Data Type:          {dtype}")
            print(f"Axes:               {axes}")
            if ij_meta:
                print(f"ImageJ Metadata:    T={frames}, Z={slices}, C={channels}")
            
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            print(f"File Size:          {size_mb:.2f} MB")
            print("---------------------\n")
            
    except Exception as e:
        print(f"Error reading file metadata: {e}")
    
    sys.exit(0)

# ==========================================
# Main
# ==========================================

def main():
    parser = argparse.ArgumentParser(
        description="RIA (Ratio Imaging Analyzer): A tool for ratiometric imaging analysis.",
        prog="ria"
    )

    # 1. 版本
    parser.add_argument('-v', '--version', action='version', version=f'RIA {__version__}', help="Show version.")

    # 2. 系统信息
    parser.add_argument('-s', '--sysinfo', action='store_true', help="Show system dependencies and environment info.")

    # 3. 文件信息
    parser.add_argument('-i', '--info', metavar='FILE', help="Inspect a Tiff file's metadata without opening GUI.")

    # 4. [新增] 调试模式
    parser.add_argument('-d', '--debug', action='store_true', help="Enable debug mode with verbose logging.")

    # 5. [新增] 初始化配置
    parser.add_argument('-ini', '--init', action='store_true', help="Generate default configuration file (ria_config.json).")

    # 6. 启动文件
    parser.add_argument('filename', nargs='?', help="Path to image/project to open.")

    args = parser.parse_args()

    # --- 1. 处理日志配置 (最先执行) ---
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        logging.debug("🔧 Debug Mode Enabled")
        logging.debug(f"Arguments parsed: {args}")
    else:
        # 默认只显示警告及以上
        logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

    # --- 2. 处理功能指令 ---
    if args.sysinfo:
        handle_sysinfo()

    if args.init:
        handle_init_config()

    if args.info:
        handle_file_info(args.info)

    # --- 3. 启动 GUI ---
    print_welcome_art()
    print(f"Starting Ratio Imaging Analyzer {__version__}...")

    if os.name == 'nt':
        try:
            myappid = f'epivitae.ratioimaginganalyzer.ria.{__version__}.v3'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            logging.warning(f"Could not set AppUserModelID: {e}")

    root = tk.Tk()

    startup_file = None
    if args.filename:
        candidate = os.path.abspath(args.filename)
        if os.path.exists(candidate):
            startup_file = candidate
            print(f"Startup file detected: {startup_file}")
            logging.debug(f"Startup file found: {startup_file}")
        else:
            print(f"Warning: File provided but not found: {candidate}")
            logging.warning(f"File not found: {candidate}")

    # 启动应用
    try:
        app = RatioAnalyzerApp(root, startup_file=startup_file)
        root.mainloop()
    except Exception as e:
        logging.critical(f"Unhandled exception in Main Loop: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()