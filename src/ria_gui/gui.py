import tkinter as tk
from tkinter import filedialog, messagebox, ttk, Toplevel
import tkinter.font as tkfont
import numpy as np
import os
import sys
import warnings
import datetime
import threading
import requests
import webbrowser
import json
from typing import List, Optional
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from mpl_toolkits.axes_grid1 import make_axes_locatable


# --- Import Components ---
try:
    from .constants import LANG_MAP
    from .components import ToggledFrame
    from .io_utils import read_and_split_multichannel, read_separate_files 
    from .gui_components import PlotManager, RoiManager
    from .model import AnalysisSession

except ImportError:
    try:
        from constants import LANG_MAP
        from components import ToggledFrame
        from io_utils import read_and_split_multichannel, read_separate_files
        from gui_components import PlotManager, RoiManager
        from model import AnalysisSession

    except ImportError as e:
        print(f"Import Error: {e}. Ensure all modules exist.")

try:
    from ._version import __version__
except ImportError:
    try:
        from _version import __version__
    except:
        __version__ = "1.0.0"

warnings.filterwarnings('ignore')


# src/gui.py (KymographWindow 部分)

class KymographWindow:
    def __init__(self, master, roi_id, app, title="Kymograph"):
        self.window = Toplevel(master)
        self.window.title(f"{title} - ROI {roi_id}")
        self.window.geometry("700x650")
        self.roi_id = roi_id
        self.app = app
        
        self.is_open = True
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # --- Data Cache ---
        self.raw_data = None
        
        # --- UI Variables ---
        self.var_um_px = tk.DoubleVar(value=1.0)
        self.var_s_frame = tk.DoubleVar(value=1.0)
        self.var_frame_start = tk.IntVar(value=0)
        self.var_frame_end = tk.IntVar(value=0)
        self.var_auto_range = tk.BooleanVar(value=True)
        self.var_cmap = tk.StringVar(value="jet")
        self.var_log = tk.BooleanVar(value=False)

        # --- Layout ---
        # 1. Plot Area
        plot_frame = ttk.Frame(self.window)
        plot_frame.pack(side="top", fill="both", expand=True)
        
        self.fig = plt.Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
        
        self.toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        self.toolbar.update()
        
        self.im_obj = None 
        self.cbar = None
        self.cax = None # [新增] 专门用于存放 Colorbar 的坐标轴，防止主图缩小

        # 2. Control Panel
        ctrl_panel = ttk.Frame(self.window, padding=5, style="Card.TFrame")
        ctrl_panel.pack(side="bottom", fill="x")
        
        self._setup_controls(ctrl_panel)
        
        self.apply_theme()


    def _setup_controls(self, parent):
        # 初始化变量
        if not hasattr(self, 'var_plot_font_size'): self.var_plot_font_size = tk.IntVar(value=10)
        if not hasattr(self, 'var_dist_start'): self.var_dist_start = tk.IntVar(value=0)
        if not hasattr(self, 'var_dist_end'): self.var_dist_end = tk.IntVar(value=0)

        P_OPTS = {'side': 'left', 'fill': 'both', 'expand': True, 'padx': 2}
        
        # =========================================================
        # Module 1: Calibration
        # =========================================================
        fr_calib = ttk.LabelFrame(parent, text="📏 Calib", padding=5, style="Card.TLabelframe")
        fr_calib.pack(**P_OPTS)
        
        f1 = ttk.Frame(fr_calib, style="Card.TFrame"); f1.pack(fill="x", pady=(0, 2))
        ttk.Label(f1, text="Dist:", width=4, style="White.TLabel").pack(side="left")
        ttk.Entry(f1, textvariable=self.var_um_px, width=5).pack(side="left")
        ttk.Label(f1, text="µm", style="White.TLabel").pack(side="left", padx=(2,0))
        
        f2 = ttk.Frame(fr_calib, style="Card.TFrame"); f2.pack(fill="x")
        ttk.Label(f2, text="Time:", width=4, style="White.TLabel").pack(side="left")
        ttk.Entry(f2, textvariable=self.var_s_frame, width=5).pack(side="left")
        ttk.Label(f2, text="s", style="White.TLabel").pack(side="left", padx=(2,0))
        
        parent.bind_all("<Return>", lambda e: self.refresh_plot())

        # =========================================================
        # Module 2: Range (布局优化：左边输入框，右边居中按钮)
        # =========================================================
        fr_range = ttk.LabelFrame(parent, text="🔍 Range", padding=5, style="Card.TLabelframe")
        fr_range.pack(**P_OPTS)
        
        # Top: Auto Toggle
        self.chk_auto = ttk.Checkbutton(fr_range, text="Auto / Full", variable=self.var_auto_range, 
                                        command=self._toggle_range_inputs, style="Toggle.TButton")
        self.chk_auto.pack(fill="x", pady=(0, 5))
        
        # Main Container: Left (Inputs) + Right (Button)
        f_main = ttk.Frame(fr_range, style="Card.TFrame")
        f_main.pack(fill="both", expand=True)

        # -- Left Column: Y and X Inputs --
        f_inputs = ttk.Frame(f_main, style="Card.TFrame")
        f_inputs.pack(side="left")

        # Y Row
        f_y = ttk.Frame(f_inputs, style="Card.TFrame"); f_y.pack(fill="x", pady=(0, 4)) # 稍微增加一点行间距
        ttk.Label(f_y, text="Y:", width=2, style="White.TLabel").pack(side="left")
        self.ent_start = ttk.Entry(f_y, textvariable=self.var_frame_start, width=4)
        self.ent_start.pack(side="left")
        ttk.Label(f_y, text="-", style="White.TLabel").pack(side="left")
        self.ent_end = ttk.Entry(f_y, textvariable=self.var_frame_end, width=4)
        self.ent_end.pack(side="left")

        # X Row
        f_x = ttk.Frame(f_inputs, style="Card.TFrame"); f_x.pack(fill="x")
        ttk.Label(f_x, text="X:", width=2, style="White.TLabel").pack(side="left")
        self.ent_dist_start = ttk.Entry(f_x, textvariable=self.var_dist_start, width=4)
        self.ent_dist_start.pack(side="left")
        ttk.Label(f_x, text="-", style="White.TLabel").pack(side="left")
        self.ent_dist_end = ttk.Entry(f_x, textvariable=self.var_dist_end, width=4)
        self.ent_dist_end.pack(side="left")
        
        # -- Right Column: Go Button (Vertically Centered) --
        # anchor="center" 让按钮在垂直方向居中
        ttk.Button(f_main, text="Go", command=self.refresh_plot, width=3, style="Compact.TButton")\
            .pack(side="left", padx=(6, 0), anchor="center")

        # =========================================================
        # Module 3: View
        # =========================================================
        fr_look = ttk.LabelFrame(parent, text="🎨 View", padding=5, style="Card.TLabelframe")
        fr_look.pack(**P_OPTS)
        ttk.Checkbutton(fr_look, text="Log Scale", variable=self.var_log, 
                        command=self.refresh_plot, style="Toggle.TButton").pack(fill="x", pady=(0, 5))
        cmap_opts = ["jet", "coolwarm", "viridis", "magma", "gray", "inferno"]
        self.combo_cmap = ttk.Combobox(fr_look, textvariable=self.var_cmap, values=cmap_opts, 
                                       state="readonly", justify="center")
        self.combo_cmap.bind("<<ComboboxSelected>>", lambda e: self.refresh_plot())
        self.combo_cmap.pack(fill="x")

        # =========================================================
        # Module 4: Font
        # =========================================================
        fr_font = ttk.LabelFrame(parent, text="Aᴀ Font", padding=5, style="Card.TLabelframe")
        fr_font.pack(**P_OPTS)

        def change_font(delta):
            v = self.var_plot_font_size.get() + delta
            if v < 6: v = 6
            if v > 30: v = 30
            self.var_plot_font_size.set(v)
            self.refresh_plot()

        f_val = ttk.Frame(fr_font, style="Card.TFrame"); f_val.pack(fill="x", pady=(0, 5))
        ttk.Label(f_val, text="Size:", style="White.TLabel").pack(side="left", padx=(2,0))
        self.lbl_font_val = ttk.Label(f_val, textvariable=self.var_plot_font_size, 
                                      font=("Segoe UI", 9, "bold"), foreground="#0056b3", style="White.TLabel")
        self.lbl_font_val.pack(side="right", padx=(0,5))

        f_btns = ttk.Frame(fr_font, style="Card.TFrame"); f_btns.pack(fill="x")
        ttk.Button(f_btns, text="A-", width=4, command=lambda: change_font(-1), style="Compact.TButton").pack(side="left", fill="x", expand=True, padx=(0, 1))
        ttk.Button(f_btns, text="A+", width=4, command=lambda: change_font(1), style="Compact.TButton").pack(side="left", fill="x", expand=True, padx=(1, 0))

    def _toggle_range_inputs(self):
        # [修改] 同时控制 Y轴 和 X轴 输入框的开关
        state = "disabled" if self.var_auto_range.get() else "normal"
        self.ent_start.config(state=state)
        self.ent_end.config(state=state)
        
        if hasattr(self, 'ent_dist_start'):
            self.ent_dist_start.config(state=state)
            self.ent_dist_end.config(state=state)
            
        self.refresh_plot()

    # ✅ [新增] 1. 获取当前窗口的所有设置
    def get_settings(self):
        return {
            "roi_id": self.roi_id,
            "um_px": self.var_um_px.get(),
            "s_frame": self.var_s_frame.get(),
            "frame_start": self.var_frame_start.get(),
            "frame_end": self.var_frame_end.get(),
            "auto_range": self.var_auto_range.get(),
            "cmap": self.var_cmap.get(),
            "log_scale": self.var_log.get(),
            "font_size": self.var_plot_font_size.get() if hasattr(self, 'var_plot_font_size') else 10,
            # 如果有 x 轴范围也加上
            "dist_start": self.var_dist_start.get() if hasattr(self, 'var_dist_start') else 0,
            "dist_end": self.var_dist_end.get() if hasattr(self, 'var_dist_end') else 0,
        }

    # ✅ [新增] 2. 应用设置
    def apply_settings(self, s):
        if not s: return
        self.var_um_px.set(s.get("um_px", 1.0))
        self.var_s_frame.set(s.get("s_frame", 1.0))
        self.var_frame_start.set(s.get("frame_start", 0))
        self.var_frame_end.set(s.get("frame_end", 0))
        self.var_auto_range.set(s.get("auto_range", True))
        self.var_cmap.set(s.get("cmap", "jet"))
        self.var_log.set(s.get("log_scale", False))
        
        if hasattr(self, 'var_plot_font_size'):
            self.var_plot_font_size.set(s.get("font_size", 10))
            
        if hasattr(self, 'var_dist_start'):
            self.var_dist_start.set(s.get("dist_start", 0))
            self.var_dist_end.set(s.get("dist_end", 0))
            
        # 刷新一下界面状态（比如 Auto 勾选后的输入框灰度）
        self._toggle_range_inputs()

    def refresh_plot(self):
        if not self.is_open or self.raw_data is None: return
        data = self.raw_data
        h, w = data.shape 
        
        # [核心逻辑] Auto 模式下，自动重置 X 和 Y 的变量为最大范围
        if self.var_auto_range.get():
            self.var_frame_start.set(0)
            self.var_frame_end.set(h)
            if hasattr(self, 'var_dist_start'):
                self.var_dist_start.set(0)
                self.var_dist_end.set(w)

        # 参数读取
        try: um_px = float(self.var_um_px.get())
        except: um_px = 1.0
        try: s_frame = float(self.var_s_frame.get())
        except: s_frame = 1.0
        try: font_size = self.var_plot_font_size.get()
        except: font_size = 10
        
        max_dist = w * um_px
        max_time = h * s_frame
        extent = [0, max_dist, max_time, 0] 

        from matplotlib.colors import LogNorm, Normalize
        vmin, vmax = np.nanmin(data), np.nanmax(data)
        if self.var_log.get():
            safe_min = max(vmin, 1e-6) if vmin > 0 else 1e-6
            norm = LogNorm(vmin=safe_min, vmax=max(vmax, safe_min * 10))
        else:
            norm = Normalize(vmin=vmin, vmax=vmax)

        self.ax.clear()
        self.im_obj = self.ax.imshow(
            data, aspect='auto', cmap=self.var_cmap.get(), norm=norm, extent=extent, origin='upper'
        )
        
        dist_unit = 'µm' if um_px != 1.0 else 'px'
        self.ax.set_xlabel(f"Distance ({dist_unit})", fontsize=font_size)
        self.ax.set_ylabel("Time (s)", fontsize=font_size)
        self.ax.tick_params(axis='both', labelsize=font_size)
        
        # [核心逻辑] 应用手动范围
        if not self.var_auto_range.get():
            # 1. 应用 Y 轴 (Time)
            try:
                t_start = self.var_frame_start.get() * s_frame
                t_end = self.var_frame_end.get() * s_frame
                self.ax.set_ylim(t_end, t_start) 
            except: pass
            
            # 2. 应用 X 轴 (Distance)
            try:
                # 假设输入的是像素索引 (与 Y 轴的 Frame 索引逻辑保持一致)
                d_start = self.var_dist_start.get() * um_px
                d_end = self.var_dist_end.get() * um_px
                self.ax.set_xlim(d_start, d_end)
            except: pass

        if self.cax is None:
            divider = make_axes_locatable(self.ax)
            self.cax = divider.append_axes("right", size="5%", pad=0.05)
        self.cax.clear()
        self.cbar = self.fig.colorbar(self.im_obj, cax=self.cax)
        self.cbar.ax.tick_params(labelsize=font_size)
        
        try: self.fig.tight_layout(pad=1.2)
        except: pass
        self.apply_theme()





    def on_close(self):
        self.is_open = False
        self.window.destroy()

    def apply_theme(self):
        if not self.window.winfo_exists(): return
        try:
            mode = self.app.current_theme
            c = self.app.THEME_COLORS[mode]
            bg, fg = c["plot_bg"], c["plot_fg"]
            
            self.window.configure(bg=c["bg"])
            self.fig.patch.set_facecolor(bg)
            self.ax.set_facecolor(bg)
            
            for spine in self.ax.spines.values(): spine.set_color(fg)
            self.ax.xaxis.label.set_color(fg)
            self.ax.yaxis.label.set_color(fg)
            self.ax.tick_params(axis='both', colors=fg)
            self.ax.title.set_color(fg)
            
            # [修改] 对 Colorbar 的处理更安全
            if self.cbar:
                self.cbar.ax.yaxis.set_tick_params(color=fg, labelcolor=fg)
                self.cbar.set_label(self.cbar.ax.get_ylabel(), color=fg)
            
            if self.toolbar:
                tb_bg = c.get("toolbar_bg", "#F0F0F0")
                self.toolbar.config(background=tb_bg)
                self.toolbar._message_label.config(background=tb_bg, foreground="black")

            self.canvas.draw_idle()
        except Exception as e: print(f"Kymo Theme Error: {e}")

    def update_data(self, data, is_log=False):
        if not self.is_open: return
        self.raw_data = data
        if self.var_auto_range.get():
            self.var_frame_start.set(0)
            self.var_frame_end.set(data.shape[0])
        if self.var_log.get() != is_log:
            self.var_log.set(is_log)
        self.refresh_plot()


class RatioAnalyzerApp:
    def __init__(self, root, startup_file=None):
        self.root = root
        self.current_theme = "light"

        # [新增] 定义两套颜色方案
        self.THEME_COLORS = {
            "light": {
                "bg": "#F0F2F5", 
                "card": "#FFFFFF", 
                "text": "#000000",             # 白天：纯黑文字
                "fg_disabled": "#A0A0A0",
                "input_bg": "#FFFFFF",
                "accent": "#0056b3",           # 白天：深蓝强调
                "plot_bg": "#FFFFFF", 
                "plot_fg": "#000000",
                "toolbar_bg": "#F0F0F0"
            },
            "dark": {
                "bg": "#2D2D2D",               # 深灰背景
                "card": "#383838",             # 卡片背景
                "text": "#FFFFFF",             # [核心修改] 纯白文字 (对比度最高)
                "fg_disabled": "#AAAAAA",      # [核心修改] 亮灰禁用字 (防止看不清)
                "input_bg": "#454545",         # 输入框背景
                "accent": "#4DA6FF",           # 亮蓝强调 (保持蓝色定义)
                "plot_bg": "#383838",          # 绘图背景
                "plot_fg": "#FFFFFF",          # [核心修改] 绘图文字纯白
                "toolbar_bg": "#BCBCBC"        # 工具栏背景
            }
        }

        # --- Font Init ---
        self.base_font_size = 10
        self.current_font_size = self.base_font_size
        self.f_normal = tkfont.Font(family="Segoe UI", size=self.base_font_size)
        self.f_bold = tkfont.Font(family="Segoe UI", size=self.base_font_size, weight="bold")
        self.f_title = tkfont.Font(family="Helvetica", size=self.base_font_size + 8, weight="bold")
        
        self.default_tk_font = tkfont.nametofont("TkDefaultFont")
        self._resize_timer = None

        # --- Theme ---
        self.setup_theme(self.current_theme)
        
        self.VERSION = __version__
        self.current_lang = "en"
        self.ui_elements = {}
        self.root.geometry("1110x990")
        self.root.configure(bg="#F0F2F5") 
        self.root.minsize(1000, 900)
        self.kymo_windows = {}
        
        try:
            icon_path = self.get_asset_path("ratiofish.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(default=icon_path) 
        except Exception as e:
            print(f"Warning: Failed to load icon: {e}")

        # --- Managers ---
        self.plot_mgr = None 
        self.roi_mgr = RoiManager(self)
        self.session = AnalysisSession()

        self.use_custom_bg_var = tk.BooleanVar(value=False)
        self.channel_buttons = [] 
        self.is_interleaved_var = tk.BooleanVar(value=False)

        self.setup_ui_skeleton()
        self.setup_shortcuts()
        self.update_language()
        self.change_font_size(0)
        
        self.root.after(100, self.load_graphics_engine)
        if startup_file:
            # 延时稍微长一点(比如800ms)，或者在 auto_load_project 里做检查，确保图形引擎加载完毕
            self.root.after(800, lambda: self.auto_load_project(startup_file))

    @property
    def data1(self): return self.session.data1
    @data1.setter
    def data1(self, value): self.session.data1 = value

    @property
    def data2(self): return self.session.data2
    @data2.setter
    def data2(self, value): self.session.data2 = value

    @property
    def data_aux(self): return self.session.data_aux
    @data_aux.setter
    def data_aux(self, value): self.session.data_aux = value
    
    @property
    def data1_raw(self): return self.session.data1_raw
    @data1_raw.setter
    def data1_raw(self, value): self.session.data1_raw = value

    @property
    def data2_raw(self): return self.session.data2_raw
    @data2_raw.setter
    def data2_raw(self, value): self.session.data2_raw = value

    @property
    def cached_bg1(self): return self.session.cached_bg1
    @cached_bg1.setter
    def cached_bg1(self, value): self.session.cached_bg1 = value
    
    @property
    def cached_bg2(self): return self.session.cached_bg2
    @cached_bg2.setter
    def cached_bg2(self, value): self.session.cached_bg2 = value
    
    @property
    def cached_bg_aux(self): return self.session.cached_bg_aux
    @cached_bg_aux.setter
    def cached_bg_aux(self, value): self.session.cached_bg_aux = value

    @property
    def c1_path(self): return self.session.c1_path
    @c1_path.setter
    def c1_path(self, value): self.session.c1_path = value

    @property
    def c2_path(self): return self.session.c2_path
    @c2_path.setter
    def c2_path(self, value): self.session.c2_path = value

    @property
    def dual_path(self): return self.session.dual_path
    @dual_path.setter
    def dual_path(self, value): self.session.dual_path = value

    @property
    def view_mode(self): return self.session.view_mode
    @view_mode.setter
    def view_mode(self, value): self.session.view_mode = value

    @property
    def is_playing(self): return self.session.is_playing
    @is_playing.setter
    def is_playing(self, value): self.session.is_playing = value

    @property
    def fps(self): return self.session.fps
    @fps.setter
    def fps(self, value): self.session.fps = value

    @property
    def custom_bg1(self): return self.session.custom_bg1
    @custom_bg1.setter
    def custom_bg1(self, value): self.session.custom_bg1 = value

    @property
    def custom_bg2(self): return self.session.custom_bg2
    @custom_bg2.setter
    def custom_bg2(self, value): self.session.custom_bg2 = value


    def inspect_file_metadata(self, filepath):
        """
        预读取文件元数据，检测多通道和 Z-Stack。
        """
        COLOR_NORMAL = "#333333"
        COLOR_DISABLED = "#A0A0A0"

        # 1. UI 初始化复位
        self.chk_inter.config(state="normal")
        self.chk_inter.state(['!disabled', '!selected']) 
        self.sp_channels.config(state="normal")
        if hasattr(self, 'lbl_ch_count'): self.lbl_ch_count.config(foreground=COLOR_NORMAL)

        # 2. 调用 Model
        is_explicit_multichannel, detected_channels, detected_z, detected_axes = self.session.inspect_file_metadata(filepath)

        # [新增] 缓存检测到的 Z 层数，供 _on_axes_change 使用
        self.cached_z_count = detected_z

        # [核心] 自动填充 Axes 输入框
        # 注意：这行代码会触发 _on_axes_change，所以后续的 UI 更新逻辑都交在那里面处理
        if hasattr(self, 'var_axes_entry'):
            self.var_axes_entry.set(detected_axes)

        # 3. 更新 Channel 状态
        if is_explicit_multichannel:
            print(f"[Metadata] File detected as {detected_channels}-Channel. Disabling manual split.")
            self.is_interleaved_var.set(False)
            self.chk_inter.config(state="disabled")
            self.sp_channels.config(state="disabled")
            if hasattr(self, 'lbl_ch_count'): self.lbl_ch_count.config(foreground=COLOR_DISABLED)
        else:
            print("[Metadata] File detected as 1-Channel (or unknown). User can manually split.")





    def auto_load_project(self, filepath):
        """
        程序启动时自动加载工程文件。
        具备重试机制，确保 Graphics Engine 初始化完毕后再加载。
        """
        # 1. 检查绘图引擎是否就绪
        if self.plot_mgr is None or not hasattr(self.plot_mgr, 'ax'):
            print("Graphics engine not ready, retrying in 200ms...")
            self.root.after(200, lambda: self.auto_load_project(filepath))
            return

        # 2. 检查文件是否存在
        if not os.path.exists(filepath):
            messagebox.showerror("Error", f"Startup file not found:\n{filepath}")
            return

        # 3. 根据文件后缀决定加载逻辑
        try:
            print(f"Auto-loading: {filepath}")
            if filepath.endswith(".ria") or filepath.endswith(".json"):
                self.load_project_logic(filepath)
            else:
                # 如果用户双击的是图片文件(.tif)而不是工程文件，尝试作为单文件加载
                self.nb_import.select(0) # 切换到 Single File Tab
                self.dual_path = filepath
                self.lbl_dual_path.config(text=os.path.basename(filepath))
                self.check_ready()
                # 只有这里需要手动触发加载，load_project_logic 内部已经包含了 load_data
                self.load_data() 
                
        except Exception as e:
            messagebox.showerror("Auto-Load Error", f"Failed to load startup file:\n{e}")


    def setup_shortcuts(self):
        # ROI Drawing Shortcuts
        self.root.bind("<Control-t>", lambda event: self.roi_mgr.start_drawing(self.shape_var.get()))
        self.root.bind("<Control-T>", lambda event: self.roi_mgr.start_drawing(self.shape_var.get()))
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

    def setup_theme(self, mode="light"):
        """
        根据 mode ("light" or "dark") 设置全局样式。
        """
        style = ttk.Style()
        try: style.theme_use('clam')
        except: pass
        
        c = self.THEME_COLORS[mode]
        
        # 1. 更新主窗口背景
        self.root.configure(bg=c["bg"])
        
        # 2. 配置下拉菜单 (Listbox) 颜色
        self.root.option_add('*TCombobox*Listbox.background', c["card"])
        self.root.option_add('*TCombobox*Listbox.foreground', c["text"])
        self.root.option_add('*TCombobox*Listbox.selectBackground', c["accent"])
        self.root.option_add('*TCombobox*Listbox.selectForeground', "white")

        # 3. 配置通用样式
        style.configure(".", background=c["bg"], foreground=c["text"], font=self.f_normal)
        style.configure("TLabel", background=c["bg"], foreground=c["text"])
        style.configure("TButton", background=c["card"], foreground=c["text"], borderwidth=1)
        
        # 状态映射
        style.map("TButton", foreground=[("disabled", c["fg_disabled"])])
        style.map("TLabel", foreground=[("disabled", c["fg_disabled"])])
        style.map("TCheckbutton", foreground=[("disabled", c["fg_disabled"])])
        
        # 输入框
        style.configure("TEntry", fieldbackground=c["input_bg"], foreground=c["text"], insertcolor=c["text"])
        style.configure("TSpinbox", fieldbackground=c["input_bg"], foreground=c["text"], arrowcolor=c["text"])
        
        # 下拉框
        style.configure("TCombobox", fieldbackground=c["input_bg"], foreground=c["text"], background=c["card"], arrowcolor=c["text"])
        style.map("TCombobox", fieldbackground=[("readonly", c["input_bg"])], foreground=[("disabled", c["fg_disabled"])])

        # 卡片容器
        style.configure("Card.TFrame", background=c["card"])
        style.configure("Card.TLabelframe", background=c["card"], foreground=c["text"])
        style.configure("Card.TLabelframe.Label", background=c["card"], foreground=c["accent"], font=self.f_bold)
        
        # 头部样式 (Header)
        style.configure("Header.TFrame", background=c["card"])
        
        # [核心修改] 标题专用样式 (Title.TLabel)
        # 1. 背景色设为 c["card"]，与 Header 背景融合，实现“伪透明”
        # 2. 前景色：浅色模式用深蓝灰(#2c3e50)显得专业，深色模式用纯白(#FFFFFF)
        title_fg = "#2c3e50" if mode == "light" else "#FFFFFF"
        style.configure("Title.TLabel", background=c["card"], foreground=title_fg)

        # 白色背景组件适配
        style.configure("White.TFrame", background=c["card"])
        style.configure("White.TLabel", background=c["card"], foreground=c["text"])
        style.configure("White.TCheckbutton", background=c["card"], foreground=c["text"])
        style.configure("White.TRadiobutton", background=c["card"], foreground=c["text"])
        
        # Toggle 按钮
        style.configure("Toggle.TButton", background=c["card"], foreground=c["text"])
        style.map("Toggle.TButton", 
            background=[("selected", c["accent"]), ("active", c["input_bg"])], 
            foreground=[("selected", "white"), ("disabled", c["fg_disabled"])]
        )
        
        # 灰色按钮
        style.configure("Gray.TButton", background=c["input_bg"], foreground=c["fg_disabled"])
        style.map("Gray.TButton", foreground=[("active", c["text"])])

        # 工具按钮
        style.configure("Toolbutton", background=c["card"], foreground=c["text"])
        style.map("Toolbutton", background=[("selected", c["input_bg"])], foreground=[("selected", c["accent"])])
        
        # 徽章
        style.configure("BadgeOrange.TLabel", background="#fd7e14", foreground="white")
        style.configure("BadgeBlue.TLabel", background=c["accent"], foreground="white")
        style.configure("BadgeGreen.TLabel", background="#28a745", foreground="white")

        # 特殊蓝色文本
        style.configure("Blue.TLabel", foreground=c["accent"])
        style.configure("Blue.TButton", foreground=c["accent"])
        style.configure("Blue.Toolbutton", foreground=c["accent"])

        self.style = style





    def toggle_theme(self):
        # 1. 切换状态
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        
        # 2. 刷新 Tkinter 样式
        self.setup_theme(self.current_theme)
        
        # 3. 刷新 Matplotlib 图表颜色
        if self.plot_mgr:
            c = self.THEME_COLORS[self.current_theme]
            self.plot_mgr.apply_theme(c["plot_bg"], c["plot_fg"])
            
            if self.plot_mgr.plot_window_controller:
                self.plot_mgr.plot_window_controller.apply_theme(c)
            
            if self.data1 is not None:
                self.update_plot()
            else:
                logo_path = self.get_asset_path("app_ico.png")
                self.plot_mgr.show_logo(logo_path)

        # [新增] 4. 刷新所有打开的 Kymograph 窗口
        for k_id, k_win in self.kymo_windows.items():
            if k_win.is_open:
                k_win.apply_theme()

        # 5. 更新按钮文字
        btn_text = "☀️" if self.current_theme == "dark" else "🌙"
        self.btn_theme.config(text=btn_text)


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
        
        # 检查 lbl_title 是否存在 (防止销毁后报错)
        if hasattr(self, 'lbl_title'):
            self.lbl_title.config(text=self.t("header_title"))
            
        for key, widget in self.ui_elements.items():
            # [核心修复] 跳过动态数值标签
            # 凡是以 "val_" 开头的 key，都是用来显示数字的，不参与翻译
            if key.startswith("val_"):
                continue
                
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
        # Header 容器使用 Header.TFrame 样式 (背景色=card)
        header = ttk.Frame(self.root, padding="15 10", style="Header.TFrame")
        header.pack(fill="x")
        
        # [修改] 移除硬编码颜色，应用 Title.TLabel 样式
        # 这样它的背景色就会自动变成 Header 的颜色，看起来就是透明的
        self.lbl_title = ttk.Label(header, text="RIA", font=self.f_title, style="Title.TLabel")
        self.lbl_title.pack(side="left")
        
        self.ui_elements["header_title"] = self.lbl_title
        
        # 右侧按钮区
        btn_frame = ttk.Frame(header, style="Header.TFrame")
        btn_frame.pack(side="right")
        
        # 字体调整按钮
        ttk.Button(btn_frame, text="A+", width=3, command=lambda: self.change_font_size(1)).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="⟳", width=3, command=self.reset_font_size).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="A-", width=3, command=lambda: self.change_font_size(-1)).pack(side="right", padx=2)
        
        # GitHub 按钮
        self.btn_github = ttk.Button(btn_frame, text="☆ GitHub", command=self.star_github)
        self.btn_github.pack(side="right", padx=10)
        
        # 语言切换 & 主题切换按钮
        ttk.Button(btn_frame, text="🌐 EN/中文", command=self.toggle_language).pack(side="right", padx=2)
        
        # [新增] 主题切换按钮 (记得保留这个我们之前加的按钮)
        self.btn_theme = ttk.Button(btn_frame, text="🌙", width=3, command=self.toggle_theme)
        self.btn_theme.pack(side="right", padx=(2, 10))
        
        # 主布局分割窗口
        self.main_pane = ttk.PanedWindow(self.root, orient="horizontal")
        self.main_pane.pack(fill="both", expand=True, padx=10, pady=10)

        # 左侧面板
        self.frame_left_container = ttk.Frame(self.main_pane, style="Card.TFrame", padding=10)
        self.main_pane.add(self.frame_left_container, weight=0)
        
        self.frame_left = ttk.Frame(self.frame_left_container, width=320, style="White.TFrame")
        self.frame_left.pack(fill="both", expand=True)

        self.setup_file_group()      # 1. File Loading
        self.setup_preprocess_group()# 2. Image Registration
        self.setup_calc_group()      # 3. Calibration
        self.setup_view_group()      # 4. Display Settings
        self.setup_brand_logo()

        # 右侧面板
        self.frame_right = ttk.Frame(self.main_pane, style="Card.TFrame", padding=10)
        self.main_pane.add(self.frame_right, weight=1)

        # 通道选择栏
        self.frame_channels = ttk.Frame(self.frame_right, style="White.TFrame")
        self.frame_channels.pack(side="top", fill="x", pady=(0, 5))

        # 绘图容器
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
            
            self.plot_mgr.add_toolbar()
                
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
        
        # === Tab 1: Single File ===
        self.tab_dual = ttk.Frame(self.nb_import, style="White.TFrame", padding=(0, 5))
        self.nb_import.add(self.tab_dual, text=" Single File ")
        self.ui_elements["tab_dual"] = lambda text: self.nb_import.tab(0, text=text) 
        
        # --- Row 1: Select File & Indicators ---
        f_row = ttk.Frame(self.tab_dual, style="White.TFrame")
        f_row.pack(fill="x", pady=1)

        self.btn_dual = ttk.Button(f_row, command=self.select_dual_threaded, text="📂 Select File") # [修改] 绑定到 threaded 方法
        self.btn_dual.pack(side="left")
        self.ui_elements["btn_dual"] = self.btn_dual

        # 徽章区
        self.lbl_ch_indicator = ttk.Label(f_row, text="", style="White.TLabel")
        self.lbl_ch_indicator.pack(side="right", padx=(2, 5))

        self.lbl_z_indicator = ttk.Label(f_row, text="", style="White.TLabel")
        self.lbl_z_indicator.pack(side="right", padx=(2, 2))

        self.lbl_dual_path = ttk.Label(f_row, text="...", foreground="gray", anchor="w", style="White.TLabel", width=1)
        self.lbl_dual_path.pack(side="left", padx=5, fill="x", expand=True)

        # ✅ [新增] 状态提示栏 (用于显示 Reading Metadata...)
        self.lbl_status = ttk.Label(self.tab_dual, text="", font=("Segoe UI", 8), foreground="#0056b3", style="White.TLabel")
        self.lbl_status.pack(fill="x", padx=2, pady=(0, 2))

        # --- Row 2: Axes Input & Manual Split ---
        f_opts = ttk.Frame(self.tab_dual, style="White.TFrame")
        f_opts.pack(fill="x", pady=(2, 0))
        
        ttk.Label(f_opts, text="Axes:", style="White.TLabel", foreground="gray").pack(side="left")
        
        self.var_axes_entry = tk.StringVar(value="?")
        self.var_axes_entry.trace_add("write", self._on_axes_change) 
        
        self.entry_axes = ttk.Entry(f_opts, textvariable=self.var_axes_entry, width=7, font=("Segoe UI", 8))
        self.entry_axes.pack(side="left", padx=(2, 8))
        
        f_right = ttk.Frame(f_opts, style="White.TFrame")
        f_right.pack(side="right")

        self.chk_inter = ttk.Checkbutton(f_right, variable=self.is_interleaved_var, style="Toggle.TButton")
        self.chk_inter.pack(side="left")
        self.ui_elements["chk_interleaved"] = self.chk_inter
        
        self.lbl_ch_count = ttk.Label(f_right, text="Ch Count:", style="White.TLabel")
        self.lbl_ch_count.pack(side="left", padx=(10, 2))
        
        self.var_n_channels = tk.IntVar(value=2)
        self.sp_channels = ttk.Spinbox(f_right, from_=1, to=20, textvariable=self.var_n_channels, width=3)
        self.sp_channels.pack(side="left")

        # ... (后续 Separate Files 和 Project Tab 代码保持不变) ...
        self.tab_sep = ttk.Frame(self.nb_import, style="White.TFrame", padding=(0, 5))
        self.nb_import.add(self.tab_sep, text=" Separate Files ") 
        self.ui_elements["tab_sep"] = lambda text: self.nb_import.tab(1, text=text) 
        self.create_compact_file_row(self.tab_sep, "btn_c1", self.select_c1, "lbl_c1_path")
        self.create_compact_file_row(self.tab_sep, "btn_c2", self.select_c2, "lbl_c2_path")
        
        self.tab_proj = ttk.Frame(self.nb_import, style="White.TFrame", padding=(0, 5))
        self.nb_import.add(self.tab_proj, text=" Project ")
        f_proj_btns = ttk.Frame(self.tab_proj, style="White.TFrame")
        f_proj_btns.pack(fill="both", expand=True, pady=5, padx=5)
        self.btn_load_proj = ttk.Button(f_proj_btns, text="📂 Load Project (.ria)", command=self.load_project_dialog)
        self.btn_load_proj.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.btn_save_proj = ttk.Button(f_proj_btns, text="💾 Save Current (.ria)", command=self.save_project_dialog)
        self.btn_save_proj.pack(side="right", fill="x", expand=True, padx=(5, 0))
        
        f_actions = ttk.Frame(self.grp_file, style="Card.TFrame")
        f_actions.pack(fill="x", pady=(10, 0))
        
        self.lbl_z_proj = ttk.Label(f_actions, text="Z-Proj:", state="disabled", foreground="#A0A0A0", style="White.TLabel")
        self.lbl_z_proj.pack(side="left", padx=(0, 2))
        self.z_proj_var = tk.StringVar(value="") 
        self.combo_z_proj = ttk.Combobox(f_actions, textvariable=self.z_proj_var, 
                                         values=["Max (MIP)", "Ave (AIP)", "None (Treat as T)"], 
                                         state="disabled", width=14, font=("Segoe UI", 8))
        self.combo_z_proj.pack(side="left", padx=(0, 5))

        self.fr_load_container = ttk.Frame(f_actions, style="Card.TFrame")
        self.fr_load_container.pack(side="left", fill="x", expand=True, padx=(0, 2))
        
        self.btn_load = ttk.Button(self.fr_load_container, command=self.load_data, state="disabled", text="🚀 Load & Analyze")
        self.btn_load.pack(fill="both", expand=True)
        self.ui_elements["btn_load"] = self.btn_load

        # [修改] 进度条默认隐藏
        self.pb_loading = ttk.Progressbar(self.fr_load_container, orient="horizontal", mode="determinate", maximum=100)

        self.btn_clear_data = ttk.Button(f_actions, text="🗑", width=4, command=self.clear_all_data, style="Gray.TButton")
        self.btn_clear_data.pack(side="right", fill="y")

    def select_dual_threaded(self):
        p = filedialog.askopenfilename(filetypes=[("Image Files", "*.tif *.tiff *.nd2 *.oir"), ("All Files", "*.*")])
        if not p: return

        # 1. 更新 UI 显示路径
        self.dual_path = p
        self.lbl_dual_path.config(text=os.path.basename(p))
        
        # 2. 设置状态为正在读取
        self.lbl_status.config(text="⏳ Reading Metadata... (Large file may take time)", foreground="#007acc")
        self.btn_dual.config(state="disabled") # 防止重复点击
        self.btn_load.config(state="disabled") # 未读完前不能加载
        self.root.update()

        # 3. 启动后台线程读取元数据
        threading.Thread(target=self._metadata_task, args=(p,), daemon=True).start()

    def _metadata_task(self, filepath):
        try:
            # 执行耗时的 IO 操作
            # inspect_file_metadata 内部如果用到了 AICSImage(metadata_only=True) 依然会比较快，
            # 但如果是网络文件，依然有延迟，所以放线程里是对的。
            meta_res = self.session.inspect_file_metadata(filepath)
            
            # 传回主线程
            self.root.after(0, lambda: self._on_metadata_ready(meta_res))
        except Exception as e:
            self.root.after(0, lambda: self._on_metadata_error(str(e)))

    def _on_metadata_ready(self, meta_res):
        is_explicit, channels, z, axes = meta_res
        
        # 更新 Model 层逻辑
        self.cached_z_count = z
        if hasattr(self, 'var_axes_entry'):
            self.var_axes_entry.set(axes) # 这会触发 _on_axes_change

        if is_explicit:
            self.is_interleaved_var.set(False)
            self.chk_inter.config(state="disabled")
            self.sp_channels.config(state="disabled")
        else:
            self.chk_inter.config(state="normal")
            self.sp_channels.config(state="normal")

        # 恢复 UI 状态
        self.lbl_status.config(text="✔ Ready.", foreground="green")
        self.btn_dual.config(state="normal")
        self.check_ready() # 激活 Load 按钮
        
        # 1秒后清除 Ready 文字
        self.root.after(2000, lambda: self.lbl_status.config(text=""))



    def save_input_thread(self):
        """启动保存 Input 数据的线程"""
        if self.data1 is None: return
        
        # --- 1. 智能生成文件名 ---
        z_method = self.z_proj_var.get()
        name_parts = ["Processed"] # 基础前缀
        
        # 判断投影方式
        if "Max" in z_method:
            name_parts.append("MIP")  # Max Intensity Projection
        elif "Ave" in z_method:
            name_parts.append("AIP")  # Average Intensity Projection
        elif "None" not in z_method and z_method != "":
            # 其他情况（或者之前是 Z-Stack 但未投影）
            pass
            
        # 判断是否做过运动校正 (通过检查 session 中的矩阵列表)
        if self.session.alignment_matrices:
            name_parts.append("Aligned")
            
        # 添加时间戳防止重名
        ts = datetime.datetime.now().strftime("%H%M%S")
        name_parts.append(ts)
        
        # 组合文件名: e.g., "Processed_MIP_Aligned_102030.tif"
        default_name = "_".join(name_parts) + ".tif"
        
        # --- 2. 弹出保存对话框 ---
        path = filedialog.asksaveasfilename(
            defaultextension=".tif", 
            initialfile=default_name,
            title="Save Preprocessed Data"
        )
        
        if not path: return
        
        # 禁用按钮防止误触
        self.btn_save_input.config(state="disabled", text="⏳ Saving...")
        threading.Thread(target=self.save_input_task, args=(path,), daemon=True).start()

    def save_input_task(self, path):
        try:
            # 调用 Model 层的新方法
            self.session.export_input_data(path)
            
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Saved successfully to:\n{path}\n\nTip: You can load this .tif file directly next time!"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Save failed: {e}"))
            import traceback; traceback.print_exc()
        finally:
            self.root.after(0, lambda: self.btn_save_input.config(state="normal", text="📥 Save Z-Proj Tiff"))


    def _on_axes_change(self, *args):
        """
        [修改] 实时监听 Axes 输入框。
        逻辑：
        1. 只要 Axes 里没有 'Z'，强制禁用 Z-Proj 并清空文字。
        2. 只要 Axes 里没有 'Z'，隐藏 Z-Stack 徽章。
        """
        # 尚未初始化完成时可能报错，先做检查
        if not hasattr(self, 'combo_z_proj') or not hasattr(self, 'lbl_z_proj'):
            return

        axes_text = self.var_axes_entry.get().upper()
        COLOR_NORMAL = "#333333"
        COLOR_DISABLED = "#A0A0A0"

        # 获取缓存的层数，默认为 1
        z_count = getattr(self, 'cached_z_count', 1)

        if 'Z' in axes_text:
            # === 情况 A: 存在 Z 轴 ===
            
            # 1. 恢复 Z-Stack 徽章 (如果层数 > 1)
            if z_count > 1:
                self.lbl_z_indicator.config(text=f"❏{z_count}", style="BadgeOrange.TLabel")
            else:
                self.lbl_z_indicator.config(text="", style="White.TLabel")

            # 2. 激活投影选项
            self.lbl_z_proj.config(state="normal", foreground=COLOR_NORMAL)
            self.combo_z_proj.config(state="readonly")
            
            # [新增] 如果文字被清空了，恢复默认值
            # 这样看起来就是从“不可用状态”变回了“可用状态”
            if not self.z_proj_var.get():
                self.z_proj_var.set("Ave (AIP)")

        else:
            # === 情况 B: 无 Z 轴 (被用户删除了，或本身就没有) ===
            
            # 1. [新增] 隐藏 Z-Stack 徽章
            self.lbl_z_indicator.config(text="", style="White.TLabel")

            # 2. 禁用投影选项
            self.lbl_z_proj.config(state="disabled", foreground=COLOR_DISABLED)
            self.combo_z_proj.config(state="disabled")
            
            # 3. [新增] 清空下拉框文字
            # 这是一个视觉 Hack，因为 disabled 的文字通常还是黑色的。
            # 直接把它设为空字符串，用户就看不到了，实现了“彻底变灰/消失”的效果。
            self.z_proj_var.set("")

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

    # src/gui.py -> setup_calc_group (替换整个方法)

    def setup_calc_group(self):
        self.grp_calc = ttk.LabelFrame(self.frame_left, padding=10, style="Card.TLabelframe")
        self.grp_calc.pack(fill="x", pady=(0, 10))
        self.ui_elements["grp_calc"] = self.grp_calc
        
        # --- Ratio Mode Selection & Reset Button ---
        f_mode = ttk.Frame(self.grp_calc, style="White.TFrame")
        f_mode.pack(fill="x", pady=(0, 5))
        
        # 1. 标签
        self.lbl_mode = ttk.Label(f_mode, style="White.TLabel")
        self.lbl_mode.pack(side="left")
        self.ui_elements["lbl_ratio_mode"] = self.lbl_mode
        
        # 2. [修改] 下拉框 (改为 pack side=left，留出右边给垃圾桶)
        self.ratio_mode_var = tk.StringVar(value="c1_c2") 
        self.combo_mode = ttk.Combobox(f_mode, state="readonly")
        # padx=(5, 2) 给右边的按钮留一点空隙
        self.combo_mode.pack(side="left", fill="x", expand=True, padx=(5, 2))
        self.combo_mode.bind("<<ComboboxSelected>>", self.on_mode_change)
        
        # 3. [新增] 清除按钮 (垃圾桶)
        self.btn_reset_calc = ttk.Button(f_mode, text="🗑", width=4, 
                                         command=self.reset_calibration_params, 
                                         style="Gray.TButton")
        self.btn_reset_calc.pack(side="right")

        # --- Sliders Variables ---
        self.var_int_thresh = tk.DoubleVar(value=0.0)
        self.var_ratio_thresh = tk.DoubleVar(value=0.0)
        self.var_smooth = tk.DoubleVar(value=0.0)
        
        # 默认背景值 0.0
        self.var_bg = tk.DoubleVar(value=0.0)
        
        # --- Sliders Creation ---
        self.create_slider(self.grp_calc, "lbl_int_thr", 0, 500, 1, self.var_int_thresh)
        self.create_slider(self.grp_calc, "lbl_ratio_thr", 0, 5.0, 0.1, self.var_ratio_thresh)
        self.create_slider(self.grp_calc, "lbl_smooth", 0, 10, 1, self.var_smooth, True)
        self.create_bg_slider(self.grp_calc, "lbl_bg", 0, 50, self.var_bg)
        
        # --- Background ROI Controls ---
        f_bg_tools = ttk.Frame(self.grp_calc, style="White.TFrame")
        f_bg_tools.pack(fill="x", pady=(5, 0))
        
        self.btn_draw_bg = ttk.Button(f_bg_tools, text="✏️ Draw BG Region", 
                                      command=self.draw_bg_roi_action)
        self.btn_draw_bg.pack(side="left", fill="x", expand=True, padx=(0, 2))
        
        self.chk_custom_bg = ttk.Checkbutton(f_bg_tools, text="Use ROI BG Mode", 
                                             variable=self.use_custom_bg_var,
                                             command=self.toggle_bg_mode,
                                             style="Toggle.TButton",                                    
                                             state="disabled") 
        self.chk_custom_bg.pack(side="right", fill="x", padx=(2, 0))
        
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
    



    def reset_calibration_params(self):
        """
        重置 Calibration 面板的所有参数为默认值 (0)。
        """
        # 1. 重置变量值
        self.var_int_thresh.set(0.0)
        self.var_ratio_thresh.set(0.0)
        self.var_smooth.set(0.0)
        self.var_bg.set(0.0)
        self.log_var.set(False) # 也可以选择重置 Log Scale

        # 2. 如果开启了 ROI BG Mode，先关闭它
        if self.use_custom_bg_var.get():
            self.use_custom_bg_var.set(False)
            self.toggle_bg_mode() # 这会处理 UI 状态的恢复

        # 3. 手动刷新滑动条旁边的数值标签
        # (因为直接 set 变量不会触发 command 回调，必须手动 config text)
        if "val_lbl_int_thr" in self.ui_elements:
            self.ui_elements["val_lbl_int_thr"].config(text="0.0")
        
        if "val_lbl_ratio_thr" in self.ui_elements:
            self.ui_elements["val_lbl_ratio_thr"].config(text="0.0")
            
        if "val_lbl_smooth" in self.ui_elements:
            self.ui_elements["val_lbl_smooth"].config(text="0")
            
        if hasattr(self, 'lbl_bg_value_display'):
            self.lbl_bg_value_display.config(text="0")

        # 4. 重新计算背景并刷新图像
        self.recalc_background()
        self.update_plot()







    def toggle_bg_mode(self):
        """
        切换背景模式：点击 'Use ROI Mode' 按钮时触发
        """
        # [修复] 获取正确的数值标签引用
        val_lbl = getattr(self, 'lbl_bg_value_display', None)
        
        if self.use_custom_bg_var.get():
            # === 进入 ROI 模式 (禁用滑块) ===
            self.bg_scale.state(['disabled'])
            
            # 1. 标题变灰
            if "lbl_bg" in self.ui_elements:
                self.ui_elements["lbl_bg"].config(foreground="#CCCCCC")
            
            # 2. 数值变灰
            if val_lbl: val_lbl.config(foreground="#CCCCCC")
            
        else:
            # === 回到滑块模式 (启用滑块) ===
            self.bg_scale.state(['!disabled'])
            
            # 1. 标题恢复深色
            if "lbl_bg" in self.ui_elements:
                self.ui_elements["lbl_bg"].config(foreground="#333333")
            
            # 2. 数值恢复红色 (强调色)
            if val_lbl: val_lbl.config(foreground="#007acc") # 或 red
            
        # 立即根据新模式刷新图像
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
        # 1. 创建底部区域容器
        bottom_area = ttk.Frame(parent, style="White.TFrame")
        bottom_area.pack(side="bottom", fill="x", pady=5)

        # === Row 0: Player Control (播放器控制栏) ===
        row_ctl = ttk.Frame(bottom_area, style="White.TFrame")
        row_ctl.pack(fill="x", pady=(0, 5))

        # 1. 播放/暂停按钮
        self.btn_play = ttk.Button(row_ctl, text="▶", width=4, command=self.toggle_play)
        self.btn_play.pack(side="left", padx=(0, 2))

        # 2. [位置调整] 循环开关 (即你提到的"重置"功能)
        # 放在播放键后面
        if not hasattr(self, 'loop_start'): self.loop_start = 0
        if not hasattr(self, 'loop_end'): self.loop_end = 0
        self.var_loop_active = tk.BooleanVar(value=False)

        self.btn_loop_toggle = ttk.Checkbutton(row_ctl, text="🔁", variable=self.var_loop_active, 
                                               style="Toggle.TButton", width=3)
        self.btn_loop_toggle.pack(side="left", padx=(0, 5))

        # 3. 帧数显示 (Frame X/Y)
        self.lbl_frame = ttk.Label(row_ctl, text="0/0", width=8, anchor="center", style="White.TLabel")
        self.lbl_frame.pack(side="left", padx=(0, 5))

        # 4. [位置调整] 循环起点 (Mark In) -> 放在进度条左边
        # 宽度减小为 2
        ttk.Button(row_ctl, text="⦗", width=2, command=self.set_loop_in, style="Compact.TButton")\
            .pack(side="left", padx=(0, 2))

        # 5. 进度条滑块 (中间自动拉伸)
        self.var_frame = tk.IntVar(value=0)
        self.frame_scale = ttk.Scale(row_ctl, from_=0, to=100, variable=self.var_frame, command=self.on_frame_slide)
        self.frame_scale.pack(side="left", fill="x", expand=True, padx=0)

        # 6. [位置调整] 循环终点 (Mark Out) -> 放在进度条右边
        # 宽度减小为 2
        ttk.Button(row_ctl, text="⦘", width=2, command=self.set_loop_out, style="Compact.TButton")\
            .pack(side="left", padx=(2, 0))

        # 7. 循环范围文字提示 (放在后面作为辅助信息)
        self.lbl_loop_range = ttk.Label(row_ctl, text="", font=("Segoe UI", 8), foreground="gray", style="White.TLabel")
        self.lbl_loop_range.pack(side="left", padx=(5, 0))

        # 8. FPS 选择菜单
        # [优化] 限制宽度，使其更紧凑
        self.fps_var = tk.StringVar(value="10 FPS")
        fps_menu = ttk.OptionMenu(row_ctl, self.fps_var, "10 FPS", "1 FPS", "5 FPS", "10 FPS", "20 FPS", "Max", command=self.change_fps)
        fps_menu.config(width=8) # 显式设置宽度缩小
        fps_menu.pack(side="left", padx=(5, 0))

        # 工具栏占位符 (保持不变)
        #self.tb_frame_placeholder = ttk.Frame(row_ctl, style="White.TFrame")
        #self.tb_frame_placeholder.pack(side="right")
        
        # === Row 1: Tools Grid (ROI 工具区) ===
        grid_area = ttk.Frame(bottom_area, style="White.TFrame")
        grid_area.pack(fill="x", expand=True)
        grid_area.columnconfigure(0, weight=2)
        grid_area.columnconfigure(1, weight=1)
        grid_area.columnconfigure(2, weight=1)
        
        # --- Col 0: ROI Tools (修正后的布局) ---
        fr_roi = ttk.LabelFrame(grid_area, padding=5, style="Card.TLabelframe")
        fr_roi.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.ui_elements["lbl_roi_tools"] = fr_roi
        
        # Sub-Row A: Shape Selection
        row_edit = ttk.Frame(fr_roi, style="White.TFrame")
        row_edit.pack(fill="x", pady=2)
        
        self.lbl_shape = ttk.Label(row_edit, text="ROI:", style="White.TLabel") 
        self.lbl_shape.pack(side="left", padx=(0, 2))
        self.ui_elements["lbl_shape"] = self.lbl_shape
        
        self.shape_var = tk.StringVar(value="rect")
        
        def set_shape_wrapper(mode): 
            self.shape_var.set(mode)
            self.roi_mgr.set_mode(mode)
            if mode == "line":
                self.btn_kymo.config(state="normal") 
            else:
                self.btn_kymo.config(state="disabled")

        f_shapes = ttk.Frame(row_edit, style="White.TFrame")
        f_shapes.pack(side="left", fill="y")
        
        # 直线 (蓝色)
        ttk.Radiobutton(f_shapes, text="╱", variable=self.shape_var, value="line", 
                        command=lambda: set_shape_wrapper("line"), style="Blue.Toolbutton").pack(side="left", padx=0)
        # 其他形状
        ttk.Radiobutton(f_shapes, text="□", variable=self.shape_var, value="rect", 
                        command=lambda: set_shape_wrapper("rect"), style="Toolbutton").pack(side="left", padx=0)
        ttk.Radiobutton(f_shapes, text="○", variable=self.shape_var, value="circle", 
                        command=lambda: set_shape_wrapper("circle"), style="Toolbutton").pack(side="left", padx=0)
        ttk.Radiobutton(f_shapes, text="⬠", variable=self.shape_var, value="polygon", 
                        command=lambda: set_shape_wrapper("polygon"), style="Toolbutton").pack(side="left", padx=0)
        
        # New ROI 按钮
        self.btn_draw = ttk.Button(
            row_edit, 
            text="New (Ctrl+T)", 
            command=lambda: self.roi_mgr.start_drawing(self.shape_var.get()), 
            style="Toggle.TButton"
        )
        self.btn_draw.pack(side="left", padx=(10, 2), fill="y", expand=True)
        self.ui_elements["btn_draw"] = self.btn_draw
        self.roi_mgr.set_draw_button(self.btn_draw)
        
        # 操作小按钮 (Undo/Clear/Save/Load)
        self.btn_undo = ttk.Button(row_edit, text="↩️", command=self.roi_mgr.remove_last, width=3, style="Compact.TButton")
        self.btn_undo.pack(side="left", padx=1, fill="y")
        self.btn_clear = ttk.Button(row_edit, text="🗑️", command=self.roi_mgr.clear_all, width=3, style="Compact.TButton")
        self.btn_clear.pack(side="left", padx=1, fill="y")
        self.btn_save_roi = ttk.Button(row_edit, text="💾", width=3, command=self.save_roi_dialog, style="Compact.TButton")
        self.btn_save_roi.pack(side="left", padx=1, fill="y")
        self.btn_load_roi = ttk.Button(row_edit, text="📂", width=3, command=self.load_roi_dialog, style="Compact.TButton")
        self.btn_load_roi.pack(side="left", padx=1, fill="y")

        # Sub-Row B: Plot & Kymo Actions
        row_act = ttk.Frame(fr_roi, style="White.TFrame")
        row_act.pack(fill="x", pady=4)
        
        # 1. Kymo 按钮 (蓝色)
        # 技巧：去掉大 width，使用 expand=True, fill="x" 让它自动拉伸
        self.btn_kymo = ttk.Button(row_act, text="🌊 Kymo", command=self.show_kymograph_window, 
                                   state="disabled", style="Blue.TButton")
        self.btn_kymo.pack(side="left", fill="x", expand=True, padx=(0, 2))
        
        # 2. Plot Curve 按钮
        self.btn_plot = ttk.Button(row_act, text="📈 Curve", command=self.plot_roi_curve)
        self.btn_plot.pack(side="left", fill="x", expand=True, padx=2)
        self.ui_elements["btn_plot"] = self.btn_plot
        
        # 3. Live Monitor
        self.live_plot_var = tk.BooleanVar(value=False)
        self.chk_live = ttk.Checkbutton(row_act, variable=self.live_plot_var, text="Live (Ctrl+L)", 
                                        style="Toggle.TButton", command=self.plot_roi_curve)
        # 关键修改：把 side="right" 改为 side="left"，并加上 expand=True
        # 这样它就会和前面两个按钮一起平分整行的宽度
        self.chk_live.pack(side="left", fill="x", expand=True, padx=(2, 0))
        self.ui_elements["chk_live"] = self.chk_live
        
        # Sub-Row C: Params
        row_param = ttk.Frame(fr_roi, style="White.TFrame")
        row_param.pack(fill="x", pady=(4, 0))
        
        # 1. Interval
        self.lbl_int = ttk.Label(row_param, text="Imaging Interval (s):", style="White.TLabel")
        self.lbl_int.pack(side="left")
        self.ui_elements["lbl_interval"] = self.lbl_int
        self.var_interval = tk.StringVar(value="1.0")
        ttk.Entry(row_param, textvariable=self.var_interval, width=5).pack(side="left", padx=2)
        
        # 2. Unit
        self.lbl_unit = ttk.Label(row_param, text="Plotting Unit:", style="White.TLabel")
        self.lbl_unit.pack(side="left", padx=(5, 0))
        self.ui_elements["lbl_unit"] = self.lbl_unit
        self.combo_unit = ttk.Combobox(row_param, values=["s", "m", "h"], width=3, state="readonly")
        self.combo_unit.current(0); self.combo_unit.pack(side="left", padx=2)

        # 3. [修改] Normalization 按钮化
        self.norm_var = tk.BooleanVar(value=False)
        # 原来是 style="White.TCheckbutton" -> 改为 style="Toggle.TButton"
        self.chk_norm = ttk.Checkbutton(row_param, 
                                        text="Normal. (ΔR/R₀)", 
                                        variable=self.norm_var, 
                                        style="Toggle.TButton")
        self.chk_norm.pack(side="right", padx=2)
        # --- Col 1: Data Export ---
        fr_exp = ttk.LabelFrame(grid_area, padding=5, style="Card.TLabelframe")
        fr_exp.grid(row=0, column=1, sticky="nsew", padx=(0, 5))
        self.ui_elements["lbl_export"] = fr_exp
        
        self.btn_save_frame = ttk.Button(fr_exp, text="📷 Save Frame", command=self.save_current_frame)
        self.btn_save_frame.pack(fill="x", pady=2)
        self.ui_elements["btn_save_frame"] = self.btn_save_frame
        
        self.btn_save_stack = ttk.Button(fr_exp, text="💾 Save Stack", command=self.save_stack_thread)
        self.btn_save_stack.pack(fill="x", pady=2)
        self.ui_elements["btn_save_stack"] = self.btn_save_stack

        # ✅ [新增] 3. Save Input (预处理后的原始图)
        # 专门用于把 OIR/Z-Proj/Align 后的结果存下来，下次直接用
        self.btn_save_input = ttk.Button(fr_exp, text=self.t("btn_save_input"), command=self.save_input_thread)
        self.btn_save_input.pack(fill="x", pady=2)
        # 不要忘了加到 ui_elements，方便后续做语言包翻译
        self.ui_elements["btn_save_input"] = self.btn_save_input
        
        self.btn_save_raw = ttk.Button(fr_exp, text="💽 Save Raw Ratio", command=self.save_raw_thread)
        self.btn_save_raw.pack(fill="x", pady=2)
        self.ui_elements["btn_save_raw"] = self.btn_save_raw
        
        # --- Col 2: Settings ---
        # [修改] 使用 ToggledFrame 组件，实现"平时隐藏，点三角形展开"的效果
        # 注意：这里直接使用 ToggledFrame (需确保文件头部已 import)
        self.fr_settings = ToggledFrame(grid_area, text="⚙ Settings", style="Card.TFrame")
        self.fr_settings.lbl_title.configure(font=self.f_bold)
        
        # sticky="new" (North-East-West) 让它靠上、靠左右撑开，防止展开时位置乱跑
        self.fr_settings.grid(row=0, column=2, sticky="new", padx=(0, 5))

        # 1. 注册标题到翻译系统
        # ToggledFrame 的标题 Label 叫 lbl_title
        self.ui_elements["lbl_settings"] = self.fr_settings.lbl_title

        # 2. 在展开区域 (sub_frame) 添加功能按钮

        # [新增] 按钮 A: 快捷键列表
        self.btn_shortcuts = ttk.Button(self.fr_settings.sub_frame, text="⌨ Shortcuts", command=self.show_shortcuts_window)
        self.btn_shortcuts.pack(fill="x", pady=(2, 2), padx=2)

        # 按钮 B: 检查更新 (保留原有的)
        self.btn_check_update = ttk.Button(self.fr_settings.sub_frame, text="🔄 Check Update", command=self.check_update_thread)
        self.btn_check_update.pack(fill="x", pady=(0, 2), padx=2)
        self.ui_elements["btn_check_update"] = self.btn_check_update

        # 按钮 C: 联系作者 (保留原有的)
        self.btn_contact = ttk.Button(
            self.fr_settings.sub_frame, 
            text="📧 Contact Author", 
            command=lambda: webbrowser.open("https://www.cns.ac.cn") 
        )
        self.btn_contact.pack(fill="x", pady=(0, 2), padx=2)
        self.ui_elements["btn_contact"] = self.btn_contact




    # [替换原有的 show_kymograph_window 方法]
    def show_kymograph_window(self):
        line_roi = self.roi_mgr.get_last_line_roi()
        if not line_roi:
            messagebox.showinfo("Kymograph", "Please select or draw a Line ROI first.")
            return

        roi_id = line_roi['id']

        # 如果窗口已存在，置顶
        if roi_id in self.kymo_windows and self.kymo_windows[roi_id].is_open:
            self.kymo_windows[roi_id].window.lift()
            return

        # 创建新窗口
        kymo_win = KymographWindow(self.root, roi_id, self)
        
        # [新增] 自动同步主界面的时间间隔
        try:
            interval = float(self.var_interval.get())
            kymo_win.var_s_frame.set(interval)
        except: pass
        
        self.kymo_windows[roi_id] = kymo_win

        # 立即计算一次数据并显示
        self.update_kymograph_for_roi(line_roi)

    def update_kymograph_for_roi(self, line_roi):
        """核心计算逻辑，供 show_kymograph_window 和 拖动事件 调用"""
        roi_id = line_roi['id']
        if roi_id not in self.kymo_windows or not self.kymo_windows[roi_id].is_open:
            return

        try:
            from .processing import extract_kymograph
        except ImportError:
            try:
                from processing import extract_kymograph
            except ImportError:
                print("Error: Could not import 'processing' module.")
                return
            
        d1, d2, bg1, bg2 = self.get_active_data()
        if d1 is None: return

        p1, p2 = line_roi['params']

        try:
            # 计算数据 (与之前相同)
            kymo1 = extract_kymograph(d1 - bg1, p1, p2)
            if kymo1 is None: return

            if d2 is not None:
                kymo2 = extract_kymograph(d2 - bg2, p1, p2)
                with np.errstate(divide='ignore', invalid='ignore'):
                    kymo_final = np.divide(kymo1, kymo2, where=kymo2 > 1.0)
                    kymo_final[kymo2 <= 1.0] = 0
            else:
                kymo_final = kymo1

            self.kymo_windows[roi_id].update_data(kymo_final, self.log_var.get())

        except Exception as e:
            print(f"Kymo update error: {e}")


    def save_roi_dialog(self):
        default_name = "ROI_Data.json"
        try:
            current_tab = self.nb_import.index("current")
            source_path = None
            if current_tab == 0: 
                source_path = self.dual_path # Tab 0 是 Single File
            elif current_tab == 1:
                source_path = self.c1_path   # Tab 1 是 Separate Files
            
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

    # src/gui.py

   

    def load_data(self, on_success=None, predefined_roles=None):
        current_tab = self.nb_import.index("current")
        if current_tab == 0 and not self.dual_path: return
        if current_tab == 1 and (not self.c1_path or not self.c2_path): return

        # UI 切换
        self.btn_load.pack_forget()
        self.pb_loading.pack(fill="both", expand=True)
        self.pb_loading["value"] = 0
        
        # [核心修改] 移除 is_loading_data 标志和 _simulate_progress 调用
        # self.is_loading_data = True
        # self.root.after(50, self._simulate_progress) <--- 删除这行

        self.root.update()

        # 收集参数
        params = {
            "tab_idx": current_tab,
            "dual_path": self.dual_path,
            "c1_path": self.c1_path,
            "c2_path": self.c2_path,
            "is_interleaved": self.is_interleaved_var.get(),
            "n_ch": self.var_n_channels.get() if self.is_interleaved_var.get() else 2,
            "z_method": None,
            "on_success_cb": on_success, 
            "predefined_roles": predefined_roles,
            "user_axes": None 
        }

        # ... (中间的 Axes 和 Z-Method 参数收集逻辑保持不变) ...
        if current_tab == 0 and hasattr(self, 'var_axes_entry'):
            raw_axes = self.var_axes_entry.get().strip().upper()
            if raw_axes and raw_axes != "?":
                params["user_axes"] = raw_axes

        if hasattr(self, 'combo_z_proj') and str(self.combo_z_proj['state']) != 'disabled':
            val = self.z_proj_var.get()
            if "Max" in val: params["z_method"] = "max"
            elif "Ave" in val: params["z_method"] = "ave"
            elif "None" in val: params["z_method"] = None 

        threading.Thread(target=self._load_data_thread, args=(params,), daemon=True).start()


    # src/gui.py -> _load_data_thread
    def _load_data_thread(self, params):
        try:
            # [标记] 用于判断是否已经从"假进度条(Indeterminate)"切换到了"真进度条(Determinate)"
            self._determinate_started = False

            # --- 定义回调 1: 更新进度条数值 ---
            def update_progress(current, total):
                def _update_bar():
                    # 如果这是第一次收到明确的进度信号 (比如 AICS 初始化完成了)
                    # 停止"左右乱跳"模式，切换为"百分比"模式
                    if not self._determinate_started:
                        self.pb_loading.stop()
                        self.pb_loading.config(mode="determinate")
                        self._determinate_started = True
                    
                    # 计算并更新百分比
                    if total > 0:
                        val = (current / total) * 100
                        self.pb_loading.configure(value=val)
                    
                    # [关键] 强制刷新 UI 闲置任务
                    # 这能防止在密集循环读取时主窗口变成"未响应"或白屏
                    self.root.update_idletasks()

                # 必须将 UI 更新指令发送回主线程执行
                self.root.after(0, _update_bar)

            # --- 定义回调 2: 更新状态文字 (例如 "Reading Metadata...") ---
            def update_status_text(msg):
                # 使用蓝色文字显示当前正在进行的底层操作
                self.root.after(0, lambda: self.lbl_status.config(text=msg, foreground="#007acc"))

            # --- 开始读取流程 ---
            raw_channels = []
            
            if params["tab_idx"] == 0:
                # [Case A] 单文件/多通道模式 (支持 OIR, ND2 等)
                # 将两个回调函数都传下去
                raw_channels = self.session.load_channels_from_file(
                    filepath=params["dual_path"], 
                    is_interleaved=params["is_interleaved"], 
                    n_channels=params["n_ch"],
                    z_proj_method=params["z_method"],
                    user_axes=params["user_axes"],
                    progress_callback=update_progress, # 传入进度回调
                    status_callback=update_status_text # 传入文字回调
                )
                
            elif params["tab_idx"] == 1:
                # [Case B] 分离文件模式 (TiffFile 读取通常很快，简单处理)
                self.root.after(0, lambda: self.lbl_status.config(text="Loading separate files...", foreground="#007acc"))
                # 给一个 50% 的假进度
                self.root.after(0, lambda: self.pb_loading.configure(mode="determinate", value=50))
                
                raw_channels = self.session.load_separate_channels(
                    params["c1_path"], 
                    params["c2_path"]
                )
            
            # --- 读取成功，清理状态并进入后处理 ---
            
            # 1. 清除状态栏文字
            self.root.after(0, lambda: self.lbl_status.config(text=""))
            
            # 2. 获取回调和预设角色
            cb = params.get("on_success_cb") 
            roles_pre = params.get("predefined_roles")
            
            # 3. 调度后处理任务到主线程 (设置数据、绘图等)
            self.root.after(0, lambda: self._load_data_post_process(raw_channels, cb, roles_pre))

        except Exception as e:
            # --- 读取失败 ---
            err_msg = str(e)
            # 清除状态文字
            self.root.after(0, lambda: self.lbl_status.config(text=""))
            # 触发错误弹窗
            self.root.after(0, lambda: self._load_data_error(err_msg))



    # [关键修改] 必须在括号里加上 predefined_roles=None，否则就会报 "but 4 were given"
    def _load_data_post_process(self, raw_channels, on_success_cb=None, predefined_roles=None):
        """
        回到主线程：处理角色分配、绘图、恢复按钮状态。
        """
        self.is_loading_data = False
        self.pb_loading["value"] = 100
        self.root.update()

        try:
            # 1. 角色分配 (Ask Roles)
            roles = None 
            
            # [新增] 优先使用预定义角色 (工程文件加载时)
            if predefined_roles is not None:
                print("Using predefined channel roles from project.")
                roles = predefined_roles

            # 否则，如果是多通道且没有预定义，则询问用户
            elif len(raw_channels) > 2:
                self.root.config(cursor="") 
                user_roles = self.ask_channel_roles(len(raw_channels))
                roles = user_roles
                
            elif len(raw_channels) == 0:
                 raise ValueError(f"No channels loaded.")

            # 2. Set Data
            self.session.set_data(raw_channels, roles)
            
            # 1. 运动矫正按钮控制
            # 逻辑变更：只要有数据且是多帧图像 (Time-Lapse)，无论单通道还是双通道，都允许矫正。
            if self.session.data1 is not None and self.session.data1.shape[0] > 1:
                self.btn_align.config(state="normal", text=self.t("btn_align"), style="TButton")
            else:
                self.btn_align.config(state="disabled")

            # 2. Ratio 阈值控件视觉反馈
            # 逻辑保持：只有存在 Ratio (双通道) 时，Ratio Min 标签才显示为黑色，否则变灰提示不可用
            if self.session.data2 is not None:
                self.ui_elements["lbl_ratio_thr"].config(foreground="black")
            else:
                self.ui_elements["lbl_ratio_thr"].config(foreground="gray")

            self.data1_raw = None
            self.btn_undo_align.config(state="disabled", text=self.t("btn_undo_align"), style="Gray.TButton")

            self.view_mode = "ratio"
            self.rebuild_channel_bar()
            
            self.frame_scale.configure(to=self.data1.shape[0]-1)
            self.var_frame.set(0); self.frame_scale.set(0)

            # ✅ [新增] 初始化循环范围为全长
            self.loop_start = 0
            self.loop_end = self.data1.shape[0] - 1
            self.var_loop_active.set(False)
            self._update_loop_label()
            
            count = len(raw_channels)
            if count == 1: self.lbl_ch_indicator.config(text=f" 1 Ch (Int) ", style="BadgeGreen.TLabel")
            else: self.lbl_ch_indicator.config(text=f" {count} Chs (Ratio) ", style="BadgeBlue.TLabel")

            h, w = self.data1.shape[1], self.data1.shape[2]
            self.plot_mgr.init_image((h, w), cmap="coolwarm")
            self.roi_mgr.connect(self.plot_mgr.ax)
            self.update_plot()

            # 4. 按钮反馈
            self.pb_loading.pack_forget()
            self.btn_load.config(text="✅ Data Loaded!", style="Success.TButton", cursor="")
            self.btn_load.pack(fill="both", expand=True) 
            self.root.after(2000, self._reset_load_button)

            # =========================================================
            # [关键] 执行工程恢复回调！
            # =========================================================
            if on_success_cb:
                print("Executing Project Restore Callback...")
                on_success_cb()

        except Exception as e:
            self._load_data_error(str(e))




    

    # [新增辅助方法 3] 主线程后处理 (失败)

    def _load_data_error(self, error_msg):
        # 停止进度条
        self.pb_loading.stop()
        self.pb_loading.pack_forget()
        
        # 恢复按钮
        self.btn_load.pack(fill="both", expand=True)
        self._reset_load_button()
        
        messagebox.showerror("Error", error_msg)
        import traceback
        traceback.print_exc()

    # [新增辅助方法 4] 重置按钮
    def _reset_load_button(self):
        # 恢复文字和样式
        self.btn_load.config(text="🚀 Load & Analyze", state="normal", style="TButton", cursor="")


    def check_ready(self):
        """
        检查文件是否已选择，从而启用/禁用 'Load' 按钮。
        """
        current_tab = self.nb_import.index("current")
        is_ready = False
        
        if current_tab == 0: # Single File
            if self.dual_path and os.path.exists(self.dual_path):
                is_ready = True
        elif current_tab == 1: # Separate Files
            if (self.c1_path and os.path.exists(self.c1_path) and 
                self.c2_path and os.path.exists(self.c2_path)):
                is_ready = True
                
        if is_ready:
            self.btn_load.config(state="normal")
        else:
            self.btn_load.config(state="disabled")


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
        self.loop_start = 0
        self.loop_end = 0
        self.var_loop_active.set(False)
        if hasattr(self, 'lbl_loop_range'):
            self.lbl_loop_range.config(text="")


        self.c1_path = None
        self.c2_path = None
        self.dual_path = None
        
        self.lbl_c1_path.config(text=self.t("lbl_no_file"))
        self.lbl_c2_path.config(text=self.t("lbl_no_file"))
        self.lbl_dual_path.config(text=self.t("lbl_no_file"))
        
        # 重置通道数徽章
        if hasattr(self, 'lbl_ch_indicator'):
            self.lbl_ch_indicator.config(text="", style="White.TLabel")

        # =========================================================
        # [核心修复] 重置 Z-Stack 相关的 UI
        # =========================================================
        if hasattr(self, 'lbl_z_indicator'):
            # 1. 清除 Z-Stack 徽章文字 (修复 bug)
            self.lbl_z_indicator.config(text="", style="White.TLabel")
        
        if hasattr(self, 'lbl_z_proj'):
            # 2. 将 "Z-Proj:" 标签文字显式变灰
            self.lbl_z_proj.config(state="disabled", foreground="#A0A0A0")
            
            # 3. 禁用下拉框 (系统会自动处理内部文字变灰，或者直接变不可点)
            self.combo_z_proj.config(state="disabled")
            
            # (可选) 如果你想让里面的字彻底消失，可以取消注释下面这行：
            # self.z_proj_var.set("") 
        # =========================================================
        
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

        # Clear all channels buttons
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

    # src/gui.py -> create_slider

    def create_slider(self, parent, label_key, min_v, max_v, step, variable, is_int=False):
        f = ttk.Frame(parent, style="White.TFrame"); f.pack(fill="x", pady=1)
        h = ttk.Frame(f, style="White.TFrame"); h.pack(fill="x")
        lbl = ttk.Label(h, style="White.TLabel"); lbl.pack(side="left") 
        self.ui_elements[label_key] = lbl
        
        # 数值显示标签
        val_lbl = ttk.Label(h, text=str(variable.get()), foreground="#007acc", font=self.f_bold, style="White.TLabel")
        val_lbl.pack(side="right", padx=(0, 10))
        
        # [关键新增] 注册这个标签，以便 load_project 时能找到并更新它
        self.ui_elements[f"val_{label_key}"] = val_lbl 
        
        def on_slide(v):
            val = float(v)
            if is_int: val = int(val)
            variable.set(val)
            fmt = "{:.0f}" if is_int else "{:.1f}"
            val_lbl.config(text=fmt.format(val))
            if not self.is_playing: self.update_plot()
            
        s = ttk.Scale(f, from_=min_v, to=max_v, command=on_slide)
        s.set(variable.get())
        s.pack(fill="x")

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
        if hasattr(self, 'var_bg'):
             self.session.bg_percent = self.var_bg.get()

        # 2. 调用 Model 计算
        # Model 内部会更新 cached_bg1, cached_bg2 等
        self.session.recalc_background()
        

    def select_c1(self):
        # [修改] 添加 *.oir 支持
        p = filedialog.askopenfilename(filetypes=[("Image Files", "*.tif *.tiff *.nd2 *.oir"), ("All Files", "*.*")])
        if p: self.c1_path = p; self.lbl_c1_path.config(text=os.path.basename(p)); self.check_ready()

    def select_c2(self):
        # [修改] 添加 *.oir 支持
        p = filedialog.askopenfilename(filetypes=[("Image Files", "*.tif *.tiff *.nd2 *.oir"), ("All Files", "*.*")])
        if p: self.c2_path = p; self.lbl_c2_path.config(text=os.path.basename(p)); self.check_ready()

    def select_dual(self):
        # [修改] 添加 *.oir 支持
        p = filedialog.askopenfilename(filetypes=[("Image Files", "*.tif *.tiff *.nd2 *.oir"), ("All Files", "*.*")])
        if p: 
            self.dual_path = p
            self.lbl_dual_path.config(text=os.path.basename(p))
            self.inspect_file_metadata(p)
            self.check_ready()





    def run_alignment_thread(self):
        if self.data1 is None: return
        self.btn_align.config(state="disabled")
        self.btn_load.config(state="disabled")
        self.pb_align.pack(fill="x", pady=(5, 0))
        self.pb_align["value"] = 0
        threading.Thread(target=self.alignment_task, daemon=True).start()



    def alignment_task(self):
        try:
            # 定义回调函数，用于更新 GUI 的进度条
            # 这里的逻辑是：Model 在后台线程跑，每处理一帧调用一次这个函数
            # 我们用 self.root.after 把更新指令发回主线程，防止界面卡死或闪退
            def progress_cb(curr, total):
                self.root.after(0, lambda: self.pb_align.configure(value=(curr/total)*100))
            
            # [CALL MODEL] 所有的脏活累活都在这里面
            self.session.align_data(progress_callback=progress_cb)
            
            # 完成后通知 UI 刷新按钮状态
            self.root.after(0, self.alignment_done_ui)
            
        except ImportError:
            # 专门捕获缺少 OpenCV 的错误
            self.root.after(0, lambda: messagebox.showerror("Error", "OpenCV not found.\nPlease run: pip install opencv-python"))
            self.root.after(0, self.alignment_reset_ui)
        except Exception as e:
            # 捕获其他未知错误
            self.root.after(0, lambda: messagebox.showerror("Alignment Error", str(e)))
            self.root.after(0, self.alignment_reset_ui)


    def undo_alignment(self):
        # [CALL MODEL] 尝试撤销
        success = self.session.undo_alignment()
        
        if success:
            # 如果撤销成功，刷新图像
            self.update_plot()
            
            # 更新按钮样式 (变绿一下提示用户)
            self.btn_undo_align.config(text=self.t("btn_undo_done"), style="Success.TButton")
            self.btn_align.config(text=self.t("btn_align"), style="TButton")
            
            # 1秒后把撤销按钮变回灰色禁用状态
            def restore_undo_btn():
                try: 
                    self.btn_undo_align.config(state="disabled", text=self.t("btn_undo_align"), style="Gray.TButton")
                except: pass
            self.root.after(1000, restore_undo_btn)


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
    

    def get_processed_frame(self, frame_idx):
        """
        [Refactored] 仅作为“参数收集器”。
        收集 UI 上的滑块值、复选框状态，打包传给 Model，然后直接返回结果。
        """
        # 1. 收集 UI 参数
        int_th = self.var_int_thresh.get()
        ratio_th = self.var_ratio_thresh.get()
        
        sm_val = int(self.var_smooth.get())
        
        is_log = self.log_var.get()
        use_custom_bg = self.use_custom_bg_var.get()

        # [新增] 检查是否需要交换通道
        # 如果下拉框选的是 "c2_c1"，则需要交换
        need_swap = (self.ratio_mode_var.get() == "c2_c1")

        # 2. 委托给 Model 计算
        return self.session.get_processed_frame(
            frame_idx=frame_idx,
            int_thresh=int_th,
            ratio_thresh=ratio_th,
            smooth_size=sm_val,
            log_scale=is_log,
            use_custom_bg=use_custom_bg,
            swap_channels=need_swap # [传参]
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
        
        # [修复] 1. 在主线程弹出对话框 (UI 线程安全)
        ts = datetime.datetime.now().strftime("%H%M%S")
        path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=f"Ratio_Stack_{ts}.tif")
        
        if not path: return # 用户取消
        
        # 2. 禁用按钮
        self.btn_save_stack.config(state="disabled", text="⏳ Saving...")
        
        # 3. 启动线程，把 path 传进去
        threading.Thread(target=self.save_stack_task, args=(path,), daemon=True).start()
    
    # [修改] 任务函数接收 path 参数，不再自己弹窗
    def save_stack_task(self, path):
        try:
            # 收集参数 (在主线程读取变量最安全，但这里读 DoubleVar 通常没问题，严谨做法是在主线程收集好 params 传进来)
            # 为了简单，这里暂且保留，如果报错，请在 save_stack_thread 里把 params 收集好传进来
            params = {
                "int_thresh": self.var_int_thresh.get(),
                "ratio_thresh": self.var_ratio_thresh.get(),
                "smooth": int(self.var_smooth.get()),
                "log_scale": self.log_var.get(),
                "use_custom_bg": self.use_custom_bg_var.get()
            }

            def progress_cb(curr, total):
                self.root.after(0, lambda: self.ui_elements["btn_save_stack"].config(text=f"⏳ {curr}/{total}"))

            # [CALL MODEL]
            self.session.export_processed_stack(path, params, progress_callback=progress_cb)
            
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Stack saved to:\n{path}"))
            
        except Exception as e: 
            self.root.after(0, lambda: messagebox.showerror("Error", f"Save failed: {e}"))
            import traceback; traceback.print_exc()
        finally: 
            self.root.after(0, lambda: self.ui_elements["btn_save_stack"].config(state="normal", text=self.t("btn_save_stack")))
    
    def save_stack_task(self):
        try:
            # 1. 禁用按钮，防止重复点击
            # 注意：在线程中操作 UI 最好用 after，或者确保这是在主线程触发前的状态更新
            self.root.after(0, lambda: self.ui_elements["btn_save_stack"].config(state="disabled", text="⏳ Saving..."))
            
            # 2. 弹出文件保存对话框 (必须在主线程，这里通常没问题，因为 thread 是在 task 内部启动的还是外部？)
            # 假设这个 task 是被 threading.Thread 调用的，那么 ask_filename 最好在外部做。
            # 但为了兼容旧逻辑，如果原本就是直接调用的，我们先这样写。
            # 如果这是一个线程函数，filedialog 可能会卡住。
            # 为了稳妥，建议逻辑是：主线程获取路径 -> 启动子线程保存。
            # 但为了少改动，我们假设这里运行环境和之前一致。
            
            ts = datetime.datetime.now().strftime("%H%M%S")
            # 注意：filedialog 并不是完全线程安全的，但在 Windows 上通常能跑
            path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=f"Ratio_Stack_{ts}.tif")
            
            if not path: 
                # 取消了，恢复按钮
                self.root.after(0, lambda: self.ui_elements["btn_save_stack"].config(state="normal", text=self.t("btn_save_stack")))
                return
            
            # 3. 收集参数 (从 UI 变量获取)
            params = {
                "int_thresh": self.var_int_thresh.get(),
                "ratio_thresh": self.var_ratio_thresh.get(),
                "smooth": int(self.var_smooth.get()),
                "log_scale": self.log_var.get(),
                "use_custom_bg": self.use_custom_bg_var.get()
            }

            # 4. 定义进度回调 (用于更新按钮文字)
            def progress_cb(curr, total):
                # 使用 root.after 确保 UI 更新在主线程执行
                self.root.after(0, lambda: self.ui_elements["btn_save_stack"].config(text=f"⏳ {curr}/{total}"))

            # 5. [CALL MODEL] 执行保存
            self.session.export_processed_stack(path, params, progress_callback=progress_cb)
            
            # 6. 完成提示
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Stack saved to:\n{path}"))
            
        except Exception as e: 
            self.root.after(0, lambda: messagebox.showerror("Error", f"Save failed: {e}"))
            # 打印报错堆栈以便调试
            import traceback; traceback.print_exc()
        finally: 
            # 无论成功失败，最后都要恢复按钮
            self.root.after(0, lambda: self.ui_elements["btn_save_stack"].config(state="normal", text=self.t("btn_save_stack")))
    def save_raw_thread(self):
        if self.data1 is None: return
        threading.Thread(target=self.save_raw_task).start()



    def save_raw_task(self):
        try:
            self.root.after(0, lambda: self.ui_elements["btn_save_raw"].config(state="disabled", text="⏳ Saving..."))
            
            ts = datetime.datetime.now().strftime("%H%M%S")
            path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=f"Clean_Ratio_Stack_{ts}.tif")
            if not path: 
                self.root.after(0, lambda: self.ui_elements["btn_save_raw"].config(state="normal", text=self.t("btn_save_raw")))
                return
            
            # 收集参数
            i_th = self.var_int_thresh.get()
            r_th = self.var_ratio_thresh.get()
            
            def progress_cb(curr, total):
                self.root.after(0, lambda: self.ui_elements["btn_save_raw"].config(text=f"⏳ {curr}/{total}"))

            # [CALL MODEL]
            self.session.export_raw_ratio_stack(path, i_th, r_th, progress_callback=progress_cb)
            
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Raw Ratio saved to:\n{path}"))
            
        except Exception as e: 
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally: 
            self.root.after(0, lambda: self.ui_elements["btn_save_raw"].config(state="normal", text=self.t("btn_save_raw")))



    def save_current_frame(self):
        # 检查是否有数据 (通过 session 检查)
        if self.session.data1 is None: return
        
        # 弹出对话框
        ts = datetime.datetime.now().strftime("%H%M%S")
        path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=f"Ratio_Frame_{self.var_frame.get()}_{ts}.tif")
        if not path: return
        
        # 收集参数
        params = {
            "int_thresh": self.var_int_thresh.get(),
            "ratio_thresh": self.var_ratio_thresh.get(),
            "smooth": int(self.var_smooth.get()),
            "log_scale": self.log_var.get(),
            "use_custom_bg": self.use_custom_bg_var.get()
        }
        
        try:
            # [CALL MODEL]
            self.session.export_current_frame(path, self.var_frame.get(), params)
            messagebox.showinfo("Success", f"Frame saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save frame: {e}")



    def on_frame_slide(self, v):
        self.var_frame.set(int(float(v))); self.lbl_frame.config(text=f"{self.var_frame.get()}/{self.data1.shape[0]-1}")
        if not self.is_playing: self.update_plot()
    
    def toggle_play(self):
        if self.is_playing: self.is_playing = False; self.btn_play.config(text="▶")
        else: self.is_playing = True; self.btn_play.config(text="⏸"); self.play_loop()
    
    def play_loop(self):
        if not self.is_playing or self.data1 is None: return
        
        curr = self.var_frame.get()
        max_frame = self.data1.shape[0] - 1
        
        loop_on = self.var_loop_active.get()
        
        # 计算下一帧
        next_frame = curr + 1
        
        if loop_on:
            # === 循环模式逻辑 ===
            # 1. 动态获取当前的有效范围，并防止越界
            safe_end = min(self.loop_end, max_frame)
            safe_start = max(0, min(self.loop_start, safe_end)) # 确保 start 不小于0且不大于 end
            
            # 2. 如果当前范围不合法（比如起点=终点），则强制全范围
            if safe_start >= safe_end:
                 safe_start = 0
                 safe_end = max_frame

            # 3. 核心循环判断
            # 如果当前帧已经超过了终点，或者当前帧甚至小于起点（比如用户拖动进度条到了前面）
            # 则跳回起点
            if next_frame > safe_end or next_frame < safe_start: # 注意这里用 next_frame 判断更流畅
                next_frame = safe_start
        else:
            # === 普通模式逻辑 ===
            if curr >= max_frame:
                next_frame = 0

        # 应用下一帧
        self.var_frame.set(next_frame)
        self.frame_scale.set(next_frame)
        self.lbl_frame.config(text=f"{next_frame}/{max_frame}")
        self.update_plot()
        
        dt = 1 if "Max" in self.fps_var.get() else int(1000/int(self.fps_var.get().split()[0]))
        self.root.after(dt, self.play_loop)


    def set_loop_in(self):
        """将当前帧设为循环起点"""
        if self.data1 is None: return
        curr = self.var_frame.get()
        max_f = self.data1.shape[0] - 1
        
        # 逻辑保护：如果起点设在终点后面，就把终点推到最后
        if curr >= self.loop_end:
            self.loop_end = max_f
            
        self.loop_start = curr
        
        # 自动开启循环模式，方便用户
        self.var_loop_active.set(True)
        self._update_loop_label()

    def set_loop_out(self):
        """将当前帧设为循环终点"""
        if self.data1 is None: return
        curr = self.var_frame.get()
        
        # 逻辑保护：如果终点设在起点前面，就把起点设为0
        if curr <= self.loop_start:
            self.loop_start = 0
            
        self.loop_end = curr
        
        # 自动开启循环模式
        self.var_loop_active.set(True)
        self._update_loop_label()

    def _update_loop_label(self):
        """更新 UI 上的范围文字"""
        if self.data1 is None:
            self.lbl_loop_range.config(text="")
            return
            
        max_f = self.data1.shape[0] - 1
        
        # 如果是全范围，显示 "All"
        if self.loop_start == 0 and self.loop_end == max_f:
             self.lbl_loop_range.config(text="All", foreground="gray")
        else:
             # 如果有特定范围，显示蓝色数字
             self.lbl_loop_range.config(text=f"{self.loop_start}-{self.loop_end}", foreground="#007acc")



    
    def change_fps(self, v):
        if "Max" in v: self.fps = 100
        else:
            try: self.fps = int(v.split()[0])
            except: self.fps = 10

    def check_update_thread(self):
        self.btn_check_update.config(state="disabled") 
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
            self.thread_safe_config(self.btn_check_update, state="normal")

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


    def save_project_dialog(self):
        if self.data1 is None:
            messagebox.showwarning("Save Project", "No data loaded to save.")
            return
            
        default_name = f"Project_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.ria"
        path = filedialog.asksaveasfilename(
            defaultextension=".ria",
            filetypes=[("RIA Project", "*.ria"), ("JSON", "*.json")],
            initialfile=default_name
        )
        if path:
            self.save_project_logic(path)

    def save_project_logic(self, filepath):
        try:
            project_dir = os.path.dirname(os.path.abspath(filepath))
            def to_relative(path):
                if not path or not os.path.exists(path):
                    return path
                try:
                    # 尝试计算相对路径
                    rel = os.path.relpath(path, project_dir)
                    return rel
                except ValueError:
                    # 如果在不同磁盘分区（Windows），无法计算相对路径，则保留绝对路径
                    return path
           
           
            # 1. 收集源文件信息
            source_info = {
                "mode": "single" if self.dual_path else "separate",
                "path_dual": to_relative(self.dual_path), # 转为相对路径
                "path_c1": to_relative(self.c1_path),     # 转为相对路径
                "path_c2": to_relative(self.c2_path),     # 转为相对路径
                "is_interleaved": self.is_interleaved_var.get(),
                "n_channels": self.var_n_channels.get(),
                # [新增] 保存 Z-Projection 设置
                "z_proj_method": self.z_proj_var.get() if str(self.combo_z_proj['state']) != 'disabled' else None,
                "channel_roles": self.session.current_roles,
                "axes": self.var_axes_entry.get() if hasattr(self, 'var_axes_entry') else None
            }
            
            # 2. 收集参数
            params = {
                "int_thresh": self.var_int_thresh.get(),
                "ratio_thresh": self.var_ratio_thresh.get(),
                "smooth": self.var_smooth.get(),
                "bg_percent": self.var_bg.get(),
                "log_scale": self.log_var.get(),
                # 自定义背景 ROI 数值
                "use_custom_bg": self.use_custom_bg_var.get(),
                "custom_bg1": self.custom_bg1,
                "custom_bg2": self.custom_bg2
            }
            
            # 3. 收集视图设置
            view_settings = {
                "ratio_mode": self.ratio_mode_var.get(),
                "cmap": self.cmap_var.get(),
                "bg_color": self.bg_color_var.get(),
                "lock_range": self.lock_var.get(),
                "vmin": self.entry_vmin.get(),
                "vmax": self.entry_vmax.get(),
                "view_mode": self.view_mode # 当前正看着哪个通道
            }
            
            # 4. 收集 ROI
            rois = self.roi_mgr.get_all_rois_data()
            
            # [新增] 序列化矩阵
            # Numpy array 不能直接被 json dump，需要转成 list
            matrices_json = []
            if self.session.alignment_matrices:
                matrices_json = [m.tolist() for m in self.session.alignment_matrices]

            # ✅ [新增] 收集绘图窗口状态
            plot_window_data = {}
            if self.plot_mgr and self.plot_mgr.plot_window_controller:
                plot_window_data = self.plot_mgr.plot_window_controller.get_settings()

            kymo_data_list = []
            for roi_id, win in self.kymo_windows.items():
                if win.is_open:
                    kymo_data_list.append(win.get_settings())

            # 写入
            project_data = {
                "version": self.VERSION,
                "timestamp": str(datetime.datetime.now()),
                "source": source_info,
                "params": params,
                "view": view_settings,
                "alignment": {
                    "is_aligned": (self.session.data1_raw is not None),
                    "matrices": matrices_json
                },
                "rois": rois,
                "plot_window": plot_window_data,  # ✅ [新增] 写入 JSON
                "kymographs": kymo_data_list

            }


            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=4)
                
            messagebox.showinfo("Success", "Project saved successfully!")
            
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def load_project_dialog(self):
        path = filedialog.askopenfilename(filetypes=[("RIA Project", "*.ria"), ("JSON", "*.json")])
        if path:
            self.load_project_logic(path)


    def load_project_logic(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            src = data.get("source", {})
            params = data.get("params", {})
            view = data.get("view", {})
            rois = data.get("rois", [])
            
            # --- [新增] 路径解析辅助函数 ---
            project_dir = os.path.dirname(os.path.abspath(filepath))

            def resolve_path(path):
                if not path: return None
                
                # 策略 1: 尝试作为相对路径拼接 (Project目录 + 相对路径)
                # 这样即使 path 存的是文件名，也能正确拼出全路径
                abs_path_rel = os.path.abspath(os.path.join(project_dir, path))
                if os.path.exists(abs_path_rel):
                    return abs_path_rel
                
                # 策略 2: 尝试作为绝对路径 (兼容旧文件或不同盘符的情况)
                if os.path.exists(path):
                    return path
                
                return None # 没找到
            # ----------------------------

            # --- 阶段 1: 恢复 UI 状态以便 load_data 读取 ---
            self.clear_all_data()
            
            mode = src.get("mode", "single")
            
            if mode == "single":
                # 解析路径
                raw_path = src.get("path_dual")
                p = resolve_path(raw_path)

                if not p:
                    # 只有当两个尝试都失败时才报错
                    messagebox.showerror("Error", f"Original source file not found:\n{raw_path}\n(Checked in: {project_dir})")
                    return
                
                self.nb_import.select(0)
                self.dual_path = p
                self.lbl_dual_path.config(text=os.path.basename(p))
                self.is_interleaved_var.set(src.get("is_interleaved", False))
                self.var_n_channels.set(src.get("n_channels", 2))

                saved_axes = src.get("axes", None)
                if saved_axes and hasattr(self, 'var_axes_entry'):
                    self.var_axes_entry.set(saved_axes)
                
                # 恢复 Z-Projection 设置
                z_method = src.get("z_proj_method")
                if z_method:
                    self.lbl_z_proj.config(state="normal")
                    self.combo_z_proj.config(state="readonly")
                    self.z_proj_var.set(z_method)
                
            else:
                raw_p1 = src.get("path_c1")
                raw_p2 = src.get("path_c2")
                
                p1 = resolve_path(raw_p1)
                p2 = resolve_path(raw_p2)

                if not p1 or not p2:
                    messagebox.showerror("Error", f"Original source files not found.\n{raw_p1}\n{raw_p2}")
                    return

                self.nb_import.select(1)
                self.c1_path = p1; self.lbl_c1_path.config(text=os.path.basename(p1))
                self.c2_path = p2; self.lbl_c2_path.config(text=os.path.basename(p2))
            
            self.check_ready()

            saved_roles = src.get("channel_roles", None)

            # --- 定义阶段 2: 数据加载成功后的回调 ---
            # --- Define Phase 2: Callback after data loading is complete ---
            def restore_settings_and_rois():
                print("Restoring Project Params & ROIs...")
                
                try:
                    # 1. Restore Parameters (Thresholds, Smooth, Log)
                    i_val = params.get("int_thresh", 0)
                    r_val = params.get("ratio_thresh", 0)
                    s_val = params.get("smooth", 0)
                    
                    self.var_int_thresh.set(i_val)
                    self.var_ratio_thresh.set(r_val)
                    self.var_smooth.set(s_val)
                    self.log_var.set(params.get("log_scale", False))
                    
                    # [Fix] Manually update the numeric labels for sliders
                    # Check if UI elements exist to avoid errors
                    if "val_lbl_int_thr" in self.ui_elements:
                        self.ui_elements["val_lbl_int_thr"].config(text=f"{i_val:.1f}")
                    
                    if "val_lbl_ratio_thr" in self.ui_elements:
                        self.ui_elements["val_lbl_ratio_thr"].config(text=f"{r_val:.1f}")
                        
                    if "val_lbl_smooth" in self.ui_elements:
                        self.ui_elements["val_lbl_smooth"].config(text=f"{int(s_val)}")

                    # 2. Restore Background Settings
                    bg_pct = params.get("bg_percent", 5.0)
                    self.var_bg.set(bg_pct)
                    
                    # Update the label next to the BG slider
                    if hasattr(self, 'lbl_bg_value_display'):
                        self.lbl_bg_value_display.config(text=f"{int(bg_pct)}")
                    
                    # Force recalculate background (setting variable doesn't trigger calculation)
                    self.recalc_background()
                    
                    # 3. Restore Custom Background Mode
                    if params.get("use_custom_bg", False):
                        self.custom_bg1 = params.get("custom_bg1", 0.0)
                        self.custom_bg2 = params.get("custom_bg2", 0.0)
                        self.use_custom_bg_var.set(True)
                        self.toggle_bg_mode() # Refresh UI state
                        self.lbl_bg_val.config(text=f"ROI Val: {self.custom_bg1:.1f} / {self.custom_bg2:.1f}")
                    else:
                        # Explicitly disable to prevent residual state
                        self.use_custom_bg_var.set(False)
                        self.toggle_bg_mode()
                    
                    # 4. Restore View Settings (Ratio Mode, Colormap, Lock Range)
                    saved_ratio_mode = view.get("ratio_mode", "c1_c2")
                    self.ratio_mode_var.set(saved_ratio_mode)
                    self.update_mode_options()
                    
                    self.cmap_var.set(view.get("cmap", "coolwarm"))
                    self.bg_color_var.set(view.get("bg_color", "Trans"))
                    
                    if view.get("lock_range", False):
                        self.lock_var.set(True)
                        self.entry_vmin.config(state="normal")
                        self.entry_vmin.delete(0, tk.END); self.entry_vmin.insert(0, view.get("vmin", "0.0"))
                        self.entry_vmax.config(state="normal")
                        self.entry_vmax.delete(0, tk.END); self.entry_vmax.insert(0, view.get("vmax", "1.0"))
                        self.toggle_scale_mode()
                    else:
                        self.lock_var.set(False)
                        self.toggle_scale_mode()

                    # =====================================================
                    # Apply saved transformation matrices
                    # =====================================================
                    # Note: 'data' variable comes from outer load_project_logic scope
                    alignment_data = data.get("alignment", {})
                    matrices = alignment_data.get("matrices", [])
                    
                    if matrices:
                        print(f"Applying {len(matrices)} saved alignment matrices...")
                        # Directly call Model to apply matrices (fast, no threading needed)
                        self.session.apply_existing_alignment(matrices)
                        
                        # Update UI buttons to "Done" state
                        self.btn_align.config(state="normal", text=self.t("btn_align_done"), style="Success.TButton")
                        self.btn_undo_align.config(state="normal", text=self.t("btn_undo_align"), style="Gray.TButton")
                    # =====================================================

                    # 5. Restore ROIs (Image data is ready now, masks generate correctly)
                    self.roi_mgr.restore_rois_from_data(rois)


                    has_line_roi = any(r['type'] == 'line' for r in self.roi_mgr.roi_list)
                    if has_line_roi:
                        self.btn_kymo.config(state="normal") # 强制激活按钮！
                        # 可选：如果你想把鼠标模式也切回直线，可以用下面这行
                        # self.shape_var.set("line"); self.roi_mgr.set_mode("line")
                    
                    # =====================================================
                    # ✅ [新增] 恢复 Kymograph 窗口
                    # =====================================================
                    saved_kymos = data.get("kymographs", [])
                    for k_settings in saved_kymos:
                        r_id = k_settings.get("roi_id")
                        
                        # 找到对应的 ROI 对象（确保 ID 匹配）
                        target_roi = next((r for r in self.roi_mgr.roi_list if r['id'] == r_id), None)
                        
                        if target_roi:
                            # 1. 创建窗口
                            k_win = KymographWindow(self.root, r_id, self)
                            self.kymo_windows[r_id] = k_win
                            
                            # 2. 应用保存的参数
                            k_win.apply_settings(k_settings)
                            
                            # 3. 计算并绘图
                            self.update_kymograph_for_roi(target_roi)
                    

                    plot_data = data.get("plot_window", {})
                    if plot_data and self.plot_mgr and self.plot_mgr.plot_window_controller:
                        # 1. 应用参数 (模式、字体、网格设置等)
                        self.plot_mgr.plot_window_controller.apply_settings(plot_data)
                        
                        # 2. 如果保存时窗口是打开的，则自动触发计算并显示
                        if plot_data.get("is_open", False):
                            # 这里直接调用 plot_roi_curve 即可
                            # 因为它会触发多线程计算，计算完后自动调用 plot_window.update_data
                            # 而 update_data 会调用 _create_ui，进而使用我们刚才 apply 的 preset 设置
                            print("Auto-opening plot window...")
                            self.plot_roi_curve()

                    # 6. Final Refresh
                    saved_view_mode = view.get("view_mode", "ratio")
                    self.set_view_mode(saved_view_mode) 
                    self.update_plot()
                    self.update_cmap()
                    
                    messagebox.showinfo("Success", "Project loaded successfully!")
                    
                except Exception as e:
                    print(f"Restore Error: {e}")
                    import traceback
                    traceback.print_exc()



            # --- 触发异步加载 ---
            self.load_data(on_success=restore_settings_and_rois, predefined_roles=saved_roles)

        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load project:\n{str(e)}")
            import traceback
            traceback.print_exc()


    def show_shortcuts_window(self):
        """显示快捷键列表弹窗"""
        # 创建弹窗
        win = Toplevel(self.root)
        win.title("Keyboard Shortcuts")
        win.geometry("380x280")
        win.transient(self.root) # 设置为子窗口
        
        # 居中显示
        try:
            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 190
            y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 140
            win.geometry(f"+{x}+{y}")
        except: pass

        # 标题
        ttk.Label(win, text="⌨ Keyboard Shortcuts", font=("Segoe UI", 12, "bold")).pack(pady=(15, 10))

        # 内容容器
        f_table = ttk.Frame(win, padding=10)
        f_table.pack(fill="both", expand=True)

        # 定义快捷键列表
        shortcuts = [
            ("Ctrl + T", "Start Drawing New ROI (新建ROI)"),
            ("Ctrl + P", "Plot Curve (生成曲线)"),
            ("Ctrl + L", "Toggle Live Monitor (实时监测)"),
            ("Esc",      "Cancel Drawing (取消绘制)"),
            ("Space",    "Pause/Play Video (暂停/播放)"), # 如果你绑定了空格键的话，没绑定可以不写
        ]

        # 渲染列表
        for key, desc in shortcuts:
            row = ttk.Frame(f_table)
            row.pack(fill="x", pady=4)
            
            # 快捷键 (蓝色代码字体)
            ttk.Label(row, text=key, font=("Consolas", 10, "bold"), 
                      foreground="#007acc", width=12, anchor="e").pack(side="left", padx=(0, 10))
            
            # 说明文字
            ttk.Label(row, text=desc, anchor="w").pack(side="left", fill="x", expand=True)

        # 底部关闭按钮
        ttk.Button(win, text="Close", command=win.destroy, width=10).pack(pady=15)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("RIA - Ratio Imaging Analyzer")
    app = RatioAnalyzerApp(root)
    root.mainloop()