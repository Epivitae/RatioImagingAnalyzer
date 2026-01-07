# src/gui.py
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
    # [修改] 导入 RiaToolbar
    from .gui_components import PlotManager, RoiManager, RiaToolbar
    from .model import AnalysisSession
except ImportError:
    try:
        from constants import LANG_MAP
        from components import ToggledFrame
        # [修改] 导入 RiaToolbar
        from gui_components import PlotManager, RoiManager, RiaToolbar
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
        
        self.raw_data = None
        
        self.var_um_px = tk.DoubleVar(value=1.0)
        self.var_s_frame = tk.DoubleVar(value=1.0)
        self.var_frame_start = tk.IntVar(value=0)
        self.var_frame_end = tk.IntVar(value=0)
        self.var_auto_range = tk.BooleanVar(value=True)
        self.var_cmap = tk.StringVar(value="jet")
        self.var_log = tk.BooleanVar(value=False)

        # --- Layout ---
        plot_frame = ttk.Frame(self.window)
        plot_frame.pack(side="top", fill="both", expand=True)
        
        self.fig = plt.Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
        
        # [修改] 使用自定义工具栏 RiaToolbar
        # 定义命名规则: Kymo_ROI_[ID].png
        def get_kymo_name():
            return f"Kymo_ROI_{self.roi_id}.png"

        self.toolbar = RiaToolbar(self.canvas, plot_frame, name_generator=get_kymo_name)
        self.toolbar.update()
        
        self.im_obj = None 
        self.cbar = None
        self.cax = None 

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

        # 1. [修复] UI 初始化复位 (增加 hasattr 检查)
        if hasattr(self, 'chk_inter'):
            self.chk_inter.config(state="normal")
            try: self.chk_inter.state(['!disabled', '!selected']) 
            except: pass
            
        if hasattr(self, 'sp_channels'):
            self.sp_channels.config(state="normal")
            
        if hasattr(self, 'lbl_ch_count'): 
            self.lbl_ch_count.config(foreground=COLOR_NORMAL)

        # 2. 调用 Model 获取元数据
        is_explicit_multichannel, detected_channels, detected_z, detected_axes = self.session.inspect_file_metadata(filepath)

        self.cached_z_count = detected_z

        # 自动填充 Axes
        if hasattr(self, 'var_axes_entry'):
            self.var_axes_entry.set(detected_axes)

        # 3. [修复] 更新旧组件状态 (增加 hasattr 检查)
        if is_explicit_multichannel:
            if hasattr(self, 'is_interleaved_var'): self.is_interleaved_var.set(False)
            if hasattr(self, 'chk_inter'): self.chk_inter.config(state="disabled")
            if hasattr(self, 'sp_channels'): self.sp_channels.config(state="disabled")
            if hasattr(self, 'lbl_ch_count'): self.lbl_ch_count.config(foreground=COLOR_DISABLED)


    def auto_load_project(self, filepath):
        """
        程序启动时自动加载工程文件。
        """
        if self.plot_mgr is None or not hasattr(self.plot_mgr, 'ax'):
            print("Graphics engine not ready, retrying in 200ms...")
            self.root.after(200, lambda: self.auto_load_project(filepath))
            return

        if not os.path.exists(filepath):
            messagebox.showerror("Error", f"Startup file not found:\n{filepath}")
            return

        try:
            print(f"Auto-loading: {filepath}")
            if filepath.endswith(".ria") or filepath.endswith(".json"):
                self.load_project_logic(filepath)
            else:
                # --- 【修复】适配新的 Tab 逻辑 ---
                # 如果是 OIR/ND2 等 Raw 格式 -> Tab 0
                ext = os.path.splitext(filepath)[1].lower()
                if ext in ['.oir', '.nd2', '.czi', '.lif']:
                     self.nb_import.select(0)
                     self.raw_path = filepath
                     self.lbl_raw_path.config(text=os.path.basename(filepath))
                     threading.Thread(target=self._metadata_task, args=(filepath,), daemon=True).start()
                else:
                     # 默认为 Tiff -> Tab 1
                     self.nb_import.select(1)
                     self.tiff_path = filepath
                     self.lbl_tiff_path.config(text=os.path.basename(filepath))
                     threading.Thread(target=self._metadata_task, args=(filepath,), daemon=True).start()
                
                self.check_ready()
                # 等待 Metadata 读取线程更新完 UI 后，用户手动点击 Load，或者这里自动 Load (建议手动，因为 Metadata 需要时间)
                
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
        
        # 标题专用样式 (Title.TLabel)
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
        
        # [新增] 选项卡样式 (Notebook Tabs)
        # 默认背景设为 card 颜色，Tab 默认设为 input_bg (浅灰)
        style.configure("TNotebook", background=c["card"], borderwidth=0)
        style.configure("TNotebook.Tab", background=c["input_bg"], foreground=c["text"], padding=[12, 3])
        
        # 选中状态映射：背景变强调色(蓝)，文字变白
        style.map("TNotebook.Tab",
            background=[("selected", c["accent"]), ("active", c["card"])],
            foreground=[("selected", "white")]
        )
        
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
        
        # 检查 lbl_title 是否存在
        if hasattr(self, 'lbl_title'):
            self.lbl_title.config(text=self.t("header_title"))
            
        for key, widget in self.ui_elements.items():
            if key.startswith("val_"): continue
            try:
                if callable(widget): 
                    widget(self.t(key))
                else:
                    widget.config(text=self.t(key))
            except: pass
            
        # --- 【修复】使用新的路径标签变量 ---
        # 如果 raw_path 为空，显示 "..."
        if hasattr(self, 'lbl_raw_path') and not getattr(self, 'raw_path', None):
             self.lbl_raw_path.config(text=self.t("lbl_no_file"))
        
        # 如果 tiff_path 为空，显示 "..."
        if hasattr(self, 'lbl_tiff_path') and not getattr(self, 'tiff_path', None):
             self.lbl_tiff_path.config(text=self.t("lbl_no_file"))
        
        # Separate Files 现在是 Listbox，不需要在这里更新 Label 文字
        
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
        
        # 1. Update Model Cache
        self.cached_z_count = z
        
        # 2. Auto-fill Axes Entry
        if hasattr(self, 'var_axes_entry'):
            self.var_axes_entry.set(axes)

        # 3. Update UI Components
        if hasattr(self, 'is_interleaved_var'):
            if is_explicit: self.is_interleaved_var.set(False)

        if hasattr(self, 'chk_inter'):
            state = "disabled" if is_explicit else "normal"
            self.chk_inter.config(state=state)
            
        if hasattr(self, 'sp_channels'):
            state = "disabled" if is_explicit else "normal"
            self.sp_channels.config(state=state)
            
        # --- Visual Feedback: Ready State (End) ---
        # 1. 恢复鼠标光标
        self.root.config(cursor="")
        
        # 2. 移除文件名旁边的沙漏 (根据当前 Tab 判断更新哪个 Label)
        current_tab = self.nb_import.index("current")
        if current_tab == 0 and hasattr(self, 'raw_path') and self.raw_path:
             self.lbl_raw_path.config(text=os.path.basename(self.raw_path))
        elif current_tab == 1 and hasattr(self, 'tiff_path') and self.tiff_path:
             self.lbl_tiff_path.config(text=os.path.basename(self.tiff_path))

        # 3. 状态栏变绿
        self.lbl_status.config(text="✔ Ready.", foreground="green")
        
        # 4. 恢复按钮文字
        self.btn_load.config(text="🚀 Load & Analyze")
        
        # 5. 【关键】此时才激活 Load 按钮
        self.check_ready() 
        
        # 1秒后清除 Ready 文字
        self.root.after(2000, lambda: self.lbl_status.config(text=""))



    def _on_metadata_error(self, error_msg):
        # 1. 恢复鼠标光标
        self.root.config(cursor="")
        
        # 2. 移除沙漏 (简单处理：尝试刷新当前显示的路径)
        try:
            current_tab = self.nb_import.index("current")
            if current_tab == 0 and hasattr(self, 'raw_path') and self.raw_path:
                self.lbl_raw_path.config(text=os.path.basename(self.raw_path))
            elif current_tab == 1 and hasattr(self, 'tiff_path') and self.tiff_path:
                self.lbl_tiff_path.config(text=os.path.basename(self.tiff_path))
        except: pass

        # 3. 恢复按钮文字并禁用
        self.btn_load.config(text="🚀 Load & Analyze", state="disabled")
        
        # 4. 状态栏变红
        self.lbl_status.config(text="❌ Error reading metadata.", foreground="red")

        # 5. 停止可能的进度条
        if hasattr(self, 'pb_loading'):
            self.pb_loading.stop()
            self.pb_loading.pack_forget()
            self.btn_load.pack(fill="both", expand=True)
            self._reset_load_button()

        messagebox.showerror("Metadata Error", f"Failed to read file info:\n{error_msg}")
        import traceback
        traceback.print_exc()


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


    # src/gui.py

    def _on_axes_change(self, *args):
        """
        [修改版] 实时监听 Axes 输入框。
        逻辑：
        1. 监听 'Z': 控制 Z-Proj 选项和 Z-Stack 徽章。
        2. 监听 'C': 如果没有 C，禁用多通道拆分控件 (Mixed Stacks, Ch Count)。
        """
        if not hasattr(self, 'combo_z_proj') or not hasattr(self, 'lbl_z_proj'):
            return

        axes_text = self.var_axes_entry.get().upper()
        COLOR_NORMAL = "#333333"
        COLOR_DISABLED = "#A0A0A0"

        # 获取缓存的层数，默认为 1
        z_count = getattr(self, 'cached_z_count', 1)

        # --- Z 轴逻辑 ---
        if 'Z' in axes_text:
            # 存在 Z 轴
            if z_count > 1:
                self.lbl_z_indicator.config(text=f"❏{z_count}", style="BadgeOrange.TLabel")
            else:
                self.lbl_z_indicator.config(text="", style="White.TLabel")

            self.lbl_z_proj.config(state="normal", foreground=COLOR_NORMAL)
            self.combo_z_proj.config(state="readonly")
            
            # 恢复默认值
            if not self.z_proj_var.get():
                self.z_proj_var.set("Ave (AIP)")
        else:
            # 无 Z 轴
            self.lbl_z_indicator.config(text="", style="White.TLabel")
            self.lbl_z_proj.config(state="disabled", foreground=COLOR_DISABLED)
            self.combo_z_proj.config(state="disabled")
            self.z_proj_var.set("") # 清空文字

        # --- [新增] C 轴逻辑 ---
        if 'C' not in axes_text:
            # 单通道：禁用拆分选项
            if hasattr(self, 'chk_inter'):
                self.chk_inter.config(state="disabled")
            if hasattr(self, 'sp_channels'):
                self.sp_channels.config(state="disabled")
            if hasattr(self, 'lbl_ch_count'):
                self.lbl_ch_count.config(foreground=COLOR_DISABLED)
        else:
            # 多通道：根据之前的检测结果决定是否启用
            # (如果之前是 explicitly detected 多通道，则保持 disabled，否则 normal)
            # 这里简单处理：至少恢复 Label 颜色，具体的 state 由加载逻辑控制
            if hasattr(self, 'lbl_ch_count'):
                self.lbl_ch_count.config(foreground=COLOR_NORMAL)



    def setup_preprocess_group(self):
        # [紧凑]
        self.grp_pre = ttk.LabelFrame(self.frame_left, padding=5, style="Card.TLabelframe")
        self.grp_pre.pack(fill="x", pady=(0, 5))
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
        # [紧凑]
        self.grp_calc = ttk.LabelFrame(self.frame_left, padding=5, style="Card.TLabelframe")
        self.grp_calc.pack(fill="x", pady=(0, 5))
        self.ui_elements["grp_calc"] = self.grp_calc
        
        # Row 1: Ratio Mode
        f_mode = ttk.Frame(self.grp_calc, style="White.TFrame")
        f_mode.pack(fill="x", pady=(0, 2)) # 减小 pady
        self.lbl_mode = ttk.Label(f_mode, style="White.TLabel")
        self.lbl_mode.pack(side="left")
        self.ui_elements["lbl_ratio_mode"] = self.lbl_mode
        self.ratio_mode_var = tk.StringVar(value="c1_c2") 
        self.combo_mode = ttk.Combobox(f_mode, state="readonly")
        self.combo_mode.pack(side="left", fill="x", expand=True, padx=(5, 2))
        self.combo_mode.bind("<<ComboboxSelected>>", self.on_mode_change)
        self.btn_reset_calc = ttk.Button(f_mode, text="🗑", width=4, command=self.reset_calibration_params, style="Gray.TButton")
        self.btn_reset_calc.pack(side="right")

        self.var_int_thresh = tk.DoubleVar(value=0.0)
        self.var_ratio_thresh = tk.DoubleVar(value=0.0)
        self.var_smooth = tk.DoubleVar(value=0.0)
        self.var_bg = tk.DoubleVar(value=0.0)
        
        # Sliders (Now Compact)
        self.create_slider(self.grp_calc, "lbl_int_thr", 0, 500, 1, self.var_int_thresh)
        self.create_slider(self.grp_calc, "lbl_ratio_thr", 0, 5.0, 0.1, self.var_ratio_thresh)
        self.create_slider(self.grp_calc, "lbl_smooth", 0, 10, 1, self.var_smooth, True)
        self.create_bg_slider(self.grp_calc, "lbl_bg", 0, 50, self.var_bg)
        
        # Background ROI
        f_bg_tools = ttk.Frame(self.grp_calc, style="White.TFrame")
        f_bg_tools.pack(fill="x", pady=(2, 0)) # 减小 pady
        self.btn_draw_bg = ttk.Button(f_bg_tools, text="✏️ Draw BG Region", command=self.draw_bg_roi_action)
        self.btn_draw_bg.pack(side="left", fill="x", expand=True, padx=(0, 2))
        self.chk_custom_bg = ttk.Checkbutton(f_bg_tools, text="Use ROI BG Mode", variable=self.use_custom_bg_var, command=self.toggle_bg_mode, style="Toggle.TButton", state="disabled") 
        self.chk_custom_bg.pack(side="right", fill="x", padx=(2, 0))
        self.lbl_bg_val = ttk.Label(self.grp_calc, text="ROI Val: None", foreground="gray", style="White.TLabel", font=("Segoe UI", 8))
        self.lbl_bg_val.pack(fill="x", padx=2, pady=(0, 2))

        # Log Scale
        self.log_var = tk.BooleanVar(value=False)
        self.chk_log = ttk.Checkbutton(self.grp_calc, text="📈 Log Scale", variable=self.log_var, command=self.update_plot, style="Toggle.TButton")
        self.chk_log.pack(fill="x", pady=0) 
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
        # [紧凑]
        self.grp_view = ttk.LabelFrame(self.frame_left, padding=5, style="Card.TLabelframe")
        self.grp_view.pack(fill="x", pady=(0, 5))
        self.ui_elements["grp_view"] = self.grp_view
        
        f_grid = ttk.Frame(self.grp_view, style="White.TFrame"); f_grid.pack(fill="x")
        self.lbl_cmap = ttk.Label(f_grid, style="White.TLabel"); self.lbl_cmap.grid(row=0, column=0, sticky="w")
        self.ui_elements["lbl_cmap"] = self.lbl_cmap
        self.cmap_var = tk.StringVar(value="coolwarm")
        ttk.OptionMenu(f_grid, self.cmap_var, "coolwarm", "jet", "viridis", "magma", "coolwarm", command=lambda _: self.update_cmap()).grid(row=0, column=1, sticky="ew")
        
        self.lbl_bg_col = ttk.Label(f_grid, style="White.TLabel"); self.lbl_bg_col.grid(row=1, column=0, sticky="w", pady=2) # 减小 pady
        self.ui_elements["lbl_bg_col"] = self.lbl_bg_col
        self.bg_color_var = tk.StringVar(value="Trans")
        ttk.OptionMenu(f_grid, self.bg_color_var, "Trans", "Trans", "Black", "White", command=lambda _: self.update_cmap()).grid(row=1, column=1, sticky="ew", pady=2)
        f_grid.columnconfigure(1, weight=1) 
        
        self.lock_var = tk.BooleanVar(value=False)
        self.chk_lock = ttk.Checkbutton(self.grp_view, variable=self.lock_var, command=self.toggle_scale_mode, style="Toggle.TButton")
        self.chk_lock.pack(fill="x", pady=(2, 2))
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
        self.fr_brand.pack(side="bottom", fill="x", pady=(5, 10)) # 移到底部，稍微留点下边距
        
        inner_box = ttk.Frame(self.fr_brand, style="White.TFrame")
        inner_box.pack(anchor="center")
        
        # [修改] 强制缩小图标
        try:
            icon_path = self.get_asset_path("app_ico.png") 
            if os.path.exists(icon_path):
                self.brand_icon_img = tk.PhotoImage(file=icon_path)
                # 假设图标原来是 256px，除以 6 变成约 40px
                if self.brand_icon_img.width() > 50:
                    scale_factor = self.brand_icon_img.width() // 100 
                    if scale_factor > 1:
                        self.brand_icon_img = self.brand_icon_img.subsample(scale_factor, scale_factor)
                ttk.Label(inner_box, image=self.brand_icon_img, style="White.TLabel").pack(side="left", padx=5) 
        except Exception as e: pass
        
        # [修改] 文字放右边，更省高度
        f_text = ttk.Frame(inner_box, style="White.TFrame")
        f_text.pack(side="left")
        ttk.Label(f_text, text="RIA 莉丫", font=("Microsoft YaHei UI", 10, "bold"), foreground="#0056b3", style="White.TLabel").pack(anchor="w")
        current_year = datetime.datetime.now().year
        ttk.Label(f_text, text=f"© {current_year} www.cns.ac.cn", font=("Segoe UI", 7), foreground="gray", style="White.TLabel").pack(anchor="w")

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
        # 1. 创建底部区域容器 (减少外部 padding)
        bottom_area = ttk.Frame(parent, style="White.TFrame")
        bottom_area.pack(side="bottom", fill="x", pady=2) 

        # ==================================================
        # Row 0: Player Control (播放器)
        # ==================================================
        row_ctl = ttk.Frame(bottom_area, style="White.TFrame")
        row_ctl.pack(fill="x", pady=(0, 2))

        # 恢复按钮宽度为默认舒适值 (width=4)
        self.btn_play = ttk.Button(row_ctl, text="▶", width=4, command=self.toggle_play)
        self.btn_play.pack(side="left", padx=(0, 2))

        if not hasattr(self, 'loop_start'): self.loop_start = 0
        if not hasattr(self, 'loop_end'): self.loop_end = 0
        self.var_loop_active = tk.BooleanVar(value=False)

        self.btn_loop_toggle = ttk.Checkbutton(row_ctl, text="🔁", variable=self.var_loop_active, style="Toggle.TButton", width=4)
        self.btn_loop_toggle.pack(side="left", padx=(0, 5))

        self.lbl_frame = ttk.Label(row_ctl, text="0/0", width=8, anchor="center", style="White.TLabel")
        self.lbl_frame.pack(side="left", padx=(0, 5))

        ttk.Button(row_ctl, text="⦗", width=2, command=self.set_loop_in, style="Compact.TButton").pack(side="left", padx=(0, 2))
        
        self.var_frame = tk.IntVar(value=0)
        self.frame_scale = ttk.Scale(row_ctl, from_=0, to=100, variable=self.var_frame, command=self.on_frame_slide)
        self.frame_scale.pack(side="left", fill="x", expand=True, padx=0)

        ttk.Button(row_ctl, text="⦘", width=2, command=self.set_loop_out, style="Compact.TButton").pack(side="left", padx=(2, 0))

        self.lbl_loop_range = ttk.Label(row_ctl, text="", font=("Segoe UI", 8), foreground="gray", style="White.TLabel")
        self.lbl_loop_range.pack(side="left", padx=(5, 0))

        self.fps_var = tk.StringVar(value="10 FPS")
        fps_menu = ttk.OptionMenu(row_ctl, self.fps_var, "10 FPS", "1 FPS", "5 FPS", "10 FPS", "20 FPS", "Max", command=self.change_fps)
        fps_menu.config(width=7) # 恢复一点宽度
        fps_menu.pack(side="left", padx=(5, 0))

        # ==================================================
        # Row 1: Tools Grid (高度压缩核心区)
        # ==================================================
        grid_area = ttk.Frame(bottom_area, style="White.TFrame")
        grid_area.pack(fill="x", expand=True)
        # 调整权重: 只要中间列 (Export) 够宽就行
        grid_area.columnconfigure(0, weight=5) # ROI Tools
        grid_area.columnconfigure(1, weight=2) # Export
        grid_area.columnconfigure(2, weight=1) # Settings
        
        # --- Col 0: ROI Tools (3行布局，主要压缩 pady) ---
        fr_roi = ttk.LabelFrame(grid_area, padding=2, style="Card.TLabelframe")
        fr_roi.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
        self.ui_elements["lbl_roi_tools"] = fr_roi
        
        # [Line 1] Shape | New | Icons
        row_1 = ttk.Frame(fr_roi, style="White.TFrame"); row_1.pack(fill="x", pady=1) # pady=1
        
        self.lbl_shape = ttk.Label(row_1, text="ROI:", style="White.TLabel"); self.lbl_shape.pack(side="left", padx=(0, 2))
        self.ui_elements["lbl_shape"] = self.lbl_shape
        self.shape_var = tk.StringVar(value="rect")
        
        def set_shape_wrapper(mode): 
            self.shape_var.set(mode)
            self.roi_mgr.set_mode(mode)
            self.btn_kymo.config(state="normal" if mode == "line" else "disabled")

        # 形状按钮 (恢复默认宽度)
        ttk.Radiobutton(row_1, text="╱", variable=self.shape_var, value="line", command=lambda: set_shape_wrapper("line"), style="Blue.Toolbutton").pack(side="left")
        ttk.Radiobutton(row_1, text="□", variable=self.shape_var, value="rect", command=lambda: set_shape_wrapper("rect"), style="Toolbutton").pack(side="left")
        ttk.Radiobutton(row_1, text="○", variable=self.shape_var, value="circle", command=lambda: set_shape_wrapper("circle"), style="Toolbutton").pack(side="left")
        ttk.Radiobutton(row_1, text="⬠", variable=self.shape_var, value="polygon", command=lambda: set_shape_wrapper("polygon"), style="Toolbutton").pack(side="left")
        
        ttk.Separator(row_1, orient="vertical").pack(side="left", fill="y", padx=5)

        # New 按钮 (恢复 fill=x, expand=True)
        self.btn_draw = ttk.Button(row_1, text="New (Ctrl+T)", command=lambda: self.roi_mgr.start_drawing(self.shape_var.get()), style="Toggle.TButton")
        self.btn_draw.pack(side="left", fill="x", expand=True, padx=2) 
        self.ui_elements["btn_draw"] = self.btn_draw
        self.roi_mgr.set_draw_button(self.btn_draw)
        
        # Icons (Undo/Clear...)
        for btn_txt, cmd in [("↩️", self.roi_mgr.remove_last), ("🗑️", self.roi_mgr.clear_all), ("💾", self.save_roi_dialog), ("📂", self.load_roi_dialog)]:
            ttk.Button(row_1, text=btn_txt, command=cmd, width=3, style="Compact.TButton").pack(side="left", padx=1)

        # [Line 2] Action Buttons (Kymo / Curve / Live)
        row_2 = ttk.Frame(fr_roi, style="White.TFrame"); row_2.pack(fill="x", pady=1) # pady=1
        
        # 按钮宽度不设死，让它们自动撑满
        self.btn_kymo = ttk.Button(row_2, text="🌊 Kymo", command=self.show_kymograph_window, state="disabled", style="Blue.TButton")
        self.btn_kymo.pack(side="left", fill="x", expand=True, padx=(0, 2))
        
        self.btn_plot = ttk.Button(row_2, text="📈 Curve (Ctrl+P)", command=self.plot_roi_curve)
        self.btn_plot.pack(side="left", fill="x", expand=True, padx=2)
        self.ui_elements["btn_plot"] = self.btn_plot
        
        self.live_plot_var = tk.BooleanVar(value=False)
        self.chk_live = ttk.Checkbutton(row_2, variable=self.live_plot_var, text="Live (Ctrl+L)", style="Toggle.TButton", command=self.plot_roi_curve)
        self.chk_live.pack(side="left", fill="x", expand=True, padx=(2, 0))
        self.ui_elements["chk_live"] = self.chk_live

        # [Line 3] Params (Interval / Unit / Norm)
        row_3 = ttk.Frame(fr_roi, style="White.TFrame"); row_3.pack(fill="x", pady=1) # pady=1
        
        self.lbl_int = ttk.Label(row_3, text="Imaging Interval (s):", style="White.TLabel"); self.lbl_int.pack(side="left")
        self.var_interval = tk.StringVar(value="1.0")
        ttk.Entry(row_3, textvariable=self.var_interval, width=6).pack(side="left", padx=2)
        
        self.lbl_unit = ttk.Label(row_3, text="Unit:", style="White.TLabel"); self.lbl_unit.pack(side="left", padx=(5, 0))
        self.combo_unit = ttk.Combobox(row_3, values=["s", "m", "h"], width=3, state="readonly"); self.combo_unit.current(0); self.combo_unit.pack(side="left", padx=2)
        
        self.norm_var = tk.BooleanVar(value=False)
        self.chk_norm = ttk.Checkbutton(row_3, text="Normalize (ΔR/R₀)", variable=self.norm_var, style="Toggle.TButton")
        self.chk_norm.pack(side="right", padx=2)

        
        # --- Col 1: Data Export (恢复三排垂直布局！) ---
        fr_exp = ttk.LabelFrame(grid_area, padding=2, style="Card.TLabelframe")
        fr_exp.grid(row=0, column=1, sticky="nsew", padx=(0, 3))
        self.ui_elements["lbl_export"] = fr_exp
        
        # 垂直排列 (默认就是垂直)，但使用 pady=1 极致压缩
        self.btn_save_frame = ttk.Button(fr_exp, text="📷 Save Frame", command=self.save_current_frame)
        self.btn_save_frame.pack(fill="x", pady=1) # pady=1
        self.ui_elements["btn_save_frame"] = self.btn_save_frame 
        
        self.btn_save_results = ttk.Button(fr_exp, text="💾 Save Results", command=self.save_results_thread)
        self.btn_save_results.pack(fill="x", pady=1) # pady=1
        self.ui_elements["btn_save_stack"] = self.btn_save_results 
        
        self.btn_save_pre = ttk.Button(fr_exp, text="📥 Save Z-Proj Tiff", command=self.save_preprocessed_thread)
        self.btn_save_pre.pack(fill="x", pady=1) # pady=1
        self.ui_elements["btn_save_input"] = self.btn_save_pre

        # --- Col 2: Settings (保持 ToggledFrame) ---
        self.fr_settings = ToggledFrame(grid_area, text="⚙ Settings", style="Card.TFrame") 
        self.fr_settings.lbl_title.configure(font=self.f_bold)
        self.fr_settings.grid(row=0, column=2, sticky="ns", padx=(0, 0)) # sticky="ns" 垂直撑满
        self.ui_elements["lbl_settings"] = self.fr_settings.lbl_title
        
        # 内部按钮
        self.btn_shortcuts = ttk.Button(self.fr_settings.sub_frame, text="⌨ Shortcuts", command=self.show_shortcuts_window)
        self.btn_shortcuts.pack(fill="x", pady=1)
        self.btn_check_update = ttk.Button(self.fr_settings.sub_frame, text="🔄 Update", command=self.check_update_thread)
        self.btn_check_update.pack(fill="x", pady=1)
        self.ui_elements["btn_check_update"] = self.btn_check_update
        self.btn_contact = ttk.Button(self.fr_settings.sub_frame, text="📧 Author", command=lambda: webbrowser.open("https://www.cns.ac.cn"))
        self.btn_contact.pack(fill="x", pady=1)
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
  

    def load_data(self, on_success=None, predefined_roles=None):
        # 1. 获取当前 Tab 索引
        current_tab = self.nb_import.index("current")
        
        # 2. 校验路径
        if current_tab == 0 and not getattr(self, 'raw_path', None): return
        if current_tab == 1 and not getattr(self, 'tiff_path', None): return
        if current_tab == 2 and len(getattr(self, 'sep_file_paths', [])) < 2: return

        # --- Visual Change: Button -> Active Progress Bar ---
        # 隐藏加载按钮
        self.btn_load.pack_forget()
        
        # 显示进度条 (位置参数与 btn_load 保持完全一致，确保无缝切换)
        self.pb_loading.pack(side="left", fill="both", expand=True, padx=(0, 2))
        
        # 【关键】设置为"不确定模式"(左右来回滚动)，让用户知道程序是活的
        self.pb_loading.configure(mode='indeterminate')
        self.pb_loading.start(15) # 数字越小滚动越快
        
        self.root.update()

        # 3. 收集参数
        params = {
            "tab_idx": current_tab,
            "z_method": None, 
            "on_success_cb": on_success, 
            "predefined_roles": predefined_roles,
            "user_axes": None 
        }

        if current_tab == 1 and hasattr(self, 'var_axes_entry'):
            raw_axes = self.var_axes_entry.get().strip().upper()
            if raw_axes and raw_axes != "?": params["user_axes"] = raw_axes

        if hasattr(self, 'z_proj_var'):
            val = self.z_proj_var.get()
            if val:
                if "Max" in val: params["z_method"] = "max"
                elif "Ave" in val: params["z_method"] = "ave"
                elif "None" in val: params["z_method"] = None 
                
        # 4. 启动后台线程
        threading.Thread(target=self._load_data_thread, args=(params,), daemon=True).start()



    def setup_file_group(self):
        # [紧凑] padding=5
        self.grp_file = ttk.LabelFrame(self.frame_left, text="1. File Loading", padding=5, style="Card.TLabelframe")
        self.grp_file.pack(fill="x", pady=(0, 5))
        self.ui_elements["grp_file"] = self.grp_file
        
        self.nb_import = ttk.Notebook(self.grp_file)
        self.nb_import.pack(fill="x", expand=True)
        self.nb_import.bind("<<NotebookTabChanged>>", lambda e: self.check_ready())
        
        # === Tab 0: Raw (已优化：网格化对齐排版) ===
        self.tab_raw = ttk.Frame(self.nb_import, style="White.TFrame", padding=5)
        self.nb_import.add(self.tab_raw, text="Raw")
        
        # 第一行：按钮和路径
        f_raw = ttk.Frame(self.tab_raw, style="White.TFrame")
        f_raw.pack(fill="x", pady=(0, 2)) # 减少下方间距，为提示语腾空间
        
        self.btn_raw = ttk.Button(f_raw, text="📂 Select Raw", command=self.select_raw_file)
        self.btn_raw.pack(side="left")
        
        self.lbl_raw_path = ttk.Label(f_raw, text="...", foreground="gray", style="White.TLabel")
        self.lbl_raw_path.pack(side="left", padx=5, fill="x", expand=True)
        
        # [新增] 第二行：网格化提示区域 (Grid Layout)
        f_hints = ttk.Frame(self.tab_raw, style="White.TFrame")
        f_hints.pack(fill="x", padx=2)

        # 定义通用小字样式
        hint_style = {"font": ("Segoe UI", 10), "foreground": "#999999", "style": "White.TLabel"}

        # Row 0: 标题
        ttk.Label(f_hints, text="Supports:", **hint_style).grid(row=0, column=0, sticky="w", columnspan=2, pady=(0, 1))

        # Row 1: 第一排厂商
        ttk.Label(f_hints, text="• .oir (Olympus)", **hint_style).grid(row=1, column=0, sticky="w", padx=(10, 5))
        ttk.Label(f_hints, text="• .nd2 (Nikon)", **hint_style).grid(row=1, column=1, sticky="w")

        # Row 2: 第二排厂商
        ttk.Label(f_hints, text="• .czi (Zeiss)", **hint_style).grid(row=2, column=0, sticky="w", padx=(10, 5))
        ttk.Label(f_hints, text="• .lif (Leica)", **hint_style).grid(row=2, column=1, sticky="w") # 修正了 Leice -> Leica

        # Row 3: 兜底说明
        ttk.Label(f_hints, text="& 160+ formats (Bio-Formats)", **hint_style).grid(row=3, column=0, columnspan=2, sticky="w", padx=(10, 0), pady=(1, 0))


        # === Tab 1: Standard Tiff ===
        self.tab_tiff = ttk.Frame(self.nb_import, style="White.TFrame", padding=5)
        self.nb_import.add(self.tab_tiff, text="Standard Tiff")
        f_tiff = ttk.Frame(self.tab_tiff, style="White.TFrame")
        f_tiff.pack(fill="x", pady=2)
        self.btn_tiff = ttk.Button(f_tiff, text="📂 Select Tiff", command=self.select_tiff_file)
        self.btn_tiff.pack(side="left")
        self.lbl_tiff_path = ttk.Label(f_tiff, text="...", foreground="gray", style="White.TLabel")
        self.lbl_tiff_path.pack(side="left", padx=5, fill="x", expand=True)

        # === Tab 2: Separate Files ===
        self.tab_sep = ttk.Frame(self.nb_import, style="White.TFrame", padding=5)
        self.nb_import.add(self.tab_sep, text="Separate Files")
        self.lst_files = tk.Listbox(self.tab_sep, height=3, selectmode="extended", bg="white", fg="black")
        self.lst_files.pack(side="top", fill="both", expand=True, pady=(0, 2))
        self.sep_file_paths = []
        btn_bar = ttk.Frame(self.tab_sep, style="White.TFrame")
        btn_bar.pack(side="top", fill="x")
        ttk.Button(btn_bar, text="➕ Add", width=8, command=self.add_separate_files).pack(side="left", padx=1)
        ttk.Button(btn_bar, text="➖ Del", width=8, command=self.remove_separate_file).pack(side="left", padx=1)
        ttk.Button(btn_bar, text="Clear", width=8, command=self.clear_separate_files).pack(side="left", padx=1)

        # === Tab 3: Project ===
        self.tab_proj = ttk.Frame(self.nb_import, style="White.TFrame", padding=5)
        self.nb_import.add(self.tab_proj, text="Project")
        ttk.Button(self.tab_proj, text="📂 Load Project (.ria)", command=self.load_project_dialog).pack(fill="x", pady=(2, 2))
        ttk.Button(self.tab_proj, text="💾 Save Current Project", command=self.save_project_dialog).pack(fill="x", pady=(2, 2))

        # === 下方公共区域 ===
        f_opts = ttk.Frame(self.grp_file, style="White.TFrame")
        f_opts.pack(fill="x", pady=(5, 0))
        ttk.Label(f_opts, text="Axes:", style="White.TLabel").pack(side="left")
        self.var_axes_entry = tk.StringVar(value="?")
        self.var_axes_entry.trace("w", self._on_axes_change) 
        ttk.Entry(f_opts, textvariable=self.var_axes_entry, width=8).pack(side="left", padx=2)
        self.lbl_ch_indicator = ttk.Label(f_opts, text="", style="White.TLabel")
        self.lbl_ch_indicator.pack(side="left", padx=2)
        self.lbl_z_indicator = ttk.Label(f_opts, text="", style="White.TLabel")
        self.lbl_z_indicator.pack(side="left", padx=2)
        self.lbl_z_proj = ttk.Label(f_opts, text="Z-Proj:", state="disabled", style="White.TLabel")
        self.lbl_z_proj.pack(side="left", padx=(5, 2))
        self.z_proj_var = tk.StringVar()
        self.combo_z_proj = ttk.Combobox(f_opts, textvariable=self.z_proj_var, values=["Max (MIP)", "Ave (AIP)", "None"], state="disabled", width=10)
        self.combo_z_proj.pack(side="left")

        f_actions = ttk.Frame(self.grp_file, style="Card.TFrame")
        f_actions.pack(fill="x", pady=(5, 0))
        
        # 初始状态：显示按钮 (Load)
        self.btn_load = ttk.Button(f_actions, command=self.load_data, state="disabled", text="🚀 Load & Analyze")
        self.btn_load.pack(side="left", fill="both", expand=True, padx=(0, 2))
        
        self.btn_clear_data = ttk.Button(f_actions, text="🗑", width=4, command=self.clear_all_data, style="Gray.TButton")
        self.btn_clear_data.pack(side="right", fill="y")
        
        # 预创建进度条 (默认隐藏)
        self.pb_loading = ttk.Progressbar(f_actions, orient="horizontal", mode="determinate")
        
        self.lbl_status = ttk.Label(self.grp_file, text="", font=("Segoe UI", 8), foreground="#007acc", style="White.TLabel")
        self.lbl_status.pack(fill="x", pady=(2, 0))
        
        # 默认选中 Standard Tiff (Tab 1)
        self.nb_import.select(1)
    
    
    
    
    # 2. 新增 Tab 2 的 Listbox 辅助方法
    def add_separate_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Tiff Files", "*.tif *.tiff"), ("All", "*.*")])
        if files:
            for f in files:
                self.sep_file_paths.append(f)
                self.lst_files.insert(tk.END, os.path.basename(f))
            self.check_ready()

    def remove_separate_file(self):
        selection = self.lst_files.curselection()
        for i in reversed(selection):
            self.lst_files.delete(i)
            del self.sep_file_paths[i]
        self.check_ready()

    def clear_separate_files(self):
        self.lst_files.delete(0, tk.END)
        self.sep_file_paths = []
        self.check_ready()

    # 3. 简化后的 select 方法
    def select_raw_file(self):
        p = filedialog.askopenfilename(filetypes=[("Bio-Formats", "*.oir *.nd2 *.czi *.lif"), ("All", "*.*")])
        if p:
            self.raw_path = p
            basename = os.path.basename(p)
            
            # --- Visual Feedback: Busy State (Start) ---
            # 1. 鼠标变沙漏
            self.root.config(cursor="watch")
            
            # 2. 文件名加沙漏前缀
            self.lbl_raw_path.config(text=f"⏳ {basename}")
            
            # 3. 禁用按钮并修改文字
            self.btn_load.config(state="disabled", text="⏳ Checking...")
            
            # 4. 状态栏显示橙色提示
            self.lbl_status.config(text="Initializing Bio-Formats Reader... (JVM Startup)", foreground="#e67e22")

            # --- Start Thread ---
            # 注意：这里不再调用 check_ready，而是等 metadata 回调后再调用
            threading.Thread(target=self._metadata_task, args=(p,), daemon=True).start()

    def select_tiff_file(self):
        p = filedialog.askopenfilename(filetypes=[("Tiff", "*.tif *.tiff"), ("All", "*.*")])
        if p:
            self.tiff_path = p
            basename = os.path.basename(p)
            
            # --- Visual Feedback: Busy State (Start) ---
            self.root.config(cursor="watch")
            self.lbl_tiff_path.config(text=f"⏳ {basename}")
            self.btn_load.config(state="disabled", text="⏳ Checking...")
            self.lbl_status.config(text="Reading Tiff Tags...", foreground="#e67e22")

            # --- Start Thread ---
            threading.Thread(target=self._metadata_task, args=(p,), daemon=True).start()
            
    # 4. 更新 check_ready
    def check_ready(self):
        tab = self.nb_import.index("current")
        ready = False
        if tab == 0 and hasattr(self, 'raw_path') and self.raw_path: ready = True
        elif tab == 1 and hasattr(self, 'tiff_path') and self.tiff_path: ready = True
        elif tab == 2 and len(self.sep_file_paths) >= 2: ready = True # 至少2个文件
        elif tab == 3: ready = False # Project tab 按钮由内部逻辑控制
        
        self.btn_load.config(state="normal" if ready else "disabled")


    # 5. 【核心】重写 _load_data_thread
    def _load_data_thread(self, params):
        try:
            # 更新状态栏
            self.root.after(0, lambda: self.lbl_status.config(text="Loading Data..."))
            
            # 1. 【关键修复】提取 Z-Proj 和 Axes 参数
            # 这些参数是在 load_data 主线程方法中收集并放入 params 字典的
            z_method = params.get("z_method")
            user_axes = params.get("user_axes")
            
            raw_channels = []
            tab_idx = params["tab_idx"]
            
            # 2. 根据选项卡索引分流处理
            if tab_idx == 0: # === Tab 0: Raw Bio-Formats (OIR/ND2) ===
                self.root.after(0, lambda: self.lbl_status.config(text="Reading Raw Bio-Formats..."))
                # 调用 Model -> IO (AICSImageIO)
                # 传入 z_method 以便在读取后立即做投影
                raw_channels = self.session.load_raw_data(self.raw_path, z_method=z_method)
                
            elif tab_idx == 1: # === Tab 1: Standard Tiff (ImageJ) ===
                self.root.after(0, lambda: self.lbl_status.config(text="Reading Standard Tiff..."))
                # 调用 Model -> IO (TiffFile)
                # 传入 user_axes (用户手动填写的轴序) 和 z_method
                raw_channels = self.session.load_tiff_data(self.tiff_path, user_axes=user_axes, z_method=z_method)
                
            elif tab_idx == 2: # === Tab 2: Separate Files (List) ===
                self.root.after(0, lambda: self.lbl_status.config(text=f"Reading {len(self.sep_file_paths)} files..."))
                # 调用 Model -> IO (Multiple Tiffs)
                # 分离文件通常不需要 override axes，但可能需要 Z-Projection
                raw_channels = self.session.load_separate_files_list(self.sep_file_paths, z_method=z_method)
            
            elif tab_idx == 3: # === Tab 3: Project ===
                # Project 加载逻辑比较特殊，通常由 load_project_logic 直接调度，
                # 但如果代码逻辑走到这里，做个防御性处理
                pass

            # 3. 统一后处理 (传递给主线程)
            self.root.after(0, lambda: self.lbl_status.config(text=""))
            
            # 调用 _load_data_post_process 进行角色分配 (Ask Roles) 和绘图初始化
            # on_success_cb: 用于工程加载成功后恢复参数的回调
            # predefined_roles: 用于工程加载时指定的通道角色
            self.root.after(0, lambda: self._load_data_post_process(
                raw_channels, 
                params.get("on_success_cb"), 
                params.get("predefined_roles")
            ))

        except Exception as e:
            # 错误处理
            err_msg = str(e)
            print(f"[Load Error] {err_msg}") # 打印到控制台方便调试
            import traceback
            traceback.print_exc()
            
            self.root.after(0, lambda: self.lbl_status.config(text="Error"))
            self.root.after(0, lambda: self._load_data_error(err_msg))

    
    def _load_data_post_process(self, raw_channels, on_success_cb=None, predefined_roles=None):
        # --- Stop Animation ---
        self.pb_loading.stop()
        self.pb_loading.configure(mode='determinate', value=100) # 瞬间填满，给一个完成的心理暗示
        self.root.update()
        
        self.is_loading_data = False

        try:
            # 1. 角色分配
            roles = None 
            if predefined_roles is not None:
                roles = predefined_roles
            elif len(raw_channels) > 2:
                self.root.config(cursor="") 
                user_roles = self.ask_channel_roles(len(raw_channels))
                roles = user_roles
            elif len(raw_channels) == 0:
                 raise ValueError(f"No channels loaded.")

            # 2. Set Data
            self.session.set_data(raw_channels, roles)
            
            # --- UI Updates ---
            if self.session.data1 is not None and self.session.data1.shape[0] > 1:
                self.btn_align.config(state="normal", text=self.t("btn_align"), style="TButton")
            else:
                self.btn_align.config(state="disabled")

            if self.session.data2 is not None:
                if "lbl_ratio_thr" in self.ui_elements:
                    self.ui_elements["lbl_ratio_thr"].config(foreground="black")
                self.view_mode = "ratio"
            else:
                if "lbl_ratio_thr" in self.ui_elements:
                    self.ui_elements["lbl_ratio_thr"].config(foreground="gray")
                self.view_mode = "ratio" 

            self.data1_raw = None
            self.btn_undo_align.config(state="disabled", text=self.t("btn_undo_align"), style="Gray.TButton")
            self.rebuild_channel_bar()
            
            self.frame_scale.configure(to=self.data1.shape[0]-1)
            self.var_frame.set(0); self.frame_scale.set(0)
            self.loop_start = 0
            self.loop_end = self.data1.shape[0] - 1
            self.var_loop_active.set(False)
            self._update_loop_label()
            
            count = len(raw_channels)
            if count == 1: 
                self.lbl_ch_indicator.config(text=f" 1 Ch (Int) ", style="BadgeGreen.TLabel")
            else: 
                self.lbl_ch_indicator.config(text=f" {count} Chs (Ratio) ", style="BadgeBlue.TLabel")

            h, w = self.data1.shape[1], self.data1.shape[2]
            self.plot_mgr.init_image((h, w), cmap="coolwarm")
            self.roi_mgr.connect(self.plot_mgr.ax)
            self.update_plot()

            # --- Visual Restore: Progress Bar -> Button ---
            self.pb_loading.pack_forget() # 移除进度条
            
            # 恢复按钮显示 (变成绿色成功状态)
            self.btn_load.config(text="✅ Data Loaded!", style="Success.TButton", cursor="")
            self.btn_load.pack(side="left", fill="both", expand=True, padx=(0, 2)) 
            
            self.root.after(2000, self._reset_load_button)

            if on_success_cb:
                on_success_cb()

        except Exception as e:
            self._load_data_error(str(e))

    def _load_data_error(self, error_msg):
        # 1. 停止动画
        self.pb_loading.stop()
        self.pb_loading.pack_forget()
        
        # 2. 恢复按钮 (原位显示)
        self.btn_load.pack(side="left", fill="both", expand=True, padx=(0, 2))
        self._reset_load_button()
        
        messagebox.showerror("Error", error_msg)
        import traceback
        traceback.print_exc()




    # [新增辅助方法 4] 重置按钮
    def _reset_load_button(self):
        # 恢复文字和样式
        self.btn_load.config(text="🚀 Load & Analyze", state="normal", style="TButton", cursor="")





    # src/gui.py

    def clear_all_data(self):
        """
        [修改版] 清除所有数据并重置 UI 到初始状态。
        """
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

        # --- 【修复】重置路径变量和 UI ---
        self.c1_path = None
        self.c2_path = None
        self.dual_path = None
        self.raw_path = None
        self.tiff_path = None
        
        # 重置 Raw Tab UI
        if hasattr(self, 'lbl_raw_path'):
            self.lbl_raw_path.config(text=self.t("lbl_no_file"))
            
        # 重置 Tiff Tab UI
        if hasattr(self, 'lbl_tiff_path'):
            self.lbl_tiff_path.config(text=self.t("lbl_no_file"))
            
        # 重置 Separate Listbox UI
        if hasattr(self, 'lst_files'):
            self.lst_files.delete(0, tk.END)
        self.sep_file_paths = []

        # --- File Loading 区域完全重置 ---
        if hasattr(self, 'var_axes_entry'):
            self.var_axes_entry.set("?") 

        if hasattr(self, 'is_interleaved_var'):
            self.is_interleaved_var.set(False)
        if hasattr(self, 'chk_inter'):
            self.chk_inter.config(state="normal")

        if hasattr(self, 'var_n_channels'):
            self.var_n_channels.set(2)
        if hasattr(self, 'sp_channels'):
            self.sp_channels.config(state="normal")
        if hasattr(self, 'lbl_ch_count'):
            self.lbl_ch_count.config(foreground="#333333") 

        if hasattr(self, 'lbl_status'):
            self.lbl_status.config(text="")
        
        if hasattr(self, 'lbl_ch_indicator'):
            self.lbl_ch_indicator.config(text="", style="White.TLabel")

        if hasattr(self, 'lbl_z_indicator'):
            self.lbl_z_indicator.config(text="", style="White.TLabel")

        if hasattr(self, 'lbl_z_proj'):
            self.lbl_z_proj.config(state="disabled", foreground="#A0A0A0")
            self.combo_z_proj.config(state="disabled")
            if hasattr(self, 'z_proj_var'):
                self.z_proj_var.set("") 

        # --------------------------------------

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
        # [紧凑版] 使用单行布局：[Label] [Scale] [Value]
        f = ttk.Frame(parent, style="White.TFrame")
        f.pack(fill="x", pady=0) # 移除垂直间距
        
        # 1. 标题 (左) - 固定宽度对齐
        lbl = ttk.Label(f, width=9, anchor="w", style="White.TLabel") 
        lbl.pack(side="left") 
        self.ui_elements[label_key] = lbl
        
        # 2. 数值 (右) - 先pack右边，确保数值不被遮挡
        val_lbl = ttk.Label(f, text=str(variable.get()), width=4, anchor="e",
                            foreground="#007acc", font=self.f_bold, style="White.TLabel")
        val_lbl.pack(side="right", padx=(2, 0))
        self.ui_elements[f"val_{label_key}"] = val_lbl 
        
        # 3. 滑动条 (中) - 自动拉伸
        def on_slide(v):
            val = float(v)
            if is_int: val = int(val)
            variable.set(val)
            fmt = "{:.0f}" if is_int else "{:.1f}"
            val_lbl.config(text=fmt.format(val))
            if not self.is_playing: self.update_plot()
            
        s = ttk.Scale(f, from_=min_v, to=max_v, command=on_slide)
        s.set(variable.get())
        s.pack(side="left", fill="x", expand=True, padx=5)

    def create_bg_slider(self, parent, label_key, min_v, max_v, variable):
        # [紧凑版] 背景滑块也改为单行
        f = ttk.Frame(parent, style="White.TFrame")
        f.pack(fill="x", pady=0)
        
        # 1. 标题
        lbl = ttk.Label(f, width=9, anchor="w", style="White.TLabel") 
        lbl.pack(side="left") 
        self.ui_elements[label_key] = lbl
        
        # 2. 数值
        val_lbl = ttk.Label(f, text=str(int(variable.get())), width=4, anchor="e",
                            foreground="#007acc", font=self.f_bold, style="White.TLabel")
        val_lbl.pack(side="right", padx=(2, 0))
        self.lbl_bg_value_display = val_lbl 
        
        def on_move(v): val_lbl.config(text=f"{int(float(v))}")
        def on_release(event):
            val = int(self.bg_scale.get())
            variable.set(val)
            self.recalc_background()
            self.update_plot()
            
        self.bg_scale = ttk.Scale(f, from_=min_v, to=max_v, command=on_move)
        self.bg_scale.set(variable.get())
        self.bg_scale.pack(side="left", fill="x", expand=True, padx=5)
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

    # src/gui.py

    def save_stack_thread(self):
        """
        启动保存处理后的堆栈 (Ratio/Intensity Stack) 的线程。
        这是保存“结果”，即用户在屏幕上看到的伪彩视频。
        """
        if self.data1 is None: return
        
        # 1. 在主线程弹出对话框 (UI 线程安全)
        ts = datetime.datetime.now().strftime("%H%M%S")
        # 默认文件名提示这是处理过的结果
        default_name = f"Result_{self.view_mode}_Stack_{ts}.tif"
        path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=default_name)
        
        if not path: return # 用户取消
        
        # 2. 禁用按钮
        self.btn_save_stack.config(state="disabled", text="⏳ Saving...")
        
        # 3. 启动线程，把 path 传进去
        threading.Thread(target=self.save_stack_task, args=(path,), daemon=True).start()
    
    def save_stack_task(self, path):
        """
        [修复版] 接收 path 参数，执行保存逻辑。
        """
        try:
            # 收集参数 (从 UI 变量获取)
            params = {
                "int_thresh": self.var_int_thresh.get(),
                "ratio_thresh": self.var_ratio_thresh.get(),
                "smooth": int(self.var_smooth.get()),
                "log_scale": self.log_var.get(),
                "use_custom_bg": self.use_custom_bg_var.get()
            }

            # 定义进度回调
            def progress_cb(curr, total):
                self.root.after(0, lambda: self.ui_elements["btn_save_stack"].config(text=f"⏳ {curr}/{total}"))

            # [CALL MODEL] 执行保存
            self.session.export_processed_stack(path, params, progress_callback=progress_cb)
            
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Stack saved to:\n{path}"))
            
        except Exception as e: 
            self.root.after(0, lambda: messagebox.showerror("Error", f"Save failed: {e}"))
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



    # --- [GUI Part 2] 导出回调函数 (新版) ---

    def save_current_frame(self):
        """保存当前展示的单帧 (所见即所得)"""
        if self.session.data1 is None: return
        
        ts = datetime.datetime.now().strftime("%H%M%S")
        # 智能命名：Frame_123_Ratio.tif
        fname = f"Frame_{self.var_frame.get()}_{self.view_mode}_{ts}.tif"
        path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=fname, title="Save Presentation Snapshot")
        if not path: return
        
        params = {
            "int_thresh": self.var_int_thresh.get(),
            "ratio_thresh": self.var_ratio_thresh.get(),
            "smooth": int(self.var_smooth.get()),
            "log_scale": self.log_var.get(),
            "use_custom_bg": self.use_custom_bg_var.get()
        }
        
        try:
            self.session.export_current_frame(path, self.var_frame.get(), params)
            messagebox.showinfo("Success", f"Snapshot saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save frame: {e}")

    def save_results_thread(self):
        """保存全量分析数据 (Ratio + Num + Den + Aux)"""
        if self.data1 is None: return
        
        ts = datetime.datetime.now().strftime("%H%M%S")
        fname = f"Analysis_Results_{ts}.tif"
        path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=fname, title="Save Quantification Data")
        if not path: return
        
        self.btn_save_results.config(state="disabled", text="⏳ Saving...")
        threading.Thread(target=self.save_results_task, args=(path,), daemon=True).start()


    def save_results_task(self, path):
        try:
            params = {
                "int_thresh": self.var_int_thresh.get(),
                "ratio_thresh": self.var_ratio_thresh.get(),
                "smooth": int(self.var_smooth.get()),
                "log_scale": self.log_var.get(),
                "use_custom_bg": self.use_custom_bg_var.get()
            }
            
            def progress_cb(curr, total):
                self.root.after(0, lambda: self.btn_save_results.config(text=f"⏳ {curr}/{total}"))

            # 调用新的 Model 方法
            self.session.export_results_data(path, params, progress_callback=progress_cb)
            
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Analysis data saved to:\n{path}\n\nContains: Ratio, Ch1, Ch2..."))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Save failed: {e}"))
            import traceback; traceback.print_exc()
        finally:
            self.root.after(0, lambda: self.btn_save_results.config(state="normal", text="💾 Save Results (Stack)"))


    def save_preprocessed_thread(self):
        """保存中间态工作流数据 (Raw Aligned)"""
        if self.data1 is None: return
        
        # 智能命名
        z_method = self.z_proj_var.get()
        name_parts = ["Preprocessed"]
        if "Max" in z_method: name_parts.append("MIP")
        elif "Ave" in z_method: name_parts.append("AIP")
        if self.session.alignment_matrices: name_parts.append("Aligned")
        name_parts.append(datetime.datetime.now().strftime("%H%M%S"))
        
        fname = "_".join(name_parts) + ".tif"
        path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=fname, title="Save Workflow State")
        if not path: return
        
        self.btn_save_pre.config(state="disabled", text="⏳ Saving...")
        threading.Thread(target=self.save_preprocessed_task, args=(path,), daemon=True).start()


    def save_preprocessed_task(self, path):
        try:
            self.session.export_input_data(path)
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Workflow saved to:\n{path}\n\nTip: You can reload this file later to skip alignment."))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Save failed: {e}"))
        finally:
            self.root.after(0, lambda: self.btn_save_pre.config(state="normal", text="📥 Save Preprocessed"))


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
                if not path or not os.path.exists(path): return path
                try: return os.path.relpath(path, project_dir)
                except ValueError: return path
           
            # --- 1. 源文件信息 ---
            source_mode = "unknown"
            path_dual = None
            path_list = []
            
            if getattr(self, 'raw_path', None):
                source_mode = "raw"
                path_dual = to_relative(self.raw_path)
            elif getattr(self, 'tiff_path', None):
                source_mode = "tiff"
                path_dual = to_relative(self.tiff_path)
            elif getattr(self, 'sep_file_paths', None) and len(self.sep_file_paths) > 0:
                source_mode = "separate_list"
                path_list = [to_relative(p) for p in self.sep_file_paths]
            elif self.dual_path: 
                source_mode = "single"
                path_dual = to_relative(self.dual_path)
            
            # 计算真实通道数
            n_ch = 2
            if self.data1 is not None:
                n_ch = 1
                if self.data2 is not None: n_ch += 1
                if hasattr(self, 'data_aux'): n_ch += len(self.data_aux)

            source_info = {
                "mode": source_mode,
                "path_dual": path_dual,
                "path_list": path_list,
                "n_channels": n_ch,
                "z_proj_method": self.z_proj_var.get() if hasattr(self, 'z_proj_var') else None,
                "channel_roles": self.session.current_roles,
                "axes": self.var_axes_entry.get() if hasattr(self, 'var_axes_entry') else None
            }
            
            # --- 2. 图像处理与分析参数 (补全) ---
            params = {
                # 基础处理
                "int_thresh": self.var_int_thresh.get(),
                "ratio_thresh": self.var_ratio_thresh.get(),
                "smooth": self.var_smooth.get(),
                "bg_percent": self.var_bg.get(),
                "log_scale": self.log_var.get(),
                
                # 自定义背景 ROI
                "use_custom_bg": self.use_custom_bg_var.get(),
                "custom_bg1": self.custom_bg1,
                "custom_bg2": self.custom_bg2,

                # [新增] 绘图分析参数 (这部分之前漏了)
                "interval": self.var_interval.get(), # 时间间隔
                "unit": self.combo_unit.get(),       # 时间单位
                "normalization": self.norm_var.get() # 归一化开关 (Delta R/R0)
            }
            
            # --- 3. 视图与播放设置 (补全) ---
            view_settings = {
                "ratio_mode": self.ratio_mode_var.get(),
                "cmap": self.cmap_var.get(),
                "bg_color": self.bg_color_var.get(),
                "lock_range": self.lock_var.get(),
                "vmin": self.entry_vmin.get(),
                "vmax": self.entry_vmax.get(),
                "view_mode": self.view_mode,
                
                # [新增] 播放器状态
                "fps": self.fps,
                "current_frame": self.var_frame.get(),
                "loop_settings": {
                    "active": self.var_loop_active.get(),
                    "start": self.loop_start,
                    "end": self.loop_end
                }
            }
            
            # 4. 收集 ROI
            rois = self.roi_mgr.get_all_rois_data()
            
            # 5. 收集 Alignment (配准矩阵)
            matrices_json = []
            if self.session.alignment_matrices:
                matrices_json = [m.tolist() for m in self.session.alignment_matrices]

            # 6. 收集 Plot Windows (弹出的曲线窗口配置)
            plot_window_data = {}
            if self.plot_mgr and self.plot_mgr.plot_window_controller:
                plot_window_data = self.plot_mgr.plot_window_controller.get_settings()

            kymo_data_list = []
            for roi_id, win in self.kymo_windows.items():
                if win.is_open:
                    kymo_data_list.append(win.get_settings())

            # 写入总字典
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
                "plot_window": plot_window_data,
                "kymographs": kymo_data_list
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=4)
                
            messagebox.showinfo("Success", "Project saved successfully!")
            
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
            import traceback
            traceback.print_exc()



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
            
            project_dir = os.path.dirname(os.path.abspath(filepath))

            def resolve_path(path):
                if not path: return None
                abs_path_rel = os.path.abspath(os.path.join(project_dir, path))
                if os.path.exists(abs_path_rel): return abs_path_rel
                if os.path.exists(path): return path
                return None

            # --- 阶段 1: 恢复文件源与 Tab 状态 ---
            self.clear_all_data()
            
            mode = src.get("mode", "single")
            
            # 根据模式切换 Tab 并填充路径
            if mode == "raw":
                p = resolve_path(src.get("path_dual"))
                if p:
                    self.nb_import.select(0)
                    self.raw_path = p
                    self.lbl_raw_path.config(text=os.path.basename(p))
            
            elif mode == "tiff" or mode == "single":
                p = resolve_path(src.get("path_dual"))
                if p:
                    self.nb_import.select(1)
                    self.tiff_path = p
                    self.lbl_tiff_path.config(text=os.path.basename(p))
            
            elif mode == "separate_list":
                paths = src.get("path_list", [])
                resolved_paths = []
                for p_raw in paths:
                    rp = resolve_path(p_raw)
                    if rp: resolved_paths.append(rp)
                
                if len(resolved_paths) >= 2:
                    self.nb_import.select(2)
                    self.sep_file_paths = resolved_paths
                    for p in self.sep_file_paths:
                        self.lst_files.insert(tk.END, os.path.basename(p))
            
            elif mode == "separate":
                p1 = resolve_path(src.get("path_c1"))
                p2 = resolve_path(src.get("path_c2"))
                if p1 and p2:
                    self.nb_import.select(2)
                    self.sep_file_paths = [p1, p2]
                    self.lst_files.insert(tk.END, os.path.basename(p1))
                    self.lst_files.insert(tk.END, os.path.basename(p2))

            # 恢复 Z-Projection 设置
            z_method = src.get("z_proj_method")
            if z_method and hasattr(self, 'z_proj_var'):
                self.lbl_z_proj.config(state="normal")
                self.combo_z_proj.config(state="readonly")
                self.z_proj_var.set(z_method)
            
            # 恢复 Axes
            saved_axes = src.get("axes", None)
            if saved_axes and hasattr(self, 'var_axes_entry'):
                self.var_axes_entry.set(saved_axes)

            self.check_ready()
            saved_roles = src.get("channel_roles", None)

            # --- 阶段 2: 数据加载成功后的回调 (恢复所有参数) ---
            def restore_settings_and_rois():
                print("Restoring Project Params & ROIs...")
                try:
                    # 1. 恢复核心处理参数
                    self.var_int_thresh.set(params.get("int_thresh", 0))
                    self.var_ratio_thresh.set(params.get("ratio_thresh", 0))
                    self.var_smooth.set(params.get("smooth", 0))
                    self.log_var.set(params.get("log_scale", False))
                    
                    # [新增] 恢复 Interval / Unit / Norm
                    if "interval" in params: self.var_interval.set(params["interval"])
                    if "unit" in params: self.combo_unit.set(params["unit"])
                    if "normalization" in params: self.norm_var.set(params["normalization"])

                    # 刷新滑块文字
                    if "val_lbl_int_thr" in self.ui_elements:
                        self.ui_elements["val_lbl_int_thr"].config(text=f"{self.var_int_thresh.get():.1f}")
                    if "val_lbl_ratio_thr" in self.ui_elements:
                        self.ui_elements["val_lbl_ratio_thr"].config(text=f"{self.var_ratio_thresh.get():.1f}")
                    if "val_lbl_smooth" in self.ui_elements:
                        self.ui_elements["val_lbl_smooth"].config(text=f"{int(self.var_smooth.get())}")

                    # 2. 恢复背景
                    bg_pct = params.get("bg_percent", 5.0)
                    self.var_bg.set(bg_pct)
                    if hasattr(self, 'lbl_bg_value_display'):
                        self.lbl_bg_value_display.config(text=f"{int(bg_pct)}")
                    self.recalc_background()
                    
                    if params.get("use_custom_bg", False):
                        self.custom_bg1 = params.get("custom_bg1", 0.0)
                        self.custom_bg2 = params.get("custom_bg2", 0.0)
                        self.use_custom_bg_var.set(True)
                        self.toggle_bg_mode()
                        self.lbl_bg_val.config(text=f"ROI Val: {self.custom_bg1:.1f} / {self.custom_bg2:.1f}")
                    else:
                        self.use_custom_bg_var.set(False)
                        self.toggle_bg_mode()
                    
                    # 3. 恢复视图参数
                    self.ratio_mode_var.set(view.get("ratio_mode", "c1_c2"))
                    self.update_mode_options()
                    self.cmap_var.set(view.get("cmap", "coolwarm"))
                    self.bg_color_var.set(view.get("bg_color", "Trans"))
                    
                    # [新增] 恢复播放器状态 (Loop, FPS)
                    self.fps = view.get("fps", 10)
                    # 更新 FPS 菜单显示 (hacky but works)
                    self.fps_var.set(f"{self.fps} FPS")
                    
                    loop_settings = view.get("loop_settings", {})
                    self.loop_start = loop_settings.get("start", 0)
                    self.loop_end = loop_settings.get("end", self.data1.shape[0]-1)
                    self.var_loop_active.set(loop_settings.get("active", False))
                    self._update_loop_label() # 刷新 UI 文字

                    # 恢复锁定范围
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

                    # 4. 恢复配准状态
                    alignment_data = data.get("alignment", {})
                    matrices = alignment_data.get("matrices", [])
                    if matrices:
                        print(f"Applying {len(matrices)} alignment matrices...")
                        self.session.apply_existing_alignment(matrices)
                        # 更新按钮状态为“已配准”
                        self.btn_align.config(state="normal", text=self.t("btn_align_done"), style="Success.TButton")
                        self.btn_undo_align.config(state="normal", text=self.t("btn_undo_align"), style="Gray.TButton")

                    # 5. 恢复 ROIs
                    self.roi_mgr.restore_rois_from_data(rois)
                    if any(r['type'] == 'line' for r in self.roi_mgr.roi_list):
                        self.btn_kymo.config(state="normal")

                    # 6. 恢复 Kymograph 窗口
                    saved_kymos = data.get("kymographs", [])
                    for k_settings in saved_kymos:
                        r_id = k_settings.get("roi_id")
                        target_roi = next((r for r in self.roi_mgr.roi_list if r['id'] == r_id), None)
                        if target_roi:
                            k_win = KymographWindow(self.root, r_id, self)
                            self.kymo_windows[r_id] = k_win
                            k_win.apply_settings(k_settings)
                            self.update_kymograph_for_roi(target_roi)
                    
                    # 7. 恢复 Plot Window 设置
                    plot_data = data.get("plot_window", {})
                    if plot_data and self.plot_mgr and self.plot_mgr.plot_window_controller:
                        self.plot_mgr.plot_window_controller.apply_settings(plot_data)
                        if plot_data.get("is_open", False):
                            self.plot_roi_curve()

                    # 8. 最终刷新
                    self.set_view_mode(view.get("view_mode", "ratio")) 
                    
                    # 恢复到保存时的那一帧
                    saved_frame = view.get("current_frame", 0)
                    self.var_frame.set(saved_frame)
                    self.frame_scale.set(saved_frame)
                    self.on_frame_slide(saved_frame)
                    
                    self.update_plot()
                    self.update_cmap()
                    
                    messagebox.showinfo("Success", "Project loaded successfully!")
                    
                except Exception as e:
                    print(f"Restore Error: {e}")
                    import traceback; traceback.print_exc()

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