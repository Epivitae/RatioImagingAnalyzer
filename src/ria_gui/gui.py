import tkinter as tk
from tkinter import filedialog, messagebox, ttk, Toplevel
import tkinter.font as tkfont
import numpy as np
import tifffile as tiff
import os
import sys
import warnings
import datetime
import threading
import requests
import webbrowser

# --- Import Components ---
try:
    from .constants import LANG_MAP
    from .components import ToggledFrame
    from .io_utils import read_and_split_multichannel, read_separate_files, read_and_split_dual_channel
    from .gui_components import PlotManager, RoiManager 
except ImportError:
    try:
        from constants import LANG_MAP
        from components import ToggledFrame
        from io_utils import read_and_split_multichannel, read_separate_files, read_and_split_dual_channel
        from gui_components import PlotManager, RoiManager
    except ImportError as e:
        print(f"Import Error: {e}. Ensure all modules exist.")

# --- Import Processing ---
try:
    from .processing import calculate_background, process_frame_ratio, align_stack_ecc
except ImportError:
    try:
        from processing import calculate_background, process_frame_ratio, align_stack_ecc
    except ImportError as e:
        print(f"CRITICAL ERROR: Failed to import processing module. Reason: {e}")
        raise e 

try:
    from ._version import __version__
except ImportError:
    try:
        from _version import __version__
    except:
        __version__ = "1.0.0"

warnings.filterwarnings('ignore')

class RatioAnalyzerApp:
    def __init__(self, root):
        self.root = root
        
        # --- Font Init ---
        self.base_font_size = 10
        self.current_font_size = self.base_font_size
        self.f_normal = tkfont.Font(family="Segoe UI", size=self.base_font_size)
        self.f_bold = tkfont.Font(family="Segoe UI", size=self.base_font_size, weight="bold")
        self.f_title = tkfont.Font(family="Helvetica", size=self.base_font_size + 8, weight="bold")
        
        self.default_tk_font = tkfont.nametofont("TkDefaultFont")
        self._resize_timer = None

        # --- Theme ---
        self.setup_theme()
        
        self.VERSION = __version__
        self.current_lang = "en"
        self.ui_elements = {}
        self.root.geometry("1080x990")
        self.root.configure(bg="#F0F2F5") 
        self.root.minsize(1000, 900)
        
        try:
            icon_path = self.get_asset_path("ratiofish.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(default=icon_path) 
        except Exception as e:
            print(f"Warning: Failed to load icon: {e}")

        # --- Managers ---
        self.plot_mgr = None 
        self.roi_mgr = RoiManager(self)

        # Data Objects
        self.data1 = None      # Numerator (or Ch1)
        self.data2 = None      # Denominator (or Ch2)
        self.data_aux = []     # List of extra channels (Ch3, Ch4...)
        
        self.data1_raw = None
        self.data2_raw = None 

        self.cached_bg1 = 0
        self.cached_bg2 = 0
        self.cached_bg_aux = [] # Backgrounds for aux channels
        
        # [NEW] Custom Background ROI Variables
        self.custom_bg1 = 0.0
        self.custom_bg2 = 0.0
        self.use_custom_bg_var = tk.BooleanVar(value=False)

        # Paths
        self.c1_path = None; self.c2_path = None
        self.dual_path = None
        
        # Mitichannel view
        self.view_mode = "ratio" # ratio, ch1, ch2, aux_0...
        self.channel_buttons = [] 

        self.is_playing = False; self.fps = 10 
        self.is_interleaved_var = tk.BooleanVar(value=False)

        self.setup_ui_skeleton()
        self.setup_shortcuts()
        self.update_language()
        self.change_font_size(0)
        
        self.root.after(100, self.load_graphics_engine)


    def setup_shortcuts(self):
        # ROI Drawing Shortcuts
        self.root.bind("<Control-t>", lambda event: self.roi_mgr.start_drawing())
        self.root.bind("<Control-T>", lambda event: self.roi_mgr.start_drawing())
        self.root.bind("<Escape>", lambda event: self.roi_mgr.cancel_drawing())
        
        # Plot Curve Shortcut (Ctrl+P)
        self.root.bind("<Control-p>", lambda event: self.plot_roi_curve())
        self.root.bind("<Control-P>", lambda event: self.plot_roi_curve())

        # [NEW] Live Monitor Shortcut (Ctrl+L)
        # 使用 invoke() 模拟点击，自动处理变量切换和回调执行
        self.root.bind("<Control-l>", lambda event: self.chk_live.invoke())
        self.root.bind("<Control-L>", lambda event: self.chk_live.invoke())

    def thread_safe_config(self, widget, **kwargs):
        try:
            self.root.after(0, lambda: widget.config(**kwargs))
        except Exception as e:
            print(f"UI Update Error: {e}")

    def setup_theme(self):
        style = ttk.Style()
        try: style.theme_use('clam')
        except: pass
        
        BG_COLOR = "#F0F2F5"
        CARD_COLOR = "#FFFFFF"
        TEXT_COLOR = "#333333"
        BLUE_COLOR = "#0056b3"
        GREEN_COLOR = "#28a745"
        
        style.configure(".", background=BG_COLOR, foreground=TEXT_COLOR, font=self.f_normal)
        style.configure("TLabel", background=BG_COLOR, font=self.f_normal)
        style.configure("TButton", padding=5, font=self.f_normal) 
        style.configure("TCheckbutton", font=self.f_normal)
        style.configure("TRadiobutton", font=self.f_normal)
        style.configure("TEntry", font=self.f_normal, padding=2)
        style.configure("TCombobox", font=self.f_normal, padding=2)
        style.configure("TSpinbox", font=self.f_normal, padding=2)
        
        style.configure("Card.TFrame", background=CARD_COLOR, relief="flat")
        style.configure("Card.TLabelframe", background=CARD_COLOR, relief="solid", borderwidth=1)
        style.configure("Card.TLabelframe.Label", background=CARD_COLOR, foreground=BLUE_COLOR, font=self.f_bold)
        style.configure("Header.TFrame", background=CARD_COLOR)
        style.configure("White.TLabel", background=CARD_COLOR, font=self.f_normal)
        style.configure("White.TCheckbutton", background=CARD_COLOR, font=self.f_normal)
        style.configure("White.TRadiobutton", background=CARD_COLOR, font=self.f_normal)
        style.configure("White.TFrame", background=CARD_COLOR)
        style.configure("Blue.TLabel", foreground=BLUE_COLOR, font=self.f_bold)
        
        style.configure("Toggle.TButton", font=self.f_normal, background="#FFFFFF", borderwidth=1, padding=5)
        style.map("Toggle.TButton", background=[("selected", "#E8F0FE"), ("active", "#F5F5F5")], foreground=[("selected", BLUE_COLOR)], relief=[("selected", "sunken"), ("!selected", "raised")])
        style.configure("Starred.TButton", font=self.f_normal, foreground="#F5C518")
        style.configure("Compact.TButton", font=self.f_normal, padding=5, width=3) 
        style.configure("Gray.TButton", font=self.f_normal, background="#E0E0E0", foreground="#555555")
        style.configure("Success.TButton", font=self.f_bold, foreground="#28a745") 
        style.configure("Toolbutton", background=CARD_COLOR, relief="flat", borderwidth=0, padding=4)
        style.map("Toolbutton", background=[("selected", "#E8F0FE")], relief=[("selected", "sunken")])
        
        style.configure(
            "BadgeBlue.TLabel", 
            background=BLUE_COLOR, 
            foreground="white", 
            font=("Segoe UI", 9, "bold"),
            padding=(8, 2)  
        )

        style.configure(
            "BadgeGreen.TLabel", 
            background=GREEN_COLOR, 
            foreground="white", 
            font=("Segoe UI", 9, "bold"),
            padding=(8, 2)
        )

        self.style = style

    def get_asset_path(self, filename):
        if hasattr(sys, '_MEIPASS'):
            path = os.path.join(sys._MEIPASS, "assets", filename)
        else:
            curr_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(curr_dir, "assets", filename)
        if not os.path.exists(path):
            print(f"DEBUG: Resource not found at {path}")
        return path

    def t(self, key):
        if key not in LANG_MAP: return key
        return LANG_MAP[key][self.current_lang]

    def toggle_language(self):
        self.current_lang = "en" if self.current_lang == "cn" else "cn"
        self.update_language()

    def update_language(self):
        self.root.title(self.t("window_title").format(self.VERSION))
        self.lbl_title.config(text=self.t("header_title"))
        for key, widget in self.ui_elements.items():
            try:
                if callable(widget): 
                    widget(self.t(key))
                else:
                    widget.config(text=self.t(key))
            except: pass
        if self.c1_path is None: self.lbl_c1_path.config(text=self.t("lbl_no_file"))
        if self.c2_path is None: self.lbl_c2_path.config(text=self.t("lbl_no_file"))
        if self.dual_path is None: self.lbl_dual_path.config(text=self.t("lbl_no_file"))
        
        if hasattr(self, 'combo_mode'):
            self.update_mode_options()

    def change_font_size(self, delta):
        new_size = self.current_font_size + delta
        if new_size < 8: new_size = 8
        if new_size > 24: new_size = 24
        self.current_font_size = new_size
        self.f_normal.configure(size=new_size)
        self.f_bold.configure(size=new_size)
        self.f_title.configure(size=new_size + 8)
        self.default_tk_font.configure(size=new_size)
        self.style.configure(".", font=self.f_normal)
        self.root.update_idletasks()

    def reset_font_size(self):
        delta = self.base_font_size - self.current_font_size
        self.change_font_size(delta)

    def on_canvas_configure(self, event):
        if self._resize_timer is not None:
            self.root.after_cancel(self._resize_timer)
        self._resize_timer = self.root.after(50, lambda: self.plot_mgr.resize(event))

    def star_github(self):
        webbrowser.open("https://github.com/Epivitae/RatioImagingAnalyzer")
        self.btn_github.config(text="★ GitHub", style="Starred.TButton")

    def setup_ui_skeleton(self):
        header = ttk.Frame(self.root, padding="15 10", style="Header.TFrame")
        header.pack(fill="x")
        self.lbl_title = ttk.Label(header, text="RIA", font=self.f_title, background="#FFFFFF", foreground="#2c3e50")
        self.lbl_title.pack(side="left")
        self.ui_elements["header_title"] = self.lbl_title
        btn_frame = ttk.Frame(header, style="Header.TFrame"); btn_frame.pack(side="right")
        ttk.Button(btn_frame, text="A+", width=3, command=lambda: self.change_font_size(1)).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="⟳", width=3, command=self.reset_font_size).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="A-", width=3, command=lambda: self.change_font_size(-1)).pack(side="right", padx=2)
        self.btn_github = ttk.Button(btn_frame, text="☆ GitHub", command=self.star_github)
        self.btn_github.pack(side="right", padx=10)
        ttk.Button(btn_frame, text="🌐 EN/中文", command=self.toggle_language).pack(side="right", padx=2)
        
        self.main_pane = ttk.PanedWindow(self.root, orient="horizontal")
        self.main_pane.pack(fill="both", expand=True, padx=10, pady=10)

        self.frame_left_container = ttk.Frame(self.main_pane, style="Card.TFrame", padding=10)
        self.main_pane.add(self.frame_left_container, weight=0)
        
        self.frame_left = ttk.Frame(self.frame_left_container, width=320, style="White.TFrame")
        self.frame_left.pack(fill="both", expand=True)

        self.setup_file_group()      # 1. File Loading
        self.setup_preprocess_group()# 2. Image Registration
        self.setup_calc_group()      # 3. Calibration
        self.setup_view_group()      # 4. Display Settings
        self.setup_brand_logo()

        self.frame_right = ttk.Frame(self.main_pane, style="Card.TFrame", padding=10)
        self.main_pane.add(self.frame_right, weight=1)

        # [新增] 通道选择栏 (Channel Bar) - 放在 Plot Container 上方
        self.frame_channels = ttk.Frame(self.frame_right, style="White.TFrame")
        self.frame_channels.pack(side="top", fill="x", pady=(0, 5))

        self.plot_container = ttk.Frame(self.frame_right, style="White.TFrame")
        self.plot_container.pack(side="top", fill="both", expand=True)
        
        self.lbl_loading = ttk.Label(self.plot_container, text="Initializing Graphics Engine...", font=("Segoe UI", 12), foreground="gray", style="White.TLabel")
        self.lbl_loading.place(relx=0.5, rely=0.5, anchor="center")

        self.create_bottom_panel(self.frame_right)

    def load_graphics_engine(self):
        try:
            self.lbl_loading.destroy()
            
            # [修改] 传入 self.plot_container (Frame) 和 self (App实例)
            self.plot_mgr = PlotManager(self.plot_container, self)
            
            self.plot_mgr.canvas_widget.bind("<Configure>", self.on_canvas_configure)
            
            if hasattr(self, 'tb_frame_placeholder'):
                self.plot_mgr.add_toolbar(self.tb_frame_placeholder)
                
            self.roi_mgr.connect(self.plot_mgr.ax)
            
            logo_path = self.get_asset_path("app_ico.png")
            self.plot_mgr.show_logo(logo_path)
            
        except Exception as e:
            print(f"Graphics Engine Init Error: {e}")
            import traceback
            traceback.print_exc() # 打印完整堆栈以便调试

    def setup_file_group(self):
        self.grp_file = ttk.LabelFrame(self.frame_left, padding=10, style="Card.TLabelframe")
        self.grp_file.pack(fill="x", pady=(0, 10))
        self.ui_elements["grp_file"] = self.grp_file
        
        self.nb_import = ttk.Notebook(self.grp_file)
        self.nb_import.pack(fill="x", expand=True)
        self.nb_import.bind("<<NotebookTabChanged>>", lambda e: self.check_ready())
        
        # --- Tab 1: Separate Files ---
        self.tab_sep = ttk.Frame(self.nb_import, style="White.TFrame", padding=(0, 5))
        self.nb_import.add(self.tab_sep, text=" Separate Files ") 
        self.ui_elements["tab_sep"] = lambda text: self.nb_import.tab(0, text=text)
        self.create_compact_file_row(self.tab_sep, "btn_c1", self.select_c1, "lbl_c1_path")
        self.create_compact_file_row(self.tab_sep, "btn_c2", self.select_c2, "lbl_c2_path")
        
        # --- Tab 2: Single File (Modified) ---
        self.tab_dual = ttk.Frame(self.nb_import, style="White.TFrame", padding=(0, 5))
        self.nb_import.add(self.tab_dual, text=" Single File ")
        self.ui_elements["tab_dual"] = lambda text: self.nb_import.tab(1, text=text)
        
        # [修改] 手动构建这一行，以便插入通道计数标签
        f_row = ttk.Frame(self.tab_dual, style="White.TFrame")
        f_row.pack(fill="x", pady=1)
        
        # 按钮
        self.btn_dual = ttk.Button(f_row, command=self.select_dual, text="📂 Select File")
        self.btn_dual.pack(side="left")
        self.ui_elements["btn_dual"] = self.btn_dual
        
        # 路径显示 (占据剩余空间)
        self.lbl_dual_path = ttk.Label(f_row, text="...", foreground="gray", anchor="w", style="White.TLabel")
        self.lbl_dual_path.pack(side="left", padx=5, fill="x", expand=True)

        # [修正] 通道数指示器 (Badge) - 放在最右侧
        # 关键点：初始化时使用 "White.TLabel" 让它与背景融合（隐身）
        self.lbl_ch_indicator = ttk.Label(f_row, text="", style="White.TLabel")
        self.lbl_ch_indicator.pack(side="right", padx=(0, 5))
        
        # 注意：你之前的代码在这里又重复定义了一次 BadgeBlue，导致出现蓝色方块。已删除。

        # Mixed Stacks & Channel Count Row
        f_inter = ttk.Frame(self.tab_dual, style="White.TFrame")
        f_inter.pack(fill="x", pady=(2, 0))
        
        self.chk_inter = ttk.Checkbutton(f_inter, variable=self.is_interleaved_var, style="Toggle.TButton")
        self.chk_inter.pack(side="left")
        self.ui_elements["chk_interleaved"] = self.chk_inter
        
        ttk.Label(f_inter, text="Ch Count:", style="White.TLabel").pack(side="left", padx=(10, 2))
        self.var_n_channels = tk.IntVar(value=2)
        self.sp_channels = ttk.Spinbox(f_inter, from_=1, to=20, textvariable=self.var_n_channels, width=3)
        self.sp_channels.pack(side="left")
        
        # Action Buttons
        f_actions = ttk.Frame(self.grp_file, style="Card.TFrame")
        f_actions.pack(fill="x", pady=(10, 0))
        
        self.btn_load = ttk.Button(f_actions, command=self.load_data, state="disabled")
        self.btn_load.pack(side="left", fill="x", expand=True, padx=(0, 2))
        self.ui_elements["btn_load"] = self.btn_load

        self.btn_clear_data = ttk.Button(f_actions, text="🗑", width=8, command=self.clear_all_data, style="Gray.TButton")
        self.btn_clear_data.pack(side="right", fill="y")
    
    def setup_preprocess_group(self):
        self.grp_pre = ttk.LabelFrame(self.frame_left, padding=10, style="Card.TLabelframe")
        self.grp_pre.pack(fill="x", pady=(0, 10))
        self.ui_elements["grp_pre"] = self.grp_pre
        row = ttk.Frame(self.grp_pre, style="White.TFrame"); row.pack(fill="x")
        self.btn_align = ttk.Button(row, command=self.run_alignment_thread, state="disabled", width=22)
        self.btn_align.pack(side="left", fill="x", padx=(0, 2))
        self.ui_elements["btn_align"] = self.btn_align
        self.btn_undo_align = ttk.Button(row, command=self.undo_alignment, state="disabled", width=8, style="Gray.TButton")
        self.btn_undo_align.pack(side="right", fill="x", expand=True)
        self.ui_elements["btn_undo_align"] = self.btn_undo_align
        self.pb_align = ttk.Progressbar(self.grp_pre, orient="horizontal", mode="determinate")

    def setup_calc_group(self):
        self.grp_calc = ttk.LabelFrame(self.frame_left, padding=10, style="Card.TLabelframe")
        self.grp_calc.pack(fill="x", pady=(0, 10))
        self.ui_elements["grp_calc"] = self.grp_calc
        
        # --- Ratio Mode Selection ---
        f_mode = ttk.Frame(self.grp_calc, style="White.TFrame"); f_mode.pack(fill="x", pady=(0, 5))
        self.lbl_mode = ttk.Label(f_mode, style="White.TLabel"); self.lbl_mode.pack(side="left")
        self.ui_elements["lbl_ratio_mode"] = self.lbl_mode
        self.ratio_mode_var = tk.StringVar(value="c1_c2") 
        self.combo_mode = ttk.Combobox(f_mode, state="readonly", width=18)
        self.combo_mode.pack(side="right", fill="x", expand=True, padx=(5, 0))
        self.combo_mode.bind("<<ComboboxSelected>>", self.on_mode_change)
        
        # --- Sliders Variables ---
        self.var_int_thresh = tk.DoubleVar(value=0.0); self.var_ratio_thresh = tk.DoubleVar(value=0.0)
        self.var_smooth = tk.DoubleVar(value=0.0); self.var_bg = tk.DoubleVar(value=5.0)
        
        # --- Sliders Creation ---
        self.create_slider(self.grp_calc, "lbl_int_thr", 0, 500, 1, self.var_int_thresh)
        self.create_slider(self.grp_calc, "lbl_ratio_thr", 0, 5.0, 0.1, self.var_ratio_thresh)
        self.create_slider(self.grp_calc, "lbl_smooth", 0, 10, 1, self.var_smooth, True)
        self.create_bg_slider(self.grp_calc, "lbl_bg", 0, 50, self.var_bg)
        
        # --- [MODIFIED] Background ROI Controls ---
        f_bg_tools = ttk.Frame(self.grp_calc, style="White.TFrame")
        f_bg_tools.pack(fill="x", pady=(5, 0))
        
        # 按钮 1: 仅用于“定义”区域 (Action)
        self.btn_draw_bg = ttk.Button(f_bg_tools, text="✏️ Draw BG Region", 
                                      command=self.draw_bg_roi_action)
        self.btn_draw_bg.pack(side="left", fill="x", expand=True, padx=(0, 2))
        
        # 按钮 2: 仅用于“切换”模式 (State Switch)
        # 使用 Checkbutton + Toggle 样式，文字明确为 "Use ROI Mode"
        self.chk_custom_bg = ttk.Checkbutton(f_bg_tools, text="Use ROI BG Mode", 
                                             variable=self.use_custom_bg_var,
                                             command=self.toggle_bg_mode,
                                             style="Toggle.TButton",                                    
                                             state="disabled") 
        self.chk_custom_bg.pack(side="right", fill="x", padx=(2, 0))
        
        # 数值显示标签
        self.lbl_bg_val = ttk.Label(self.grp_calc, text="ROI Val: None", 
                                    foreground="gray", style="White.TLabel", font=("Segoe UI", 8))
        self.lbl_bg_val.pack(fill="x", padx=2, pady=(2, 5))

        # --- Log Scale Toggle ---
        self.log_var = tk.BooleanVar(value=False)
        self.chk_log = ttk.Checkbutton(self.grp_calc, text="📈 Log Scale", 
                                       variable=self.log_var, 
                                       command=self.update_plot, 
                                       style="Toggle.TButton")
        self.chk_log.pack(fill="x", pady=2) 
        self.ui_elements["chk_log"] = self.chk_log 
    
    def toggle_bg_mode(self):
        """
        切换背景模式：点击 'Use ROI Mode' 按钮时触发
        """
        # 获取数值标签的引用
        val_lbl = self.ui_elements.get("val_lbl_bg")
        
        if self.use_custom_bg_var.get():
            # === 进入 ROI 模式 (禁用滑块) ===
            self.bg_scale.state(['disabled'])
            
            # 1. 标题变灰
            self.ui_elements["lbl_bg"].config(foreground="#CCCCCC")
            
            # 2. [NEW] 数值变灰 (不再显示红色)
            if val_lbl: val_lbl.config(foreground="#CCCCCC")
            
        else:
            # === 回到滑块模式 (启用滑块) ===
            self.bg_scale.state(['!disabled'])
            
            # 1. 标题恢复深色
            self.ui_elements["lbl_bg"].config(foreground="#333333")
            
            # 2. [NEW] 数值恢复红色 (强调色)
            if val_lbl: val_lbl.config(foreground="red")
            
        # 立即根据新模式刷新图像
        self.update_plot()
            
        # 2. 刷新图像 (原来的功能)
        self.update_plot()
    def setup_view_group(self):
        self.grp_view = ttk.LabelFrame(self.frame_left, padding=10, style="Card.TLabelframe")
        self.grp_view.pack(fill="x", pady=(0, 10))
        self.ui_elements["grp_view"] = self.grp_view
        f_grid = ttk.Frame(self.grp_view, style="White.TFrame"); f_grid.pack(fill="x")
        self.lbl_cmap = ttk.Label(f_grid, style="White.TLabel"); self.lbl_cmap.grid(row=0, column=0, sticky="w")
        self.ui_elements["lbl_cmap"] = self.lbl_cmap
        self.cmap_var = tk.StringVar(value="coolwarm")
        ttk.OptionMenu(f_grid, self.cmap_var, "coolwarm", "jet", "viridis", "magma", "coolwarm", command=lambda _: self.update_cmap()).grid(row=0, column=1, sticky="ew")
        self.lbl_bg_col = ttk.Label(f_grid, style="White.TLabel"); self.lbl_bg_col.grid(row=1, column=0, sticky="w", pady=5)
        self.ui_elements["lbl_bg_col"] = self.lbl_bg_col
        self.bg_color_var = tk.StringVar(value="Trans")
        ttk.OptionMenu(f_grid, self.bg_color_var, "Trans", "Trans", "Black", "White", command=lambda _: self.update_cmap()).grid(row=1, column=1, sticky="ew", pady=5)
        f_grid.columnconfigure(1, weight=1) 
        self.lock_var = tk.BooleanVar(value=False)
        self.chk_lock = ttk.Checkbutton(self.grp_view, variable=self.lock_var, command=self.toggle_scale_mode, style="Toggle.TButton")
        self.chk_lock.pack(fill="x", pady=(5, 2))
        self.ui_elements["chk_lock"] = self.chk_lock
        f_rng = ttk.Frame(self.grp_view, style="White.TFrame"); f_rng.pack(fill="x")
        self.entry_vmin = ttk.Entry(f_rng, width=6); self.entry_vmin.pack(side="left")
        ttk.Label(f_rng, text="-", style="White.TLabel").pack(side="left")
        self.entry_vmax = ttk.Entry(f_rng, width=6); self.entry_vmax.pack(side="left")
        self.entry_vmin.insert(0,"0.0"); self.entry_vmax.insert(0,"1.0")
        self.entry_vmin.config(state="disabled"); self.entry_vmax.config(state="disabled")
        self.btn_apply = ttk.Button(f_rng, command=self.update_plot, width=6, style="Compact.TButton")
        self.btn_apply.pack(side="right", padx=2, fill="y")
        self.ui_elements["btn_apply"] = self.btn_apply

    def setup_brand_logo(self):
        self.fr_brand = ttk.Frame(self.frame_left, style="White.TFrame")

        self.fr_brand.pack(side="top", fill="x", pady=(0, 0))
        
        inner_box = ttk.Frame(self.fr_brand, style="White.TFrame")
        inner_box.pack(anchor="center")
        try:
            icon_path = self.get_asset_path("app_ico.png") 
            if os.path.exists(icon_path):
                self.brand_icon_img = tk.PhotoImage(file=icon_path)
                if self.brand_icon_img.width() > 100:
                    scale_factor = self.brand_icon_img.width() // 80
                    self.brand_icon_img = self.brand_icon_img.subsample(scale_factor, scale_factor)
                ttk.Label(inner_box, image=self.brand_icon_img, style="White.TLabel").pack(side="top", pady=(0, 5)) 
        except Exception as e: print(f"Brand icon load error: {e}")
        
        ttk.Label(inner_box, text="RIA 莉丫", font=("Microsoft YaHei UI", 12, "bold"), foreground="#0056b3", style="White.TLabel").pack(side="top")
        current_year = datetime.datetime.now().year
        ttk.Label(inner_box, text=f"© {current_year} Dr. Kui Wang | www.cns.ac.cn", font=("Segoe UI", 8), foreground="gray", style="White.TLabel").pack(side="top", pady=(2, 0))


    def rebuild_channel_bar(self):
        """
        根据当前加载的数据，动态生成通道切换按钮。
        """
        # 1. [修正] 清除容器内的所有组件 (包括按钮和分割线)
        for widget in self.frame_channels.winfo_children():
            widget.destroy()
        
        # 重置按钮列表
        self.channel_buttons = []
        
        # 如果没数据，什么都不做
        if self.data1 is None: return

        # 定义一个通用样式函数
        def create_btn(text, mode, parent):
            btn = ttk.Button(parent, text=text, style="Toggle.TButton", 
                             command=lambda m=mode: self.set_view_mode(m))
            btn.pack(side="left", padx=2)
            self.channel_buttons.append(btn)
            return btn

        # 2. 生成 Ratio 按钮
        if self.data2 is not None:
            # 双通道模式
            create_btn("📊 Ratio", "ratio", self.frame_channels)
        else:
            # 单通道模式
            create_btn("🔥 Intensity", "ratio", self.frame_channels)

        # 插入分割线 (现在它会被上面的循环正确清除了)
        ttk.Separator(self.frame_channels, orient="vertical").pack(side="left", fill="y", padx=5)

        # 3. 生成 Ch1 按钮
        create_btn("Ch1", "ch1", self.frame_channels)

        # 4. 生成 Ch2 按钮 (如果存在)
        if self.data2 is not None:
            create_btn("Ch2", "ch2", self.frame_channels)

        # 5. 生成 Aux 按钮
        if hasattr(self, 'data_aux'):
            for i, _ in enumerate(self.data_aux):
                create_btn(f"Ch{i+3}", f"aux_{i}", self.frame_channels)

        # 6. 刷新按钮状态高亮
        self.update_channel_buttons_state()


    def set_view_mode(self, mode):
        # 1. [新增] 切换视图时，如果锁定了范围，强制解锁
        # 防止从 Ratio (0-2.0) 切到 Intensity (0-65535) 时画面因范围不匹配而全黑/全白
        if self.lock_var.get():
            self.lock_var.set(False)
            # 手动更新 UI 状态 (禁用输入框)，但不调用 toggle_scale_mode() 以免触发多余的重绘
            self.entry_vmin.config(state="disabled")
            self.entry_vmax.config(state="disabled")

        self.view_mode = mode
        self.update_channel_buttons_state()
        
        # 2. 自动切换 Colormap
        # 如果切回 Ratio/Int，使用用户选定的 cmap (如 coolwarm)
        # 如果切到原始通道，使用 gray 或 viridis 以便看清细节
        if mode == "ratio":
            self.update_cmap() # 恢复原来的 cmap
        else:
            # 临时切换到 gray 观看原始通道
            self.plot_mgr.update_cmap("gray", "Black") 
            
        self.update_plot()

    def update_channel_buttons_state(self):
        """高亮当前选中的视图模式按钮"""
        # 这一步比较麻烦，因为按钮存储在 list 里，我们需要根据 text 或 command 判断
        # 简单起见，我们重新遍历
        # 这里的逻辑稍微 Hack 一下：我们无法直接获取 command 中的 lambda 参数
        # 所以我们依赖顺序：Ratio -> Ch1 -> Ch2 -> Aux...
        
        # 更好的方法是：在 create_btn 时把 mode 绑定到 widget 属性上
        targets = []
        if self.data2 is not None: targets.append("ratio")
        else: targets.append("ratio") # Intensity
        
        targets.append("ch1")
        if self.data2 is not None: targets.append("ch2")
        if hasattr(self, 'data_aux'):
            for i in range(len(self.data_aux)): targets.append(f"aux_{i}")
            
        # 遍历按钮并设置状态
        for btn, mode_name in zip(self.channel_buttons, targets):
            if mode_name == self.view_mode:
                btn.state(['pressed', 'selected'])
                # 给当前选中的按钮加点颜色样式? 暂时用 pressed 状态
            else:
                btn.state(['!pressed', '!selected'])



    def create_bottom_panel(self, parent):
        bottom_area = ttk.Frame(parent, padding=(0, 10, 0, 0), style="White.TFrame")
        bottom_area.pack(fill="x", side="bottom")
        
        # --- Player Control ---
        p_frame = ttk.LabelFrame(bottom_area, text="Player", style="Card.TLabelframe")
        p_frame.pack(fill="x", pady=(0,10))
        
        row_bar = ttk.Frame(p_frame, style="White.TFrame"); row_bar.pack(fill="x", padx=5)
        self.var_frame = tk.IntVar(value=0)
        self.lbl_frame = ttk.Label(row_bar, text="0/0", width=8, style="White.TLabel"); self.lbl_frame.pack(side="left")
        self.frame_scale = ttk.Scale(row_bar, from_=0, to=1, command=self.on_frame_slide); self.frame_scale.pack(side="left", fill="x", expand=True)
        
        row_ctl = ttk.Frame(p_frame, style="White.TFrame"); row_ctl.pack(fill="x", padx=5, pady=2)
        self.btn_play = ttk.Button(row_ctl, text="▶", width=5, command=self.toggle_play); self.btn_play.pack(side="left")
        self.lbl_spd = ttk.Label(row_ctl, text="Speed:", style="White.TLabel"); self.lbl_spd.pack(side="left", padx=(10,2))
        self.ui_elements["lbl_speed"] = self.lbl_spd
        self.fps_var = tk.StringVar(value="10 FPS")
        ttk.OptionMenu(row_ctl, self.fps_var, "10 FPS", "5 FPS", "10 FPS", "20 FPS", "Max", command=self.change_fps).pack(side="left")
        self.tb_frame_placeholder = ttk.Frame(row_ctl, style="White.TFrame"); self.tb_frame_placeholder.pack(side="right")
        
        # --- Tools Grid ---
        grid_area = ttk.Frame(bottom_area, style="White.TFrame"); grid_area.pack(fill="x", expand=True)
        grid_area.columnconfigure(0, weight=2); grid_area.columnconfigure(1, weight=1); grid_area.columnconfigure(2, weight=1)
        
        # --- Col 0: ROI Tools ---
        fr_roi = ttk.LabelFrame(grid_area, padding=5, style="Card.TLabelframe"); fr_roi.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.ui_elements["lbl_roi_tools"] = fr_roi
        
        row_edit = ttk.Frame(fr_roi, style="White.TFrame"); row_edit.pack(fill="x", pady=2)
        self.shape_var = tk.StringVar(value="rect")
        def set_shape(mode): self.shape_var.set(mode); self.roi_mgr.set_mode(mode)
        
        f_shapes = ttk.Frame(row_edit, style="White.TFrame"); f_shapes.pack(side="left", fill="y")
        self.lbl_shape = ttk.Label(f_shapes, text="Shape:", style="White.TLabel"); self.lbl_shape.pack(side="left", padx=(0, 2))
        self.ui_elements["lbl_shape"] = self.lbl_shape
        ttk.Radiobutton(f_shapes, text="□", variable=self.shape_var, value="rect", command=lambda: set_shape("rect"), style="Toolbutton").pack(side="left", padx=1)
        ttk.Radiobutton(f_shapes, text="○", variable=self.shape_var, value="circle", command=lambda: set_shape("circle"), style="Toolbutton").pack(side="left", padx=1)
        ttk.Radiobutton(f_shapes, text="⬠", variable=self.shape_var, value="polygon", command=lambda: set_shape("polygon"), style="Toolbutton").pack(side="left", padx=2)
        
        # New ROI (Ctrl+T)
        self.btn_draw = ttk.Button(row_edit, text="New (Ctrl+T)", command=self.roi_mgr.start_drawing, style="Toggle.TButton"); self.btn_draw.pack(side="left", padx=(10, 2), fill="y", expand=True)
        self.ui_elements["btn_draw"] = self.btn_draw
        self.roi_mgr.set_draw_button(self.btn_draw)
        
        self.btn_undo = ttk.Button(row_edit, text="↩️", command=self.roi_mgr.remove_last, width=3, style="Compact.TButton"); self.btn_undo.pack(side="left", padx=1, fill="y")
        self.btn_clear = ttk.Button(row_edit, text="🗑️", command=self.roi_mgr.clear_all, width=3, style="Compact.TButton"); self.btn_clear.pack(side="left", padx=1, fill="y")
        
        # Save/Load ROI
        self.btn_save_roi = ttk.Button(row_edit, text="💾", width=3, command=self.save_roi_dialog, style="Compact.TButton"); self.btn_save_roi.pack(side="left", padx=1, fill="y")
        self.btn_load_roi = ttk.Button(row_edit, text="📂", width=3, command=self.load_roi_dialog, style="Compact.TButton"); self.btn_load_roi.pack(side="left", padx=1, fill="y")

        # Plot Action Row
        row_act = ttk.Frame(fr_roi, style="White.TFrame"); row_act.pack(fill="x", pady=4)
        
        # 1. Plot Button
        self.btn_plot = ttk.Button(row_act, text="📈 Plot Curve (Ctrl+P)", command=self.plot_roi_curve)
        self.btn_plot.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.ui_elements["btn_plot"] = self.btn_plot
        
        # 2. [MODIFIED] Live Monitor Toggle
        self.live_plot_var = tk.BooleanVar(value=False)
        self.chk_live = ttk.Checkbutton(row_act, 
                                        variable=self.live_plot_var, 
                                        text="Live Monitor (Ctrl+L)", # 更新文字显示快捷键
                                        style="Toggle.TButton", 
                                        width=25,                     # [NEW] 设置固定宽度 (20字符宽) 让它看起来更宽
                                        command=self.plot_roi_curve)
        self.chk_live.pack(side="right")
        self.ui_elements["chk_live"] = self.chk_live
        
        # Params Row
        row_param = ttk.Frame(fr_roi, style="White.TFrame"); row_param.pack(fill="x", pady=(4, 0))
        row_param.columnconfigure(0, weight=1); row_param.columnconfigure(1, weight=1); row_param.columnconfigure(2, weight=1)
        
        f_int = ttk.Frame(row_param, style="White.TFrame"); f_int.grid(row=0, column=0, sticky="w")
        self.lbl_int = ttk.Label(f_int, text="Imaging Interval (s):", style="White.TLabel"); self.lbl_int.pack(side="left")
        self.ui_elements["lbl_interval"] = self.lbl_int
        self.var_interval = tk.DoubleVar(value=1.0)
        ttk.Entry(f_int, textvariable=self.var_interval, width=5).pack(side="left", padx=(2, 0))
        
        f_unit = ttk.Frame(row_param, style="White.TFrame"); f_unit.grid(row=0, column=1) 
        self.lbl_unit = ttk.Label(f_unit, text="Plotting Unit:", style="White.TLabel"); self.lbl_unit.pack(side="left")
        self.ui_elements["lbl_unit"] = self.lbl_unit
        self.combo_unit = ttk.Combobox(f_unit, values=["s", "m", "h"], width=3, state="readonly"); self.combo_unit.set("s"); self.combo_unit.pack(side="left", padx=2)
        
        self.norm_var = tk.BooleanVar(value=False)
        self.chk_norm = ttk.Checkbutton(row_param, text="Normalization (ΔR/R₀)", variable=self.norm_var, style="Toggle.TButton", command=self.plot_roi_curve); self.chk_norm.grid(row=0, column=2, sticky="e")
        
        # --- Col 1: Export ---
        fr_exp = ttk.LabelFrame(grid_area, padding=5, style="Card.TLabelframe"); fr_exp.grid(row=0, column=1, sticky="nsew", padx=5)
        self.ui_elements["lbl_export"] = fr_exp
        self.btn_save_frame = ttk.Button(fr_exp, command=self.save_current_frame); self.btn_save_frame.pack(fill="x", pady=2)
        self.ui_elements["btn_save_frame"] = self.btn_save_frame
        self.btn_save_stack = ttk.Button(fr_exp, command=self.save_stack_thread); self.btn_save_stack.pack(fill="x", pady=2)
        self.ui_elements["btn_save_stack"] = self.btn_save_stack
        self.btn_save_raw = ttk.Button(fr_exp, command=self.save_raw_thread, style="Gray.TButton"); self.btn_save_raw.pack(fill="x", pady=2)
        self.ui_elements["btn_save_raw"] = self.btn_save_raw
        
        # --- Col 2: Settings ---
        fr_set = ToggledFrame(grid_area, text="Settings", style="Card.TFrame"); fr_set.grid(row=0, column=2, sticky="new", padx=(5, 0))
        self.ui_elements["lbl_settings"] = fr_set.lbl_title
        self.btn_update = ttk.Button(fr_set.sub_frame, command=self.check_update_thread); self.btn_update.pack(fill="x", pady=2)
        self.ui_elements["btn_check_update"] = self.btn_update
        self.btn_contact = ttk.Button(fr_set.sub_frame, command=lambda: webbrowser.open("https://www.cns.ac.cn")); self.btn_contact.pack(fill="x", pady=2)
        self.ui_elements["btn_contact"] = self.btn_contact

    def save_roi_dialog(self):
        default_name = "ROI_Data.json"
        try:
            current_tab = self.nb_import.index("current")
            source_path = None
            if current_tab == 0: source_path = self.c1_path
            else: source_path = self.dual_path
            
            if source_path:
                base = os.path.splitext(os.path.basename(source_path))[0]
                default_name = f"{base}.json"
        except: pass

        path = filedialog.asksaveasfilename(
            defaultextension=".json", 
            filetypes=[("JSON Files", "*.json")],
            initialfile=default_name
        )
        if path: self.roi_mgr.save_rois(path)

    def load_roi_dialog(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if path:
            self.roi_mgr.load_rois(path)

    def ask_channel_roles(self, n_channels):
        dialog = Toplevel(self.root)
        dialog.title("Assign Channels")
        dialog.geometry("320x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 160
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 150
        dialog.geometry(f"+{x}+{y}")
        
        ttk.Label(dialog, text=f"Detected {n_channels} Channels!", font=("Segoe UI", 11, "bold")).pack(pady=10)
        ttk.Label(dialog, text="Please select the pair for Ratio calculation:").pack()
        
        f_form = ttk.Frame(dialog, padding=20)
        f_form.pack(fill="x")
        
        opts = [f"Channel {i+1}" for i in range(n_channels)]
        
        ttk.Label(f_form, text="Numerator (Ch1):").grid(row=0, column=0, pady=5, sticky="e")
        cb_num = ttk.Combobox(f_form, values=opts, state="readonly", width=12)
        cb_num.current(0)
        cb_num.grid(row=0, column=1, pady=5, padx=5)
        
        ttk.Label(f_form, text="Denominator (Ch2):").grid(row=1, column=0, pady=5, sticky="e")
        cb_den = ttk.Combobox(f_form, values=opts, state="readonly", width=12)
        cb_den.current(1) 
        cb_den.grid(row=1, column=1, pady=5, padx=5)
        
        ttk.Label(dialog, text="(Remaining channels will be loaded as Aux)", foreground="gray", font=("Segoe UI", 9)).pack()
        
        selection = {"num": 0, "den": 1}
        
        def confirm():
            n = cb_num.current()
            d = cb_den.current()
            if n == d:
                messagebox.showwarning("Warning", "Numerator and Denominator cannot be the same channel!")
                return
            selection["num"] = n
            selection["den"] = d
            dialog.destroy()
            
        ttk.Button(dialog, text="Confirm", command=confirm, style="Success.TButton").pack(pady=15, fill="x", padx=40)
        
        self.root.wait_window(dialog)
        return selection

    def load_data(self):
        try:
            self.root.config(cursor="watch")
            self.root.update()
            
            self.data_aux = []
            
            current_tab = self.nb_import.index("current")
            channels = []
            
            if current_tab == 0:
                d1, d2 = read_separate_files(self.c1_path, self.c2_path)
                channels = [d1, d2]
                # 分离文件模式，肯定是2通道，这里不需要更新 Single File 的标签
            else:
                n_ch = self.var_n_channels.get() if self.is_interleaved_var.get() else 2
                channels = read_and_split_multichannel(self.dual_path, self.is_interleaved_var.get(), n_ch)
                
                # [修改] 根据通道数，动态应用“样式”和“文字”
                count = len(channels)
                if count == 1:
                    # 激活绿色徽章样式
                    self.lbl_ch_indicator.config(
                        text=f" 1 Ch (Int) ", 
                        style="BadgeGreen.TLabel" 
                    )
                else:
                    # 激活蓝色徽章样式
                    self.lbl_ch_indicator.config(
                        text=f" {count} Chs (Ratio) ", 
                        style="BadgeBlue.TLabel"
                    )

            # ... (后续代码保持不变) ...
            if len(channels) == 1:
                self.data1 = channels[0]
                self.data2 = None
                self.data_aux = []
                self.btn_align.config(state="disabled")
                self.ui_elements["lbl_ratio_thr"].config(foreground="gray")

            elif len(channels) == 2:
                self.data1 = channels[0]
                self.data2 = channels[1]
                self.data_aux = []
                self.btn_align.config(state="normal")
                self.ui_elements["lbl_ratio_thr"].config(foreground="black")

            elif len(channels) > 2:
                self.root.config(cursor="")
                roles = self.ask_channel_roles(len(channels))
                idx_num = roles["num"]
                idx_den = roles["den"]
                self.data1 = channels[idx_num]
                self.data2 = channels[idx_den]
                self.data_aux = []
                for i, d in enumerate(channels):
                    if i != idx_num and i != idx_den:
                        self.data_aux.append(d)
                self.btn_align.config(state="normal")
                self.ui_elements["lbl_ratio_thr"].config(foreground="black")
            else:
                raise ValueError(f"No channels loaded.")

            self.data1_raw = None
            self.data2_raw = None
            self.btn_undo_align.config(state="disabled", text=self.t("btn_undo_align"), style="Gray.TButton")
            
            if self.data2 is not None:
                self.btn_align.config(state="normal", text=self.t("btn_align"), style="TButton")
            else:
                self.btn_align.config(state="disabled")


            self.view_mode = "ratio"
            self.rebuild_channel_bar()


            self.recalc_background()
            self.frame_scale.configure(to=self.data1.shape[0]-1)
            self.var_frame.set(0); self.frame_scale.set(0)
            h, w = self.data1.shape[1], self.data1.shape[2]
            self.plot_mgr.init_image((h, w), cmap="coolwarm")
            self.roi_mgr.connect(self.plot_mgr.ax)
            self.update_plot()
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            self.root.config(cursor="")
    def clear_all_data(self):
        self.is_playing = False
        self.btn_play.config(text="▶")

        self.data1 = None
        self.data2 = None
        self.data_aux = []
        self.data1_raw = None
        self.data2_raw = None
        self.cached_bg1 = 0
        self.cached_bg2 = 0
        self.cached_bg_aux = []
        
        self.c1_path = None
        self.c2_path = None
        self.dual_path = None
        
        self.lbl_c1_path.config(text=self.t("lbl_no_file"))
        self.lbl_c2_path.config(text=self.t("lbl_no_file"))
        self.lbl_dual_path.config(text=self.t("lbl_no_file"))
        
        # [新增] 重置通道数标签
        if hasattr(self, 'lbl_ch_indicator'):
            self.lbl_ch_indicator.config(text="", style="White.TLabel")
        
        self.btn_load.config(state="disabled")
        self.btn_align.config(state="disabled", text=self.t("btn_align"), style="TButton")
        self.btn_undo_align.config(state="disabled", text=self.t("btn_undo_align"), style="Gray.TButton")
        
        self.roi_mgr.clear_all()
        
        if self.plot_mgr:
            logo_path = self.get_asset_path("app_ico.png")
            self.plot_mgr.show_logo(logo_path)
        
        self.var_frame.set(0)
        self.frame_scale.configure(to=1, value=0)
        self.lbl_frame.config(text="0/0")
        self.pb_align.pack_forget()

        # Clear all channels
        for btn in self.channel_buttons:
            btn.destroy()
        self.channel_buttons = []


    def update_mode_options(self):
        txt_c1_c2 = self.t("mode_c1_c2") if "mode_c1_c2" in LANG_MAP else "Ch1 / Ch2"
        txt_c2_c1 = self.t("mode_c2_c1") if "mode_c2_c1" in LANG_MAP else "Ch2 / Ch1"
        self.combo_mode['values'] = [txt_c1_c2, txt_c2_c1]
        current_idx = 0 if self.ratio_mode_var.get() == "c1_c2" else 1
        self.combo_mode.current(current_idx)

    def on_mode_change(self, event):
        idx = self.combo_mode.current()
        self.ratio_mode_var.set("c1_c2" if idx == 0 else "c2_c1")
        self.update_plot()

    def get_active_data(self):
        if self.data1 is None: return None, None, 0, 0
        
        # [NEW] Determine which background to use
        if self.use_custom_bg_var.get():
            # Use user-defined ROI background
            bg1 = self.custom_bg1
            bg2 = self.custom_bg2
        else:
            # Use default percentile background
            bg1 = self.cached_bg1
            bg2 = self.cached_bg2

        # [修改] 单通道处理
        if self.data2 is None:
             # 返回 (Data1, None, BG1, 0)
             return self.data1, None, bg1, 0

        if self.ratio_mode_var.get() == "c1_c2":
            return self.data1, self.data2, bg1, bg2
        else:
            return self.data2, self.data1, bg2, bg1
    
    def draw_bg_roi_action(self):
        # Trigger RoiManager to start drawing in 'background' mode
        self.roi_mgr.start_drawing(mode="rect", is_background=True)
    
    def set_custom_background(self, val1, val2):
        """
        回调函数：由 RoiManager 计算完成后调用。
        """
        self.custom_bg1 = val1
        self.custom_bg2 = val2
        
        # [优化] 根据模式显示不同的文本
        if self.data2 is None:
            self.lbl_bg_val.config(text=f"ROI Val: {val1:.1f}")
        else:
            self.lbl_bg_val.config(text=f"ROI Val: {val1:.1f} / {val2:.1f}")
        
        self.chk_custom_bg.config(state="normal")
        
        if self.use_custom_bg_var.get():
            self.update_plot()


    def create_compact_file_row(self, parent, btn_key, cmd, lbl_attr):
        f = ttk.Frame(parent, style="White.TFrame"); f.pack(fill="x", pady=1)
        btn = ttk.Button(f, command=cmd); btn.pack(side="left")
        self.ui_elements[btn_key] = btn
        lbl = ttk.Label(f, text="...", foreground="gray", anchor="w", style="White.TLabel"); lbl.pack(side="left", padx=5, fill="x", expand=True)
        setattr(self, lbl_attr, lbl)

    def create_slider(self, parent, label_key, min_v, max_v, step, variable, is_int=False):
        f = ttk.Frame(parent, style="White.TFrame"); f.pack(fill="x", pady=1)
        h = ttk.Frame(f, style="White.TFrame"); h.pack(fill="x")
        lbl = ttk.Label(h, style="White.TLabel"); lbl.pack(side="left") 
        self.ui_elements[label_key] = lbl
        val_lbl = ttk.Label(h, text=str(variable.get()), foreground="#007acc", font=self.f_bold, style="White.TLabel")
        val_lbl.pack(side="right", padx=(0, 10))
        def on_slide(v):
            val = float(v)
            if is_int: val = int(val)
            variable.set(val)
            fmt = "{:.0f}" if is_int else "{:.1f}"
            val_lbl.config(text=fmt.format(val))
            if not self.is_playing: self.update_plot()
        s = ttk.Scale(f, from_=min_v, to=max_v, command=on_slide); s.set(variable.get()); s.pack(fill="x")

    def create_bg_slider(self, parent, label_key, min_v, max_v, variable):
        f = ttk.Frame(parent, style="White.TFrame"); f.pack(fill="x", pady=1)
        h = ttk.Frame(f, style="White.TFrame"); h.pack(fill="x")
        
        # 标题 Label (需要翻译，所以放入 ui_elements)
        lbl = ttk.Label(h, style="White.TLabel"); lbl.pack(side="left") 
        self.ui_elements[label_key] = lbl
        
        # 数值 Label (显示动态数字，不能放入 ui_elements，否则会被翻译系统覆盖)
        val_lbl = ttk.Label(h, text=str(int(variable.get())), foreground="#007acc", font=self.f_bold, style="White.TLabel")
        val_lbl.pack(side="right", padx=(0, 10))
        
        # [FIX] 单独存储这个引用，避开 update_language 的循环
        self.lbl_bg_value_display = val_lbl 
        
        def on_move(v): val_lbl.config(text=f"{int(float(v))}")
        def on_release(event):
            val = int(self.bg_scale.get())
            variable.set(val)
            self.recalc_background()
            self.update_plot()
            
        self.bg_scale = ttk.Scale(f, from_=min_v, to=max_v, command=on_move)
        self.bg_scale.set(variable.get()); self.bg_scale.pack(fill="x")
        self.bg_scale.bind("<ButtonRelease-1>", on_release)


    def recalc_background(self):
        if self.data1 is None: return
        try:
            p = self.var_bg.get()
            self.cached_bg1 = calculate_background(self.data1, p)
            
            # [修改] 只有当 data2 存在时才计算 bg2
            if self.data2 is not None:
                self.cached_bg2 = calculate_background(self.data2, p)
            else:
                self.cached_bg2 = 0.0

            self.cached_bg_aux = []
            if hasattr(self, 'data_aux'):
                for aux in self.data_aux:
                    self.cached_bg_aux.append(calculate_background(aux, p))
        except: pass

    def select_c1(self):
        p = filedialog.askopenfilename()
        if p: self.c1_path = p; self.lbl_c1_path.config(text=os.path.basename(p)); self.check_ready()
    def select_c2(self):
        p = filedialog.askopenfilename()
        if p: self.c2_path = p; self.lbl_c2_path.config(text=os.path.basename(p)); self.check_ready()
    def select_dual(self):
        p = filedialog.askopenfilename(filetypes=[("TIFF Files", "*.tif *.tiff *.nd2"), ("All Files", "*.*")])
        if p: 
            self.dual_path = p
            self.lbl_dual_path.config(text=os.path.basename(p))
            self.check_ready()

    def check_ready(self):
        current_tab = self.nb_import.index("current")
        if current_tab == 0:
            if self.c1_path and self.c2_path: self.btn_load.config(state="normal")
            else: self.btn_load.config(state="disabled")
        else:
            if self.dual_path: self.btn_load.config(state="normal")
            else: self.btn_load.config(state="disabled")

    def run_alignment_thread(self):
        if self.data1 is None: return
        self.btn_align.config(state="disabled")
        self.btn_load.config(state="disabled")
        self.pb_align.pack(fill="x", pady=(5, 0))
        self.pb_align["value"] = 0
        threading.Thread(target=self.alignment_task, daemon=True).start()

    def alignment_task(self):
        try:
            if self.data1_raw is None:
                self.data1_raw = self.data1.copy()
                self.data2_raw = self.data2.copy()
            def progress_cb(curr, total):
                self.root.after(0, lambda: self.pb_align.configure(value=(curr/total)*100))
            d1_aligned, d2_aligned = align_stack_ecc(self.data1, self.data2, progress_callback=progress_cb)
            self.data1 = d1_aligned
            self.data2 = d2_aligned
            self.root.after(0, self.alignment_done_ui)
        except ImportError:
            self.root.after(0, lambda: messagebox.showerror("Error", "OpenCV not found.\nPlease run: pip install opencv-python"))
            self.root.after(0, self.alignment_reset_ui)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Alignment Error", str(e)))
            self.root.after(0, self.alignment_reset_ui)

    def alignment_done_ui(self):
        self.recalc_background()
        self.update_plot()
        self.pb_align.pack_forget()
        self.btn_load.config(state="normal")
        self.btn_align.config(state="normal", text=self.t("btn_align_done"), style="Success.TButton")
        self.btn_undo_align.config(state="normal", text=self.t("btn_undo_align"), style="Gray.TButton")

    def alignment_reset_ui(self):
        self.pb_align.pack_forget()
        self.btn_load.config(state="normal")
        self.btn_align.config(state="normal")

    def undo_alignment(self):
        if self.data1_raw is not None:
            self.data1 = self.data1_raw.copy()
            self.data2 = self.data2_raw.copy()
            self.recalc_background()
            self.update_plot()
            self.data1_raw = None
            self.data2_raw = None
            self.btn_undo_align.config(text=self.t("btn_undo_done"), style="Success.TButton")
            self.btn_align.config(text=self.t("btn_align"), style="TButton")
            def restore_undo_btn():
                try: self.btn_undo_align.config(state="disabled", text=self.t("btn_undo_align"), style="Gray.TButton")
                except: pass
            self.root.after(1000, restore_undo_btn)

    def get_processed_frame(self, frame_idx):
        d_num, d_den, bg_num, bg_den = self.get_active_data()
        if d_num is None: return None
        
        # === 逻辑分支 ===
        
        # 1. 原始通道模式 (Ch1, Ch2, Aux)
        if self.view_mode == "ch1":
            # 返回：(数据 - 背景)，并 Clip 掉负值
            raw = d_num[frame_idx].astype(np.float32) - bg_num
            return np.clip(raw, 0, None)
            
        elif self.view_mode == "ch2":
            if d_den is None: return None
            raw = d_den[frame_idx].astype(np.float32) - bg_den
            return np.clip(raw, 0, None)
            
        elif self.view_mode.startswith("aux_"):
            try:
                idx = int(self.view_mode.split("_")[1])
                if idx < len(self.data_aux):
                    # Aux 也有背景吗？目前我们在 recalc_background 里算过 cached_bg_aux
                    bg_val = self.cached_bg_aux[idx] if idx < len(self.cached_bg_aux) else 0
                    raw = self.data_aux[idx][frame_idx].astype(np.float32) - bg_val
                    return np.clip(raw, 0, None)
            except: return None

        # 2. Ratio / Main 模式 (默认)
        # 这里维持原来的逻辑，进行比率计算、阈值过滤、平滑等
        return process_frame_ratio(
            d_num[frame_idx], 
            d_den[frame_idx] if d_den is not None else None,
            bg_num, bg_den,
            self.var_int_thresh.get(), self.var_ratio_thresh.get(),
            int(self.var_smooth.get()), False 
        )

    def toggle_scale_mode(self):
        if self.lock_var.get():
            self.entry_vmin.config(state="normal")
            self.entry_vmax.config(state="normal")
        else:
            self.entry_vmin.config(state="disabled")
            self.entry_vmax.config(state="disabled")
        self.update_plot()

    def update_plot(self):
        if self.data1 is None: return
        idx = self.var_frame.get()
        img = self.get_processed_frame(idx)
        if img is None: return

        # 1. 计算 View Mode 字符串 (用于标题) 和 Colorbar 标签
        cbar_str = "Intensity Value" # 默认值
        
        if self.view_mode == "ratio":
            if self.data2 is not None:
                mode_str = "Ratio"
                cbar_str = "Ratio Value" # 只有双通道 Ratio 模式才显示 Ratio
            else:
                mode_str = "Intensity"
                cbar_str = "Intensity Value" # 单通道模式显示 Intensity
        elif self.view_mode == "ch1": 
            mode_str = "Ch1 (Raw-BG)"
        elif self.view_mode == "ch2": 
            mode_str = "Ch2 (Raw-BG)"
        else: 
            mode_str = self.view_mode.capitalize()

        # 2. 计算 Scaling Mode (Auto / Lock) 和 vmin/vmax
        if self.lock_var.get():
            try: 
                vmin, vmax = float(self.entry_vmin.get()), float(self.entry_vmax.get())
            except: 
                vmin, vmax = 0.1, 1.0 
            mode = "Lock"
            self.entry_vmin.config(state="normal")
            self.entry_vmax.config(state="normal")
        else:
            mode = "Auto"
            try:
                valid_mask = ~np.isnan(img)
                if self.log_var.get(): valid_mask &= (img > 1e-6)
                valid_data = img[valid_mask]
                if len(valid_data) > 0: vmin, vmax = np.nanpercentile(valid_data, [5, 95])
                else: vmin, vmax = 0.1, 1.0
            except: vmin, vmax = 0, 1
            
            self.entry_vmin.config(state="normal"); self.entry_vmax.config(state="normal")
            self.entry_vmin.delete(0, tk.END); self.entry_vmin.insert(0, f"{vmin:.2f}")
            self.entry_vmax.delete(0, tk.END); self.entry_vmax.insert(0, f"{vmax:.2f}")
            self.entry_vmin.config(state="disabled"); self.entry_vmax.config(state="disabled")

        # 3. 构建标题
        log_str = 'Log' if self.log_var.get() else 'Linear'
        title = f"{mode_str} | Frame {idx} | {mode} | {log_str}"

        # 4. 更新图像 (传入 cbar_label)
        self.plot_mgr.update_image(
            img, vmin, vmax, 
            log_scale=self.log_var.get(), 
            title=title, 
            cbar_label=cbar_str # [修改] 传入计算好的标签
        )

    def update_cmap(self):
        self.plot_mgr.update_cmap(self.cmap_var.get(), self.bg_color_var.get())

    def plot_roi_curve(self):
        try: interval = float(self.var_interval.get())
        except: interval = 1.0
        unit = self.combo_unit.get()
        i_th = self.var_int_thresh.get()
        r_th = self.var_ratio_thresh.get()
        self.roi_mgr.plot_curve(
            interval=interval, 
            unit=unit, 
            is_log=self.log_var.get(),
            do_norm=self.norm_var.get(),
            int_thresh=i_th,
            ratio_thresh=r_th
        )

    def save_stack_thread(self):
        if self.data1 is None: return
        threading.Thread(target=self.save_stack_task).start()
    
    def save_stack_task(self):
        try:
            self.thread_safe_config(self.ui_elements["btn_save_stack"], state="disabled", text="⏳ Saving...")
            ts = datetime.datetime.now().strftime("%H%M%S")
            path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=f"Ratio_Stack_{ts}.tif")
            if not path: return
            with tiff.TiffWriter(path, bigtiff=True) as tif:
                for i in range(self.data1.shape[0]):
                    if i%10==0: self.thread_safe_config(self.ui_elements["btn_save_stack"], text=f"⏳ {i}/{self.data1.shape[0]}")
                    tif.write(self.get_processed_frame(i).astype(np.float32), contiguous=True)
            self.root.after(0, lambda: messagebox.showinfo("OK", f"Saved: {path}"))
        except Exception as e: self.root.after(0, lambda: messagebox.showerror("Err", str(e)))
        finally: 
            self.thread_safe_config(self.ui_elements["btn_save_stack"], state="normal", text=self.t("btn_save_stack"))

    def save_raw_thread(self):
        if self.data1 is None: return
        threading.Thread(target=self.save_raw_task).start()

    def save_raw_task(self):
        try:
            self.thread_safe_config(self.ui_elements["btn_save_raw"], state="disabled", text="⏳ Saving...")
            ts = datetime.datetime.now().strftime("%H%M%S")
            path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=f"Clean_Ratio_Stack_{ts}.tif")
            if not path: return
            d_num, d_den, bg_num, bg_den = self.get_active_data()
            with tiff.TiffWriter(path, bigtiff=True) as tif:
                for i in range(d_num.shape[0]):
                    if i%10==0: self.thread_safe_config(self.ui_elements["btn_save_raw"], text=f"⏳ {i}/{d_num.shape[0]}")
                    ratio_frame = process_frame_ratio(
                        d_num[i], d_den[i],
                        bg_num, bg_den,
                        self.var_int_thresh.get(), self.var_ratio_thresh.get(),
                        smooth_size=0, log_scale=False
                    )
                    tif.write(ratio_frame.astype(np.float32), contiguous=True)
            self.root.after(0, lambda: messagebox.showinfo("OK", f"Saved Clean Ratio Stack: {path}"))
        except Exception as e: self.root.after(0, lambda: messagebox.showerror("Err", str(e)))
        finally: 
            self.thread_safe_config(self.ui_elements["btn_save_raw"], state="normal", text=self.t("btn_save_raw"))

    def save_current_frame(self):
        if self.data1 is None: return
        path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=f"Ratio_F{self.var_frame.get()}.tif")
        if path: tiff.imwrite(path, self.get_processed_frame(self.var_frame.get()))

    def on_frame_slide(self, v):
        self.var_frame.set(int(float(v))); self.lbl_frame.config(text=f"{self.var_frame.get()}/{self.data1.shape[0]-1}")
        if not self.is_playing: self.update_plot()
    
    def toggle_play(self):
        if self.is_playing: self.is_playing = False; self.btn_play.config(text="▶")
        else: self.is_playing = True; self.btn_play.config(text="⏸"); self.play_loop()
    
    def play_loop(self):
        if not self.is_playing: return
        curr = self.var_frame.get(); nxt = 0 if curr >= self.data1.shape[0]-1 else curr + 1
        self.var_frame.set(nxt); self.frame_scale.set(nxt)
        self.lbl_frame.config(text=f"{nxt}/{self.data1.shape[0]-1}"); self.update_plot()
        dt = 1 if "Max" in self.fps_var.get() else int(1000/int(self.fps_var.get().split()[0]))
        self.root.after(dt, self.play_loop)
    
    def change_fps(self, v):
        if "Max" in v: self.fps = 100
        else:
            try: self.fps = int(v.split()[0])
            except: self.fps = 10

    def check_update_thread(self):
        self.btn_update.config(state="disabled")
        threading.Thread(target=self.check_update_task, daemon=True).start()

    def check_update_task(self):
        api_url = "https://api.github.com/repos/Epivitae/RatioImagingAnalyzer/releases/latest"
        try:
            response = requests.get(api_url, timeout=5)
            response.raise_for_status() 
            data = response.json()
            latest_tag = data.get("tag_name", "").strip() 
            html_url = data.get("html_url", "")
            if self.is_newer_version(latest_tag, self.VERSION):
                self.root.after(0, lambda: self.ask_download(latest_tag, html_url))
            else:
                self.root.after(0, lambda: messagebox.showinfo(self.t("title_update"), self.t("msg_uptodate")))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"{self.t('err_check')}{str(e)}"))
        finally:
            self.thread_safe_config(self.btn_update, state="normal")

    def is_newer_version(self, latest, current):
        def parse_ver(v_str):
            v_clean = v_str.lower().replace("v", "").replace("ver", "")
            try: return [int(x) for x in v_clean.split('.')]
            except: return [0, 0, 0]
        return parse_ver(latest) > parse_ver(current)

    def ask_download(self, version, url):
        msg = self.t("msg_new_ver").format(version)
        if messagebox.askyesno(self.t("title_update"), msg):
            webbrowser.open(url)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("RIA - Ratio Imaging Analyzer")
    app = RatioAnalyzerApp(root)
    root.mainloop()