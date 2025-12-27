import tkinter as tk
from tkinter import filedialog, messagebox, ttk, Toplevel
import tkinter.font as tkfont
import numpy as np
import tifffile as tiff
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.widgets import RectangleSelector
from matplotlib.colors import LogNorm, Normalize
import os
import sys
import warnings
import datetime
import threading
import requests
import webbrowser

# --- 引入拆分模块 ---
from constants import LANG_MAP
from components import ToggledFrame

try:
    from processing import calculate_background, process_frame_ratio
except ImportError:
    try:
        from .processing import calculate_background, process_frame_ratio
    except ImportError:
        pass 

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
        
        # --- 1. 核心字体对象初始化 ---
        self.base_font_size = 10
        self.current_font_size = self.base_font_size
        
        # 定义动态字体对象
        self.f_normal = tkfont.Font(family="Segoe UI", size=self.base_font_size)
        self.f_bold = tkfont.Font(family="Segoe UI", size=self.base_font_size, weight="bold")
        self.f_title = tkfont.Font(family="Helvetica", size=self.base_font_size + 8, weight="bold")
        
        # 接管系统字体
        self.default_tk_font = tkfont.nametofont("TkDefaultFont")
        self.text_tk_font = tkfont.nametofont("TkTextFont")
        self.caption_tk_font = tkfont.nametofont("TkCaptionFont")

        # --- 样式初始化 ---
        self.setup_theme()
        
        self.VERSION = __version__
        self.current_lang = "cn"
        self.ui_elements = {}
        self.root.geometry("1280x850")
        self.root.configure(bg="#F0F2F5") 
        
        # 设置最小窗口大小，防止布局完全崩坏
        self.root.minsize(1000, 600)
        
        try:
            icon_path = self.get_asset_path("ratiofish.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass

        self.data1 = None; self.data2 = None
        self.cached_bg1 = 0; self.cached_bg2 = 0
        self.im_object = None; self.ax = None; self.cbar = None
        self.c1_path = None; self.c2_path = None
        self.is_playing = False; self.fps = 10 
        
        self.roi_selector = None; self.roi_coords = None
        self.plot_window = None; self.plot_ax = None; self.plot_canvas = None
        self.is_calculating_roi = False 

        self.setup_ui()
        self.update_language()
        
        # 初始化触发一次
        self.change_font_size(0)

    def setup_theme(self):
        """配置现代扁平化主题，并绑定动态字体"""
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except:
            pass
            
        BG_COLOR = "#F0F2F5"
        CARD_COLOR = "#FFFFFF"
        TEXT_COLOR = "#333333"
        
        # --- 全局字体绑定 ---
        style.configure(".", background=BG_COLOR, foreground=TEXT_COLOR, font=self.f_normal)
        style.configure("TLabel", background=BG_COLOR, font=self.f_normal)
        style.configure("TButton", padding=4, font=self.f_normal)
        style.configure("TCheckbutton", font=self.f_normal)
        style.configure("TRadiobutton", font=self.f_normal)
        style.configure("TEntry", font=self.f_normal)
        style.configure("TCombobox", font=self.f_normal)
        
        # --- 自定义样式 ---
        # 1. 卡片样式
        style.configure("Card.TFrame", background=CARD_COLOR, relief="flat")
        
        # 2. LabelFrame 样式
        style.configure("Card.TLabelframe", background=CARD_COLOR, relief="solid", borderwidth=1)
        style.configure("Card.TLabelframe.Label", background=CARD_COLOR, foreground="#0056b3", font=self.f_bold)
        
        # 3. 头部样式
        style.configure("Header.TFrame", background=CARD_COLOR)
        
        # 4. 内部控件适配白色背景
        style.configure("White.TLabel", background=CARD_COLOR, font=self.f_normal)
        style.configure("White.TCheckbutton", background=CARD_COLOR, font=self.f_normal)
        style.configure("White.TRadiobutton", background=CARD_COLOR, font=self.f_normal)
        style.configure("White.TFrame", background=CARD_COLOR)
        
        self.style = style

    def get_asset_path(self, filename):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, "assets", filename)
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__)) 
            project_root = os.path.dirname(current_dir)             
            return os.path.join(project_root, "assets", filename)

    def t(self, key):
        if key not in LANG_MAP: return key
        return LANG_MAP[key][self.current_lang]

    def change_font_size(self, delta):
        """统一调整所有字体大小，修复单/双号字号遮挡问题"""
        new_size = self.current_font_size + delta
        if new_size < 8: new_size = 8
        if new_size > 24: new_size = 24
        self.current_font_size = new_size
        
        # 1. 更新字体对象
        self.f_normal.configure(size=new_size)
        self.f_bold.configure(size=new_size)
        self.f_title.configure(size=new_size + 8)
        
        # 2. 更新系统默认字体
        self.default_tk_font.configure(size=new_size)
        self.text_tk_font.configure(size=new_size)
        self.caption_tk_font.configure(size=new_size, weight="bold")
        
        # 3. [关键修复] 强制重新配置 Style
        self.style.configure(".", font=self.f_normal)
        self.style.configure("TButton", font=self.f_normal)
        self.style.configure("Card.TLabelframe.Label", font=self.f_bold) 

        # 4. [关键修复] 强制触发布局更新
        self.root.update_idletasks()

    def reset_font_size(self):
        delta = self.base_font_size - self.current_font_size
        self.change_font_size(delta)

    def setup_ui(self):
        # --- Header ---
        header = ttk.Frame(self.root, padding="15 10", style="Header.TFrame")
        header.pack(fill="x")
        
        sep = tk.Frame(self.root, bg="#ddd", height=1)
        sep.pack(fill="x")
        
        self.lbl_title = ttk.Label(header, text="RIA", font=self.f_title, background="#FFFFFF", foreground="#2c3e50")
        self.lbl_title.pack(side="left")
        self.ui_elements["header_title"] = self.lbl_title

        btn_frame = ttk.Frame(header, style="Header.TFrame")
        btn_frame.pack(side="right")
        
        ttk.Button(btn_frame, text="🌐 CN/EN", command=self.toggle_language).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="A+", width=3, command=lambda: self.change_font_size(1)).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="⟳", width=3, command=self.reset_font_size).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="A-", width=3, command=lambda: self.change_font_size(-1)).pack(side="right", padx=2)

        # --- Footer ---
        footer = tk.Frame(self.root, bg="#F0F2F5", height=25)
        footer.pack(side="bottom", fill="x")
        ttk.Label(footer, text=f"© Dr. Kui Wang | {self.VERSION} | k@cns.ac.cn", font=("Arial", 9), foreground="#888").pack(pady=5)

        # --- Main Layout (PanedWindow) ---
        self.main_pane = ttk.PanedWindow(self.root, orient="horizontal")
        self.main_pane.pack(fill="both", expand=True, padx=10, pady=10)

        # === Left Panel ===
        self.frame_left_container = ttk.Frame(self.main_pane, style="Card.TFrame", padding=10)
        
        # [关键设置] 左侧 weight=0 意味着它不会参与拉伸，自然保护了它不被随意压缩（直到空间极度不足）
        self.main_pane.add(self.frame_left_container, weight=0)
        
        self.frame_left = ttk.Frame(self.frame_left_container, width=320, style="White.TFrame")
        self.frame_left.pack(fill="both", expand=True)

        # 1. File Group
        self.grp_file = ttk.LabelFrame(self.frame_left, padding=10, style="Card.TLabelframe")
        self.grp_file.pack(fill="x", pady=(0, 10))
        self.ui_elements["grp_file"] = self.grp_file
        
        self.create_compact_file_row(self.grp_file, "btn_c1", self.select_c1, "lbl_c1_path")
        self.create_compact_file_row(self.grp_file, "btn_c2", self.select_c2, "lbl_c2_path")
        self.btn_load = ttk.Button(self.grp_file, command=self.load_data, state="disabled")
        self.btn_load.pack(fill="x", pady=5)
        self.ui_elements["btn_load"] = self.btn_load

        # 2. Calculation Group
        self.grp_calc = ttk.LabelFrame(self.frame_left, padding=10, style="Card.TLabelframe")
        self.grp_calc.pack(fill="x", pady=(0, 10))
        self.ui_elements["grp_calc"] = self.grp_calc
        
        self.var_int_thresh = tk.DoubleVar(value=0.0); self.var_ratio_thresh = tk.DoubleVar(value=0.0)
        self.var_smooth = tk.DoubleVar(value=0.0); self.var_bg = tk.DoubleVar(value=5.0)
        
        self.create_slider(self.grp_calc, "lbl_int_thr", 0, 500, 1, self.var_int_thresh)
        self.create_slider(self.grp_calc, "lbl_ratio_thr", 0, 5.0, 0.1, self.var_ratio_thresh)
        self.create_slider(self.grp_calc, "lbl_smooth", 0, 10, 1, self.var_smooth, True)
        self.create_bg_slider(self.grp_calc, "lbl_bg", 0, 50, self.var_bg)
        
        self.log_var = tk.BooleanVar(value=False)
        self.chk_log = ttk.Checkbutton(self.grp_calc, variable=self.log_var, command=self.update_plot, style="White.TCheckbutton")
        self.chk_log.pack(anchor="w", pady=2); self.ui_elements["chk_log"] = self.chk_log

        # 3. View Group
        self.grp_view = ttk.LabelFrame(self.frame_left, padding=10, style="Card.TLabelframe")
        self.grp_view.pack(fill="x", pady=(0, 10))
        self.ui_elements["grp_view"] = self.grp_view
        
        f_grid = ttk.Frame(self.grp_view, style="White.TFrame"); f_grid.pack(fill="x")
        self.lbl_cmap = ttk.Label(f_grid, style="White.TLabel"); self.lbl_cmap.grid(row=0, column=0, sticky="w")
        self.ui_elements["lbl_cmap"] = self.lbl_cmap
        self.cmap_var = tk.StringVar(value="jet")
        ttk.OptionMenu(f_grid, self.cmap_var, "jet", "jet", "viridis", "magma", "coolwarm", command=lambda _: self.update_cmap()).grid(row=0, column=1, sticky="ew")
        
        self.lbl_bg_col = ttk.Label(f_grid, style="White.TLabel"); self.lbl_bg_col.grid(row=1, column=0, sticky="w", pady=5)
        self.ui_elements["lbl_bg_col"] = self.lbl_bg_col
        self.bg_color_var = tk.StringVar(value="Transparent")
        ttk.OptionMenu(f_grid, self.bg_color_var, "Transparent", "Transparent", "Black", "White", command=lambda _: self.update_cmap()).grid(row=1, column=1, sticky="ew", pady=5)

        self.lock_var = tk.BooleanVar(value=False)
        self.chk_lock = ttk.Checkbutton(self.grp_view, variable=self.lock_var, command=self.toggle_scale_mode, style="White.TCheckbutton")
        self.chk_lock.pack(anchor="w"); self.ui_elements["chk_lock"] = self.chk_lock
        
        f_rng = ttk.Frame(self.grp_view, style="White.TFrame"); f_rng.pack(fill="x")
        self.entry_vmin = ttk.Entry(f_rng, width=6); self.entry_vmin.pack(side="left")
        ttk.Label(f_rng, text="-", style="White.TLabel").pack(side="left")
        self.entry_vmax = ttk.Entry(f_rng, width=6); self.entry_vmax.pack(side="left")
        self.entry_vmin.insert(0,"0.0"); self.entry_vmax.insert(0,"1.0")
        self.entry_vmin.config(state="disabled"); self.entry_vmax.config(state="disabled")
        
        self.btn_apply = ttk.Button(f_rng, command=self.update_plot, width=6)
        self.btn_apply.pack(side="right", padx=2); self.ui_elements["btn_apply"] = self.btn_apply

        # === Right Panel ===
        self.frame_right = ttk.Frame(self.main_pane, style="Card.TFrame", padding=10)
        
        # 右侧 weight=1，表示它会吸收多余空间或优先被压缩
        self.main_pane.add(self.frame_right, weight=1)

        # Plot Container
        self.plot_container = ttk.Frame(self.frame_right, style="White.TFrame")
        self.plot_container.pack(fill="both", expand=True)
        
        self.fig = plt.Figure(figsize=(6, 5), dpi=100)
        self.fig.patch.set_facecolor('#FFFFFF') 
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_container)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.mpl_connect('motion_notify_event', self.on_roi_mouse_move)

        self.create_bottom_panel(self.frame_right)

    def create_bottom_panel(self, parent):
        bottom_area = ttk.Frame(parent, padding=(0, 10, 0, 0), style="White.TFrame")
        bottom_area.pack(fill="x", side="bottom")

        # Player Frame
        p_frame = ttk.LabelFrame(bottom_area, text="Player", style="Card.TLabelframe")
        p_frame.pack(fill="x", pady=(0,10))
        
        row_bar = ttk.Frame(p_frame, style="White.TFrame"); row_bar.pack(fill="x", padx=5)
        self.var_frame = tk.IntVar(value=0)
        self.lbl_frame = ttk.Label(row_bar, text="0/0", width=8, style="White.TLabel"); self.lbl_frame.pack(side="left")
        self.frame_scale = ttk.Scale(row_bar, from_=0, to=1, command=self.on_frame_slide)
        self.frame_scale.pack(side="left", fill="x", expand=True)
        
        row_ctl = ttk.Frame(p_frame, style="White.TFrame"); row_ctl.pack(fill="x", padx=5, pady=2)
        self.btn_play = ttk.Button(row_ctl, text="▶", width=5, command=self.toggle_play); self.btn_play.pack(side="left")
        
        self.lbl_spd = ttk.Label(row_ctl, text="Speed:", style="White.TLabel"); self.lbl_spd.pack(side="left", padx=(10,2))
        self.ui_elements["lbl_speed"] = self.lbl_spd
        self.fps_var = tk.StringVar(value="10 FPS")
        ttk.OptionMenu(row_ctl, self.fps_var, "10 FPS", "5 FPS", "10 FPS", "20 FPS", "Max", command=self.change_fps).pack(side="left")
        
        # Toolbar
        tb_frame = ttk.Frame(row_ctl, style="White.TFrame"); tb_frame.pack(side="right")
        self.toolbar = NavigationToolbar2Tk(self.canvas, tb_frame)
        self.toolbar.config(background="#FFFFFF") 
        self.toolbar._message_label.config(background="#FFFFFF")
        self.toolbar.update()

        # Tools Grid
        grid_area = ttk.Frame(bottom_area, style="White.TFrame")
        grid_area.pack(fill="x", expand=True)
        
        grid_area.columnconfigure(0, weight=2)
        grid_area.columnconfigure(1, weight=1)
        grid_area.columnconfigure(2, weight=1)

        # ROI Tools
        fr_roi = ttk.LabelFrame(grid_area, padding=5, style="Card.TLabelframe")
        fr_roi.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.ui_elements["lbl_roi_tools"] = fr_roi
        
        self.btn_draw = ttk.Button(fr_roi, command=self.activate_roi_drawer)
        self.btn_draw.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.ui_elements["btn_draw"] = self.btn_draw
        
        self.btn_clear = ttk.Button(fr_roi, command=self.clear_roi)
        self.btn_clear.grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        self.ui_elements["btn_clear"] = self.btn_clear
        
        self.btn_plot = ttk.Button(fr_roi, command=self.plot_roi_curve)
        self.btn_plot.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self.ui_elements["btn_plot"] = self.btn_plot

        self.live_plot_var = tk.BooleanVar(value=False)
        self.chk_live = ttk.Checkbutton(fr_roi, variable=self.live_plot_var, style="White.TCheckbutton")
        self.chk_live.grid(row=1, column=1, padx=5, pady=2, sticky="w")
        self.ui_elements["chk_live"] = self.chk_live

        f_time = ttk.Frame(fr_roi, style="White.TFrame")
        f_time.grid(row=2, column=0, columnspan=2, sticky="w", padx=2, pady=5)
        
        self.lbl_int = ttk.Label(f_time, text="Interval (s):", style="White.TLabel"); self.lbl_int.pack(side="left")
        self.ui_elements["lbl_interval"] = self.lbl_int
        
        self.var_interval = tk.DoubleVar(value=1.0)
        ttk.Entry(f_time, textvariable=self.var_interval, width=5).pack(side="left", padx=(2, 10))
        
        self.lbl_unit = ttk.Label(f_time, text="X-Axis Unit:", style="White.TLabel"); self.lbl_unit.pack(side="left")
        self.ui_elements["lbl_unit"] = self.lbl_unit

        self.combo_unit = ttk.Combobox(f_time, values=["s", "m", "h"], width=3, state="readonly")
        self.combo_unit.set("s"); self.combo_unit.pack(side="left", padx=2)

        fr_roi.columnconfigure(0, weight=1)
        fr_roi.columnconfigure(1, weight=1)

        # Export Tools
        fr_exp = ttk.LabelFrame(grid_area, padding=5, style="Card.TLabelframe")
        fr_exp.grid(row=0, column=1, sticky="nsew", padx=5)
        self.ui_elements["lbl_export"] = fr_exp
        
        self.btn_save_frame = ttk.Button(fr_exp, command=self.save_current_frame)
        self.btn_save_frame.pack(fill="x", pady=2)
        self.ui_elements["btn_save_frame"] = self.btn_save_frame
        
        self.btn_save_stack = ttk.Button(fr_exp, command=self.save_stack_thread)
        self.btn_save_stack.pack(fill="x", pady=2)
        self.ui_elements["btn_save_stack"] = self.btn_save_stack

        # Settings
        fr_set = ToggledFrame(grid_area, text="Settings", style="Card.TFrame")
        fr_set.grid(row=0, column=2, sticky="new", padx=(5, 0))
        self.ui_elements["lbl_settings"] = fr_set.lbl_title
        
        self.btn_update = ttk.Button(fr_set.sub_frame, command=self.check_update_thread)
        self.btn_update.pack(fill="x", pady=2)
        self.ui_elements["btn_check_update"] = self.btn_update

    def toggle_language(self):
        self.current_lang = "en" if self.current_lang == "cn" else "cn"
        self.update_language()

    def update_language(self):
        self.root.title(self.t("window_title").format(self.VERSION))
        self.lbl_title.config(text=self.t("header_title"))
        for key, widget in self.ui_elements.items():
            try: widget.config(text=self.t(key))
            except: pass
        if self.c1_path is None: self.lbl_c1_path.config(text=self.t("lbl_no_file"))
        if self.c2_path is None: self.lbl_c2_path.config(text=self.t("lbl_no_file"))

    def create_compact_file_row(self, parent, btn_key, cmd, lbl_attr):
        f = ttk.Frame(parent, style="White.TFrame"); f.pack(fill="x", pady=1)
        btn = ttk.Button(f, width=8, command=cmd); btn.pack(side="left")
        self.ui_elements[btn_key] = btn
        lbl = ttk.Label(f, text="...", foreground="gray", anchor="w", style="White.TLabel"); lbl.pack(side="left", padx=5, fill="x", expand=True)
        setattr(self, lbl_attr, lbl)

    def create_slider(self, parent, label_key, min_v, max_v, step, variable, is_int=False):
        f = ttk.Frame(parent, style="White.TFrame"); f.pack(fill="x", pady=1)
        h = ttk.Frame(f, style="White.TFrame"); h.pack(fill="x")
        lbl = ttk.Label(h, style="White.TLabel"); lbl.pack(side="left") 
        self.ui_elements[label_key] = lbl
        
        # 数值显示使用 f_bold
        val_lbl = ttk.Label(h, text=str(variable.get()), foreground="#007acc", font=self.f_bold, style="White.TLabel")
        val_lbl.pack(side="right")
        
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
        lbl = ttk.Label(h, style="White.TLabel"); lbl.pack(side="left") 
        self.ui_elements[label_key] = lbl
        
        val_lbl = ttk.Label(h, text=str(variable.get()), foreground="red", font=self.f_bold, style="White.TLabel")
        val_lbl.pack(side="right")
        
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
            self.cached_bg2 = calculate_background(self.data2, p)
        except: pass

    def load_data(self):
        try:
            self.root.config(cursor="watch"); self.root.update()
            d1 = tiff.imread(self.c1_path).astype(np.float32)
            d2 = tiff.imread(self.c2_path).astype(np.float32)
            if d1.shape != d2.shape: raise ValueError("Mismatch!")
            self.data1, self.data2 = d1, d2
            self.recalc_background()
            
            self.frame_scale.configure(to=self.data1.shape[0]-1)
            self.var_frame.set(0); self.frame_scale.set(0)
            
            self.fig.clear()
            self.ax = self.fig.add_subplot(111); self.ax.axis('off')
            self.im_object = self.ax.imshow(np.zeros((d1.shape[1], d1.shape[2])), cmap="jet")
            
            self.cbar = self.fig.colorbar(self.im_object, ax=self.ax, shrink=0.6, pad=0.02, label='Ratio (C1/C2)')
            self.update_plot()
        except Exception as e: messagebox.showerror("Error", str(e))
        finally: self.root.config(cursor="")

    def get_processed_frame(self, frame_idx):
        if self.data1 is None: return None
        return process_frame_ratio(
            self.data1[frame_idx], self.data2[frame_idx],
            self.cached_bg1, self.cached_bg2,
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
        if self.data1 is None or self.im_object is None: return
        idx = self.var_frame.get()
        img = self.get_processed_frame(idx)
        if img is None: return

        if self.lock_var.get():
            try: vmin, vmax = float(self.entry_vmin.get()), float(self.entry_vmax.get())
            except: vmin, vmax = 0.1, 1.0 
            mode = "Lock"
        else:
            mode = "Auto"
            try:
                if self.log_var.get():
                    valid = img[img > 1e-6]
                    if len(valid) > 0: vmin, vmax = np.nanpercentile(valid, [5, 95])
                    else: vmin, vmax = 0.1, 1.0
                else: vmin, vmax = np.nanpercentile(img, [5, 95])
            except: vmin, vmax = 0, 1
            
            self.entry_vmin.config(state="normal"); self.entry_vmax.config(state="normal")
            self.entry_vmin.delete(0, tk.END); self.entry_vmin.insert(0, f"{vmin:.2f}")
            self.entry_vmax.delete(0, tk.END); self.entry_vmax.insert(0, f"{vmax:.2f}")
            self.entry_vmin.config(state="disabled"); self.entry_vmax.config(state="disabled")

        if self.log_var.get():
            safe_vmin = max(vmin, 0.1)
            safe_vmax = max(vmax, safe_vmin * 1.1) 
            norm = LogNorm(vmin=safe_vmin, vmax=safe_vmax)
        else:
            norm = Normalize(vmin=vmin, vmax=vmax)

        self.im_object.set_data(img)
        self.im_object.set_norm(norm)
        if self.cbar: self.cbar.update_normal(self.im_object)
        self.ax.set_title(f"Frame {idx} | {mode} | {'Log' if self.log_var.get() else 'Linear'}")
        self.canvas.draw_idle()

    def update_cmap(self):
        if self.im_object is None: return
        cmap = plt.get_cmap(self.cmap_var.get()).copy()
        bg = self.bg_color_var.get().lower()
        if bg == "transparent": cmap.set_bad(alpha=0)
        else: cmap.set_bad(bg)
        self.im_object.set_cmap(cmap)
        self.canvas.draw_idle()

    def activate_roi_drawer(self):
        if self.ax is None: return
        if self.roi_selector: 
            self.roi_selector.set_active(True); self.roi_selector.set_visible(True)
            return
        self.roi_selector = RectangleSelector(
            self.ax, self.on_roi_select, useblit=True, button=[1], 
            minspanx=5, minspany=5, spancoords='pixels', interactive=True
        )
        self.canvas.draw()

    def on_roi_mouse_move(self, event):
        if not self.live_plot_var.get() or self.is_calculating_roi: return
        if self.roi_selector and self.roi_selector.active and event.button == 1 and event.inaxes == self.ax:
            try:
                xmin, xmax, ymin, ymax = self.roi_selector.extents
                self.roi_coords = (int(xmin), int(ymin), int(xmax), int(ymax))
                self.plot_roi_curve()
            except: pass

    def clear_roi(self):
        if self.roi_selector: self.roi_selector.set_active(False); self.roi_selector.set_visible(False)
        self.roi_coords = None; self.canvas.draw()

    def on_roi_select(self, eclick, erelease):
        x1, y1, x2, y2 = int(eclick.xdata), int(eclick.ydata), int(erelease.xdata), int(erelease.ydata)
        self.roi_coords = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        if self.live_plot_var.get(): self.plot_roi_curve()

    def plot_roi_curve(self):
        if self.data1 is None or self.roi_coords is None: return
        if self.is_calculating_roi and not self.live_plot_var.get(): return
        
        try: interval = float(self.var_interval.get())
        except: interval = 1.0
        unit = self.combo_unit.get()
        
        self.is_calculating_roi = True
        threading.Thread(target=self.calc_curve_thread, args=(self.roi_coords, interval, unit)).start()

    def calc_curve_thread(self, coords, interval, unit):
        try:
            x1, y1, x2, y2 = coords
            h, w = self.data1.shape[1], self.data1.shape[2]
            x1, x2 = max(0, x1), min(w, x2); y1, y2 = max(0, y1), min(h, y2)
            if x2<=x1 or y2<=y1: return

            d1 = self.data1[:, y1:y2, x1:x2]; d2 = self.data2[:, y1:y2, x1:x2]
            bg1, bg2 = self.cached_bg1, self.cached_bg2
            d1 = np.clip(d1 - bg1, 0, None); d2 = np.clip(d2 - bg2, 0, None)
            
            with np.errstate(divide='ignore', invalid='ignore'):
                r = np.divide(d1, d2); r[d2==0] = np.nan
            
            means = np.nanmean(r, axis=(1, 2))
            mult = 1.0/60.0 if unit == "m" else (1.0/3600.0 if unit == "h" else 1.0)
            times = np.arange(len(means)) * interval * mult
            
            self.root.after(0, self.show_plot_window, times, means, unit)
        finally: self.is_calculating_roi = False

    def show_plot_window(self, x, y, unit):
        # [关键修复]：解决弹窗默认太小和按钮被遮挡的问题
        if self.plot_window is None or not Toplevel.winfo_exists(self.plot_window):
            self.plot_window = Toplevel(self.root)
            self.plot_window.title("ROI Curve")
            
            # 1. 移除硬编码的 Geometry，或者设置得大一点，比如 "600x500"
            self.plot_window.geometry("640x520") 
            self.plot_window.minsize(500, 400)
            self.plot_window.config(bg="#F0F2F5")
            
            # 2. 布局优化：先放置底部的按钮，使用 pack(side="bottom")
            bf = ttk.Frame(self.plot_window, style="White.TFrame", padding=10)
            bf.pack(side="bottom", fill="x")
            
            ttk.Button(bf, text=self.t("btn_copy_all"), command=lambda: self.copy_data(x, y, "all")).pack(side="left", padx=5)
            ttk.Button(bf, text=self.t("btn_copy_y"), command=lambda: self.copy_data(x, y, "y")).pack(side="left", padx=5)

            # 3. 再放置 Canvas
            fig = plt.Figure(figsize=(5, 4), dpi=100)
            self.plot_ax = fig.add_subplot(111)
            fig.patch.set_facecolor('#FFFFFF')
            self.plot_canvas = FigureCanvasTkAgg(fig, master=self.plot_window)
            self.plot_canvas.get_tk_widget().pack(side="top", fill="both", expand=True, padx=10, pady=10)
            
        else:
            pass

        self.plot_ax.clear()
        self.plot_ax.plot(x, y, 'r-', linewidth=1.5)
        self.plot_ax.set_yscale('log' if self.log_var.get() else 'linear')
        self.plot_ax.set_ylabel("Mean Ratio")
        self.plot_ax.set_xlabel(f"Time ({unit})")
        self.plot_ax.grid(True, which="both", alpha=0.5)
        self.plot_canvas.figure.tight_layout()
        self.plot_canvas.draw()
        
        # 强制将弹窗置顶一下
        self.plot_window.lift()

    def copy_data(self, x, y, mode):
        s = "Time\tRatio\n" if mode=="all" else "Ratio\n"
        for i in range(len(y)):
            if mode=="all": s += f"{x[i]:.3f}\t{y[i]:.5f}\n"
            else: s += f"{y[i]:.5f}\n"
        self.root.clipboard_clear(); self.root.clipboard_append(s)
        messagebox.showinfo("OK", "Copied!")

    def save_stack_thread(self):
        if self.data1 is None: return
        threading.Thread(target=self.save_stack_task).start()
    
    def save_stack_task(self):
        try:
            self.ui_elements["btn_save_stack"].config(state="disabled", text="⏳ Saving...")
            ts = datetime.datetime.now().strftime("%H%M%S")
            path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=f"Ratio_Stack_{ts}.tif")
            if not path: return
            
            with tiff.TiffWriter(path, bigtiff=True) as tif:
                for i in range(self.data1.shape[0]):
                    if i%10==0: self.ui_elements["btn_save_stack"].config(text=f"⏳ {i}/{self.data1.shape[0]}")
                    tif.write(self.get_processed_frame(i).astype(np.float32), contiguous=True)
            messagebox.showinfo("OK", f"Saved: {path}")
        except Exception as e: messagebox.showerror("Err", str(e))
        finally: 
            self.ui_elements["btn_save_stack"].config(state="normal", text=self.t("btn_save_stack"))

    def save_current_frame(self):
        if self.data1 is None: return
        path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=f"Ratio_F{self.var_frame.get()}.tif")
        if path: tiff.imwrite(path, self.get_processed_frame(self.var_frame.get()))

    def select_c1(self):
        p = filedialog.askopenfilename()
        if p: self.c1_path = p; self.lbl_c1_path.config(text=os.path.basename(p)); self.check_ready()
    def select_c2(self):
        p = filedialog.askopenfilename()
        if p: self.c2_path = p; self.lbl_c2_path.config(text=os.path.basename(p)); self.check_ready()
    def check_ready(self):
        if self.c1_path and self.c2_path: self.btn_load.config(state="normal")
    
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
        if "Max" in v:
            self.fps = 100
        else:
            try:
                self.fps = int(v.split()[0])
            except:
                self.fps = 10

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
            self.root.after(0, lambda: self.btn_update.config(state="normal"))

    def is_newer_version(self, latest, current):
        def parse_ver(v_str):
            v_clean = v_str.lower().replace("v", "").replace("ver", "")
            try:
                return [int(x) for x in v_clean.split('.')]
            except:
                return [0, 0, 0]
        
        l_list = parse_ver(latest)
        c_list = parse_ver(current)
        return l_list > c_list

    def ask_download(self, version, url):
        msg = self.t("msg_new_ver").format(version)
        if messagebox.askyesno(self.t("title_update"), msg):
            webbrowser.open(url)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("RIA - Ratio Imaging Analyzer")
    app = RatioAnalyzerApp(root)
    root.mainloop()