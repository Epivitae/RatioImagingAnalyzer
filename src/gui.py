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
from PIL import Image, ImageTk

# --- Attempt to import processing logic ---
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

# --- 1. Define Language Map ---
LANG_MAP = {
    "window_title": {"cn": "比率成像分析器 ({})", "en": "Ratio Imaging Analyzer ({})"},
    "header_title": {"cn": "Ratio Imaging Analyzer (RIA)", "en": "Ratio Imaging Analyzer (RIA)"},
    "grp_file": {"cn": "1. 文件加载", "en": "1. File Loading"},
    "btn_c1": {"cn": "📂 通道 1", "en": "📂 Ch1"},
    "btn_c2": {"cn": "📂 通道 2", "en": "📂 Ch2"},
    "btn_load": {"cn": "🚀 加载并分析", "en": "🚀 Load & Analyze"},
    "lbl_no_file": {"cn": "...", "en": "..."},
    "grp_calc": {"cn": "2. 参数计算", "en": "2. Calculation"},
    "lbl_int_thr": {"cn": "强度阈值", "en": "Int. Min"},
    "lbl_ratio_thr": {"cn": "比率阈值", "en": "Ratio Min"},
    "lbl_smooth": {"cn": "平滑 (Smooth)", "en": "Smooth"},
    "lbl_bg": {"cn": "背景扣除 %", "en": "BG %"},
    "chk_log": {"cn": "📈 Log (对数显示)", "en": "📈 Log Scale"},
    "grp_view": {"cn": "3. 显示设置", "en": "3. Display Settings"},
    "lbl_cmap": {"cn": "伪彩:", "en": "Colormap:"},
    "lbl_bg_col": {"cn": "背景色:", "en": "BG Color:"},
    "chk_lock": {"cn": "🔒 锁定范围", "en": "🔒 Lock Range"},
    "btn_apply": {"cn": "应用", "en": "Apply"},
    "lbl_roi_tools": {"cn": "🛠️ ROI & 测量", "en": "🛠️ ROI & Measurement"},
    "lbl_export": {"cn": "💾 数据导出", "en": "💾 Data Export"},
    "lbl_settings": {"cn": "⚙️ 其他设置", "en": "⚙️ Settings"},
    "btn_draw": {"cn": "✏️ 绘制 ROI", "en": "✏️ Draw ROI"},
    "btn_clear": {"cn": "❌ 清除", "en": "❌ Clear"},
    "btn_plot": {"cn": "📈 生成曲线", "en": "📈 Plot Curve"},
    "btn_save_stack": {"cn": "💾 保存序列 (Stack)", "en": "💾 Save Stack"},
    "btn_save_raw": {"cn": "💽 保存原始比值 (Raw)", "en": "💽 Save Raw Ratio"}, 
    "btn_save_frame": {"cn": "📷 保存当前帧", "en": "📷 Save Frame"}, 
    "chk_live": {"cn": "🔴 实时监测 (Live)", "en": "🔴 Live Monitor"},
    "lbl_interval": {"cn": "Imaging Interval (s):", "en": "Imaging Interval (s):"}, 
    "lbl_unit": {"cn": "Plotting Unit:", "en": "Plotting Unit:"},
    "lbl_speed": {"cn": "倍速:", "en": "Speed:"},
    "btn_copy_all": {"cn": "📋 复制全部数据", "en": "📋 Copy All"},
    "btn_copy_y": {"cn": "🔢 仅复制 Ratio", "en": "🔢 Copy Ratio"},
    "btn_check_update": {"cn": "🔄 检查更新", "en": "🔄 Check Update"},
    "btn_contact": {"cn": "📧 联系作者", "en": "📧 Contact Author"},
    "msg_uptodate": {"cn": "当前已是最新版本！", "en": "You are up to date!"},
    "msg_new_ver": {"cn": "发现新版本: {}\n是否前往下载？", "en": "New version found: {}\nGo to download page?"},
    "title_update": {"cn": "版本更新", "en": "Update Check"},
    "err_check": {"cn": "检查更新失败: ", "en": "Check failed: "},
}

# --- 2. Define ToggledFrame Class ---
class ToggledFrame(ttk.Frame):
    def __init__(self, parent, text="", *args, **options):
        # Default to Card style unless specified
        if "style" not in options:
            options["style"] = "Card.TFrame"
            
        ttk.Frame.__init__(self, parent, *args, **options)
        
        self.show = tk.IntVar()
        self.show.set(0)
        
        self.title_frame = ttk.Frame(self, style="Card.TFrame")
        self.title_frame.pack(fill="x", expand=1)
        
        self.toggle_btn = ttk.Checkbutton(
            self.title_frame, 
            width=2, 
            text='▶', 
            command=self.toggle, 
            variable=self.show, 
            style='Toolbutton'
        )
        self.toggle_btn.pack(side="left")
        
        self.lbl_title = ttk.Label(self.title_frame, text=text, style="Blue.TLabel")
        self.lbl_title.pack(side="left", padx=5)
        
        self.sub_frame = ttk.Frame(self, relief="flat", borderwidth=0, padding=5, style="Card.TFrame")

    def toggle(self):
        if self.show.get():
            self.sub_frame.pack(fill="x", expand=1, pady=(2,0))
            self.toggle_btn.configure(text='▼')
        else:
            self.sub_frame.forget()
            self.toggle_btn.configure(text='▶')


class RatioAnalyzerApp:
    def __init__(self, root):
        self.root = root
        
        # --- 1. Initialize core font objects ---
        self.base_font_size = 10
        self.current_font_size = self.base_font_size
        
        # Define dynamic font objects
        self.f_normal = tkfont.Font(family="Segoe UI", size=self.base_font_size)
        self.f_bold = tkfont.Font(family="Segoe UI", size=self.base_font_size, weight="bold")
        self.f_title = tkfont.Font(family="Helvetica", size=self.base_font_size + 8, weight="bold")
        
        # Take over system fonts
        self.default_tk_font = tkfont.nametofont("TkDefaultFont")
        self.text_tk_font = tkfont.nametofont("TkTextFont")
        self.caption_tk_font = tkfont.nametofont("TkCaptionFont")

        self._resize_timer = None

        # --- Style initialization ---
        self.setup_theme()
        
        self.VERSION = __version__
        self.current_lang = "en" # Default to English
        self.ui_elements = {}
        self.root.geometry("1280x850")
        self.root.configure(bg="#F0F2F5") 
        
        self.root.minsize(1000, 600)
        
        # --- Icon Loading (Window & Taskbar) ---
        try:
            icon_path = self.get_asset_path("ratiofish.ico")
            if os.path.exists(icon_path):
                # Using iconbitmap is best for Windows as it supports multi-size icons (16/32/48/256)
                self.root.iconbitmap(default=icon_path) 
        except Exception as e:
            print(f"Warning: Failed to load icon: {e}")

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
        
        self.change_font_size(0)

    def setup_theme(self):
        """Configure modern flat theme and bind dynamic fonts."""
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except:
            pass
            
        BG_COLOR = "#F0F2F5"
        CARD_COLOR = "#FFFFFF"
        TEXT_COLOR = "#333333"
        BLUE_COLOR = "#0056b3"
        
        # --- Global font binding ---
        style.configure(".", background=BG_COLOR, foreground=TEXT_COLOR, font=self.f_normal)
        style.configure("TLabel", background=BG_COLOR, font=self.f_normal)
        style.configure("TButton", padding=4, font=self.f_normal)
        style.configure("TCheckbutton", font=self.f_normal)
        style.configure("TRadiobutton", font=self.f_normal)
        style.configure("TEntry", font=self.f_normal)
        style.configure("TCombobox", font=self.f_normal)
        
        # --- Custom Styles ---
        style.configure("Card.TFrame", background=CARD_COLOR, relief="flat")
        style.configure("Card.TLabelframe", background=CARD_COLOR, relief="solid", borderwidth=1)
        style.configure("Card.TLabelframe.Label", background=CARD_COLOR, foreground=BLUE_COLOR, font=self.f_bold)
        style.configure("Header.TFrame", background=CARD_COLOR)
        style.configure("White.TLabel", background=CARD_COLOR, font=self.f_normal)
        style.configure("White.TCheckbutton", background=CARD_COLOR, font=self.f_normal)
        style.configure("White.TRadiobutton", background=CARD_COLOR, font=self.f_normal)
        style.configure("White.TFrame", background=CARD_COLOR)
        style.configure("Blue.TLabel", foreground=BLUE_COLOR, font=self.f_bold)

        # --- Modern Toggle Button Style ---
        style.configure("Toggle.TButton", font=self.f_normal, background="#FFFFFF", borderwidth=1)
        style.map("Toggle.TButton",
            background=[("selected", "#E8F0FE"), ("active", "#F5F5F5")], 
            foreground=[("selected", BLUE_COLOR)],
            relief=[("selected", "sunken"), ("!selected", "raised")]
        )

        # --- GitHub Star Style (Gold) ---
        style.configure("Starred.TButton", font=self.f_normal, foreground="#F5C518")
        
        # --- Compact Button Style ---
        style.configure("Compact.TButton", font=self.f_normal, padding=(2, 0))

        # --- Gray Button Style (for less common actions) ---
        style.configure("Gray.TButton", font=self.f_normal, background="#E0E0E0", foreground="#555555")
        style.map("Gray.TButton",
            background=[("active", "#D5D5D5"), ("pressed", "#C0C0C0")], 
            foreground=[("active", "#333333")]
        )
        
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
        new_size = self.current_font_size + delta
        if new_size < 8: new_size = 8
        if new_size > 24: new_size = 24
        self.current_font_size = new_size
        
        self.f_normal.configure(size=new_size)
        self.f_bold.configure(size=new_size)
        self.f_title.configure(size=new_size + 8)
        self.default_tk_font.configure(size=new_size)
        self.text_tk_font.configure(size=new_size)
        self.caption_tk_font.configure(size=new_size, weight="bold")
        
        self.style.configure(".", font=self.f_normal)
        self.style.configure("TButton", font=self.f_normal)
        self.style.configure("Toggle.TButton", font=self.f_normal)
        self.style.configure("Starred.TButton", font=self.f_normal)
        self.style.configure("Compact.TButton", font=self.f_normal)
        self.style.configure("Gray.TButton", font=self.f_normal) 
        self.style.configure("Card.TLabelframe.Label", font=self.f_bold) 
        self.style.configure("Blue.TLabel", font=self.f_bold)
        
        self.root.update_idletasks()

    def reset_font_size(self):
        delta = self.base_font_size - self.current_font_size
        self.change_font_size(delta)

    def on_canvas_configure(self, event):
        if self._resize_timer is not None:
            self.root.after_cancel(self._resize_timer)
        self._resize_timer = self.root.after(50, lambda: self._perform_resize(event))

    def _perform_resize(self, event):
        if self.canvas:
            self.canvas.resize(event)
            self._resize_timer = None

    def star_github(self):
        webbrowser.open("https://github.com/Epivitae/RatioImagingAnalyzer")
        self.btn_github.config(text="★ GitHub", style="Starred.TButton")

    def setup_ui(self):
        header = ttk.Frame(self.root, padding="15 10", style="Header.TFrame")
        header.pack(fill="x")
        
        sep = tk.Frame(self.root, bg="#ddd", height=1)
        sep.pack(fill="x")
        
        self.lbl_title = ttk.Label(header, text="RIA", font=self.f_title, background="#FFFFFF", foreground="#2c3e50")
        self.lbl_title.pack(side="left")
        self.ui_elements["header_title"] = self.lbl_title

        # --- Top Button Area Layout ---
        btn_frame = ttk.Frame(header, style="Header.TFrame")
        btn_frame.pack(side="right")
        
        # 1. Right: Font controls
        ttk.Button(btn_frame, text="A+", width=3, command=lambda: self.change_font_size(1)).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="⟳", width=3, command=self.reset_font_size).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="A-", width=3, command=lambda: self.change_font_size(-1)).pack(side="right", padx=2)
        
        # 2. Middle: GitHub Link
        self.btn_github = ttk.Button(btn_frame, text="☆ GitHub", command=self.star_github)
        self.btn_github.pack(side="right", padx=10)
        
        # 3. Left: Language Switch [Fixed]
        ttk.Button(btn_frame, text="🌐 EN/中文", command=self.toggle_language).pack(side="right", padx=2)

        footer = tk.Frame(self.root, bg="#F0F2F5", height=25)
        footer.pack(side="bottom", fill="x")
        ttk.Label(footer, text=f"© Dr. Kui Wang | {self.VERSION} | k@cns.ac.cn | www.cns.ac.cn", font=("Arial", 10), foreground="#888").pack(pady=5)

        self.main_pane = ttk.PanedWindow(self.root, orient="horizontal")
        self.main_pane.pack(fill="both", expand=True, padx=10, pady=10)

        # === Left Panel ===
        self.frame_left_container = ttk.Frame(self.main_pane, style="Card.TFrame", padding=10)
        self.main_pane.add(self.frame_left_container, weight=0)
        
        self.frame_left = ttk.Frame(self.frame_left_container, width=320, style="White.TFrame")
        self.frame_left.pack(fill="both", expand=True)

        self.grp_file = ttk.LabelFrame(self.frame_left, padding=10, style="Card.TLabelframe")
        self.grp_file.pack(fill="x", pady=(0, 10))
        self.ui_elements["grp_file"] = self.grp_file
        
        self.create_compact_file_row(self.grp_file, "btn_c1", self.select_c1, "lbl_c1_path")
        self.create_compact_file_row(self.grp_file, "btn_c2", self.select_c2, "lbl_c2_path")
        self.btn_load = ttk.Button(self.grp_file, command=self.load_data, state="disabled")
        self.btn_load.pack(fill="x", pady=5)
        self.ui_elements["btn_load"] = self.btn_load

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
        self.chk_log = ttk.Checkbutton(self.grp_calc, variable=self.log_var, command=self.update_plot, style="Toggle.TButton")
        self.chk_log.pack(fill="x", pady=2) 
        self.ui_elements["chk_log"] = self.chk_log

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

        # --- Bottom Brand Logo (Using PIL for high-quality scaling) ---
        self.fr_brand = ttk.Frame(self.frame_left, style="White.TFrame")
        self.fr_brand.pack(side="bottom", fill="x", pady=(30, 10))

        inner_box = ttk.Frame(self.fr_brand, style="White.TFrame")
        inner_box.pack(anchor="center")

        try:
            icon_path = self.get_asset_path("ratiofish.ico")
            if os.path.exists(icon_path):
                # Use PIL to read and resize
                pil_img = Image.open(icon_path)
                
                # Resize icon to 64x64 for better visibility
                icon_size = 64
                pil_img = pil_img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                
                self.brand_icon_img = ImageTk.PhotoImage(pil_img)
                
                # Icon on top
                lbl_ico = ttk.Label(inner_box, image=self.brand_icon_img, style="White.TLabel")
                lbl_ico.pack(side="top", pady=(0, 5)) 
        except Exception as e:
            print(f"Brand icon load error: {e}")

        # Brand Text on bottom
        lbl_brand = ttk.Label(
            inner_box, 
            text="RIA 莉丫", 
            font=("Microsoft YaHei UI", 12, "bold"), 
            foreground="#0056b3",
            style="White.TLabel"
        )
        lbl_brand.pack(side="top")

        # === Right Panel ===
        self.frame_right = ttk.Frame(self.main_pane, style="Card.TFrame", padding=10)
        self.main_pane.add(self.frame_right, weight=1)

        self.plot_container = ttk.Frame(self.frame_right, style="White.TFrame")
        self.fig = plt.Figure(figsize=(6, 5), dpi=100)
        self.fig.patch.set_facecolor('#FFFFFF') 
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_container)
        self.canvas.mpl_connect('motion_notify_event', self.on_roi_mouse_move)

        tk_canvas_widget = self.canvas.get_tk_widget()
        tk_canvas_widget.unbind("<Configure>")
        tk_canvas_widget.bind("<Configure>", self.on_canvas_configure)

        self.create_bottom_panel(self.frame_right)

        self.plot_container.pack(side="top", fill="both", expand=True)
        tk_canvas_widget.pack(fill="both", expand=True)

    def create_bottom_panel(self, parent):
        bottom_area = ttk.Frame(parent, padding=(0, 10, 0, 0), style="White.TFrame")
        bottom_area.pack(fill="x", side="bottom")

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
        
        tb_frame = ttk.Frame(row_ctl, style="White.TFrame"); tb_frame.pack(side="right")
        self.toolbar = NavigationToolbar2Tk(self.canvas, tb_frame)
        self.toolbar.config(background="#FFFFFF") 
        self.toolbar._message_label.config(background="#FFFFFF")
        self.toolbar.update()

        grid_area = ttk.Frame(bottom_area, style="White.TFrame")
        grid_area.pack(fill="x", expand=True)
        
        grid_area.columnconfigure(0, weight=2)
        grid_area.columnconfigure(1, weight=1)
        grid_area.columnconfigure(2, weight=1)

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
        self.chk_live = ttk.Checkbutton(fr_roi, variable=self.live_plot_var, style="Toggle.TButton")
        self.chk_live.grid(row=1, column=1, padx=2, pady=2, sticky="ew") 
        self.ui_elements["chk_live"] = self.chk_live

        f_time = ttk.Frame(fr_roi, style="White.TFrame")
        f_time.grid(row=2, column=0, columnspan=2, sticky="ew", padx=2, pady=5)
        
        f_time.columnconfigure(0, weight=1)
        f_time.columnconfigure(1, weight=1)
        
        # Left: Interval
        f_left = ttk.Frame(f_time, style="White.TFrame")
        f_left.grid(row=0, column=0)
        self.lbl_int = ttk.Label(f_left, text="Imaging Interval (s):", style="White.TLabel") 
        self.lbl_int.pack(side="left")
        self.ui_elements["lbl_interval"] = self.lbl_int
        self.var_interval = tk.DoubleVar(value=1.0)
        ttk.Entry(f_left, textvariable=self.var_interval, width=5, justify='center').pack(side="left", padx=2)
        
        # Right: Unit
        f_right = ttk.Frame(f_time, style="White.TFrame")
        f_right.grid(row=0, column=1)
        self.lbl_unit = ttk.Label(f_right, text="Plotting Unit:", style="White.TLabel")
        self.lbl_unit.pack(side="left")
        self.ui_elements["lbl_unit"] = self.lbl_unit
        self.combo_unit = ttk.Combobox(f_right, values=["s", "m", "h"], width=3, state="readonly")
        self.combo_unit.set("s"); self.combo_unit.pack(side="left", padx=2)

        fr_roi.columnconfigure(0, weight=1)
        fr_roi.columnconfigure(1, weight=1)

        fr_exp = ttk.LabelFrame(grid_area, padding=5, style="Card.TLabelframe")
        fr_exp.grid(row=0, column=1, sticky="nsew", padx=5)
        self.ui_elements["lbl_export"] = fr_exp
        
        self.btn_save_frame = ttk.Button(fr_exp, command=self.save_current_frame)
        self.btn_save_frame.pack(fill="x", pady=2)
        self.ui_elements["btn_save_frame"] = self.btn_save_frame
        
        self.btn_save_stack = ttk.Button(fr_exp, command=self.save_stack_thread)
        self.btn_save_stack.pack(fill="x", pady=2)
        self.ui_elements["btn_save_stack"] = self.btn_save_stack
        
        # Save Raw Ratio Button
        self.btn_save_raw = ttk.Button(fr_exp, command=self.save_raw_thread, style="Gray.TButton")
        self.btn_save_raw.pack(fill="x", pady=2)
        self.ui_elements["btn_save_raw"] = self.btn_save_raw

        fr_set = ToggledFrame(grid_area, text="Settings", style="Card.TFrame")
        fr_set.grid(row=0, column=2, sticky="new", padx=(5, 0))
        self.ui_elements["lbl_settings"] = fr_set.lbl_title
        
        self.btn_update = ttk.Button(fr_set.sub_frame, command=self.check_update_thread)
        self.btn_update.pack(fill="x", pady=2)
        self.ui_elements["btn_check_update"] = self.btn_update
        
        self.btn_contact = ttk.Button(fr_set.sub_frame, command=lambda: webbrowser.open("https://www.cns.ac.cn"))
        self.btn_contact.pack(fill="x", pady=2)
        self.ui_elements["btn_contact"] = self.btn_contact

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
            
            if self.data1 is not None:
                try:
                    self.root.config(cursor="watch")
                    self.root.update()
                    
                    bg1, bg2 = self.cached_bg1, self.cached_bg2
                    int_th, ratio_th = self.var_int_thresh.get(), self.var_ratio_thresh.get()
                    is_log = self.log_var.get()
                    
                    g_min, g_max = np.inf, -np.inf
                    
                    for i in range(len(self.data1)):
                        f1 = np.clip(self.data1[i] - bg1, 0, None)
                        f2 = np.clip(self.data2[i] - bg2, 0, None)
                        
                        mask = (f1 < int_th) | (f2 < int_th)
                        
                        with np.errstate(divide='ignore', invalid='ignore'):
                            ratio = np.divide(f1, f2)
                            ratio[f2 == 0] = np.nan
                            ratio[f1 == 0] = 0
                        
                        ratio[mask] = np.nan
                        if ratio_th > 0: ratio[ratio < ratio_th] = np.nan
                        if is_log: ratio = np.log1p(ratio)
                        
                        valid_pixels = ratio[~np.isnan(ratio)]
                        if valid_pixels.size > 0:
                            p1, p99 = np.percentile(valid_pixels, [1, 99])
                            if p1 < g_min: g_min = p1
                            if p99 > g_max: g_max = p99
                            
                    if g_min != np.inf and g_max != -np.inf:
                        self.entry_vmin.delete(0, tk.END)
                        self.entry_vmin.insert(0, f"{g_min:.2f}")
                        self.entry_vmax.delete(0, tk.END)
                        self.entry_vmax.insert(0, f"{g_max:.2f}")
                        
                except Exception as e:
                    print(f"Auto range error: {e}")
                finally:
                    self.root.config(cursor="")
            
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
        
        if bg == "transparent" or bg == "trans": 
            cmap.set_bad(alpha=0)
        else: 
            cmap.set_bad(bg)
            
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
        
        self.live_plot_var.set(True)
        
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
        if self.plot_window is None or not Toplevel.winfo_exists(self.plot_window):
            self.plot_window = Toplevel(self.root)
            self.plot_window.title("ROI Curve")
            self.plot_window.geometry("640x520") 
            self.plot_window.minsize(500, 400)
            self.plot_window.config(bg="#F0F2F5")
            
            try:
                icon_path = self.get_asset_path("ratiofish.ico")
                if os.path.exists(icon_path):
                    self.plot_window.iconbitmap(icon_path)
            except: pass
            
            bf = ttk.Frame(self.plot_window, style="White.TFrame", padding=10)
            bf.pack(side="bottom", fill="x")
            
            ttk.Button(bf, text=self.t("btn_copy_all"), command=lambda: self.copy_data(x, y, "all")).pack(side="left", padx=5)
            ttk.Button(bf, text=self.t("btn_copy_y"), command=lambda: self.copy_data(x, y, "y")).pack(side="left", padx=5)

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

    def save_raw_thread(self):
        if self.data1 is None: return
        threading.Thread(target=self.save_raw_task).start()

    def save_raw_task(self):
        try:
            self.ui_elements["btn_save_raw"].config(state="disabled", text="⏳ Saving...")
            ts = datetime.datetime.now().strftime("%H%M%S")
            path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=f"Raw_Ratio_Stack_{ts}.tif")
            if not path: return
            
            with tiff.TiffWriter(path, bigtiff=True) as tif:
                for i in range(self.data1.shape[0]):
                    if i%10==0: self.ui_elements["btn_save_raw"].config(text=f"⏳ {i}/{self.data1.shape[0]}")
                    
                    # Compute raw ratio without processing
                    d1 = self.data1[i].astype(np.float32)
                    d2 = self.data2[i].astype(np.float32)
                    with np.errstate(divide='ignore', invalid='ignore'):
                        ratio = np.divide(d1, d2)
                        ratio[d2 == 0] = np.nan
                        
                    tif.write(ratio, contiguous=True)
                    
            messagebox.showinfo("OK", f"Saved Raw Ratio: {path}")
        except Exception as e: messagebox.showerror("Err", str(e))
        finally: 
            self.ui_elements["btn_save_raw"].config(state="normal", text=self.t("btn_save_raw"))

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