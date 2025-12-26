import tkinter as tk
from tkinter import filedialog, messagebox, ttk, Toplevel
import numpy as np
import tifffile as tiff
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.widgets import RectangleSelector
import os
import warnings
import datetime
import threading
import time

# 导入核心算法
from .processing import calculate_background, process_frame_ratio

warnings.filterwarnings('ignore')

# 语言包 (保持不变)
LANG_MAP = {
    "window_title": {"cn": "比率成像分析器 (Ver 1.7 - JOSS)", "en": "Ratio Imaging Analyzer (Ver 1.7 - JOSS)"},
    "header_title": {"cn": "Ratio Imaging Analyzer (RIA)", "en": "Ratio Imaging Analyzer (RIA)"},
    # ... (为了节省篇幅，这里请把之前 V1.7 代码里的 LANG_MAP 字典完整复制过来) ...
    # 务必把之前的 LANG_MAP 完整内容贴在这里
    # Groups
    "grp_file": {"cn": "1. 文件加载 (File Loading)", "en": "1. File Loading"},
    "grp_calc": {"cn": "2. 参数计算 (Calculation)", "en": "2. Calculation"},
    "grp_view": {"cn": "3. 显示设置 (Display)", "en": "3. Display Settings"},
    "grp_save": {"cn": "4. 数据保存 (Export)", "en": "4. Export Data"},

    # File Section
    "btn_c1": {"cn": "📂 选择通道 1", "en": "📂 Select Ch1"},
    "btn_c2": {"cn": "📂 选择通道 2", "en": "📂 Select Ch2"},
    "btn_load": {"cn": "🚀 加载并分析", "en": "🚀 Load & Analyze"},
    "lbl_no_file": {"cn": "未选择文件", "en": "No File Selected"},

    # Calc Section
    "lbl_int_thr": {"cn": "Intensity Min (强度阈值)", "en": "Intensity Min"},
    "lbl_ratio_thr": {"cn": "Ratio Min (比率阈值)", "en": "Ratio Min"},
    "lbl_smooth": {"cn": "Smooth Size (平滑)", "en": "Smooth Size"},
    "lbl_bg": {"cn": "BG Percentile (背景扣除)", "en": "BG Percentile"},
    "chk_log": {"cn": "Log Scale (对数变换)", "en": "Log Scale"},

    # View Section
    "lbl_cmap": {"cn": "Colormap (伪彩):", "en": "Colormap:"},
    "lbl_bg_col": {"cn": "BG Color (无效区域):", "en": "NaN Color:"},
    "lbl_scale": {"cn": "Color Scale (范围):", "en": "Color Scale Range:"},
    "chk_lock": {"cn": "🔒 锁定范围 (Manual)", "en": "🔒 Lock Range"},
    "btn_apply": {"cn": "应用范围", "en": "Apply Range"},

    # Save Section
    "btn_save_frame": {"cn": "💾 保存当前帧 (.tif)", "en": "💾 Save Current Frame"},
    "btn_save_stack": {"cn": "📚 保存整个序列 (.tif)", "en": "📚 Save Entire Stack"},
    
    # ROI Section
    "grp_roi": {"cn": "ROI 分析 (Region of Interest)", "en": "ROI Analysis"},
    "btn_draw_roi": {"cn": "✏️ 绘制 ROI", "en": "✏️ Draw ROI"},
    "btn_clear_roi": {"cn": "❌ 清除 ROI", "en": "❌ Clear ROI"},
    "chk_live_plot": {"cn": "实时绘图", "en": "Live Plot"},
    "btn_plot_roi": {"cn": "📈 生成曲线", "en": "📈 Plot Curve"},
    "lbl_interval": {"cn": "每帧间隔:", "en": "Time Interval:"},
    "lbl_unit": {"cn": "单位:", "en": "Unit:"},
    "btn_copy_all": {"cn": "📋 复制: Time & Ratio", "en": "📋 Copy: Time & Ratio"},
    "btn_copy_y": {"cn": "🔢 复制: Ratio Only", "en": "🔢 Copy: Ratio Only"},
    
    # Player
    "lbl_player": {"cn": "播放控制 (Player)", "en": "Player Control"},
    "lbl_speed": {"cn": "速度:", "en": "Speed:"},
    
    # Switch Button
    "btn_lang": {"cn": "🌐 Switch to English", "en": "🌐 切换到中文"}
}

class RatioAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.current_lang = "cn"
        self.ui_elements = {}
        self.root.geometry("1280x980")
        
        # --- Data Variables ---
        self.data1 = None
        self.data2 = None
        self.cached_bg1 = 0
        self.cached_bg2 = 0
        self.im_object = None 
        self.ax = None
        self.c1_path = None
        self.c2_path = None
        self.is_playing = False
        self.fps = 10 
        
        # ROI Variables
        self.roi_selector = None
        self.roi_coords = None
        self.plot_window = None
        self.plot_ax = None
        self.plot_canvas = None
        self.is_calculating_roi = False 

        # --- Style ---
        style = ttk.Style()
        style.configure("Big.TLabel", font=("Helvetica", 20, "bold")) 
        style.configure("Copyright.TLabel", foreground="#555555", font=("Segoe UI", 9))

        self.setup_ui()
        self.update_language()

    def t(self, key):
        return LANG_MAP[key][self.current_lang]

    # ... (这里省略 setup_ui, create_slider 等辅助 UI 函数，请直接复制 V1.7 的代码) ...
    # ... 为了保持整洁，请把 V1.7 的 setup_ui 到 create_player_bar 的代码全部贴在这里 ...
    # 下面我只列出被修改的核心逻辑函数

    def setup_ui(self):
        # 1. Top Header
        header_frame = ttk.Frame(self.root, padding=15)
        header_frame.pack(side="top", fill="x")
        self.lbl_title = ttk.Label(header_frame, style="Big.TLabel")
        self.lbl_title.pack(side="left")
        self.ui_elements["header_title"] = self.lbl_title
        self.btn_lang = ttk.Button(header_frame, command=self.toggle_language, width=20)
        self.btn_lang.pack(side="right")
        self.ui_elements["btn_lang"] = self.btn_lang

        # 2. Bottom Copyright
        footer_frame = tk.Frame(self.root, bg="#f0f0f0", height=30)
        footer_frame.pack(side="bottom", fill="x")
        self.lbl_copyright = ttk.Label(footer_frame, style="Copyright.TLabel", 
                                       text="© Dr. Kui Wang      🌐 www.cns.ac.cn      ✉ k@cns.ac.cn")
        self.lbl_copyright.pack(pady=8)

        # 3. Main Split
        self.main_pane = ttk.PanedWindow(self.root, orient="horizontal")
        self.main_pane.pack(side="top", fill="both", expand=True, padx=5, pady=5)

        # === Left Panel ===
        self.frame_left = ttk.Frame(self.main_pane, padding=10, width=380)
        self.main_pane.add(self.frame_left, weight=0)

        # Controls
        self.grp_file = ttk.LabelFrame(self.frame_left, padding=10)
        self.grp_file.pack(fill="x", pady=5)
        self.ui_elements["grp_file"] = self.grp_file
        self.create_file_row(self.grp_file, "btn_c1", self.select_c1, "lbl_c1_path")
        self.create_file_row(self.grp_file, "btn_c2", self.select_c2, "lbl_c2_path")
        self.btn_load = ttk.Button(self.grp_file, command=self.load_data, state="disabled")
        self.btn_load.pack(fill="x", pady=10)
        self.ui_elements["btn_load"] = self.btn_load

        self.grp_calc = ttk.LabelFrame(self.frame_left, padding=10)
        self.grp_calc.pack(fill="x", pady=5)
        self.ui_elements["grp_calc"] = self.grp_calc
        self.var_int_thresh = tk.DoubleVar(value=0.0)
        self.var_ratio_thresh = tk.DoubleVar(value=0.0)
        self.var_smooth = tk.DoubleVar(value=0.0)
        self.var_bg = tk.DoubleVar(value=5.0)
        self.create_slider(self.grp_calc, "lbl_int_thr", 0.0, 500.0, 1.0, self.var_int_thresh)
        self.create_slider(self.grp_calc, "lbl_ratio_thr", 0.0, 5.0, 0.1, self.var_ratio_thresh)
        self.create_slider(self.grp_calc, "lbl_smooth", 0, 10, 1, self.var_smooth, is_int=True)
        self.create_bg_slider(self.grp_calc, "lbl_bg", 0, 50, self.var_bg)
        self.log_var = tk.BooleanVar(value=False)
        self.chk_log = ttk.Checkbutton(self.grp_calc, variable=self.log_var, command=self.update_plot)
        self.chk_log.pack(anchor="w", pady=5)
        self.ui_elements["chk_log"] = self.chk_log

        self.grp_view = ttk.LabelFrame(self.frame_left, padding=10)
        self.grp_view.pack(fill="x", pady=5)
        self.ui_elements["grp_view"] = self.grp_view
        self.lbl_cmap = ttk.Label(self.grp_view); self.lbl_cmap.pack(anchor="w")
        self.ui_elements["lbl_cmap"] = self.lbl_cmap
        self.cmap_var = tk.StringVar(value="jet")
        ttk.OptionMenu(self.grp_view, self.cmap_var, "jet", "jet", "Spectral", "viridis", "magma", "coolwarm", command=lambda _: self.update_cmap()).pack(fill="x", pady=2)
        
        self.lbl_bg_col = ttk.Label(self.grp_view); self.lbl_bg_col.pack(anchor="w", pady=(5,0))
        self.ui_elements["lbl_bg_col"] = self.lbl_bg_col
        self.bg_color_var = tk.StringVar(value="Transparent")
        ttk.OptionMenu(self.grp_view, self.bg_color_var, "Transparent", "Transparent", "Black", "White", "Gray", command=lambda _: self.update_cmap()).pack(fill="x", pady=2)
        
        self.lbl_scale = ttk.Label(self.grp_view); self.lbl_scale.pack(anchor="w", pady=(10,0))
        self.ui_elements["lbl_scale"] = self.lbl_scale
        self.lock_var = tk.BooleanVar(value=False)
        self.chk_lock = ttk.Checkbutton(self.grp_view, variable=self.lock_var, command=self.toggle_scale_mode)
        self.chk_lock.pack(anchor="w")
        self.ui_elements["chk_lock"] = self.chk_lock
        
        range_frame = ttk.Frame(self.grp_view)
        range_frame.pack(fill="x", pady=2)
        self.entry_vmin = ttk.Entry(range_frame, width=8); self.entry_vmin.pack(side="left"); self.entry_vmin.insert(0,"0.0")
        self.entry_vmax = ttk.Entry(range_frame, width=8); self.entry_vmax.pack(side="left", padx=5); self.entry_vmax.insert(0,"1.0")
        self.entry_vmin.config(state="disabled"); self.entry_vmax.config(state="disabled")
        self.btn_apply = ttk.Button(self.grp_view, command=self.update_plot)
        self.btn_apply.pack(fill="x", pady=5)
        self.ui_elements["btn_apply"] = self.btn_apply

        self.grp_save = ttk.LabelFrame(self.frame_left, padding=10)
        self.grp_save.pack(fill="x", pady=5)
        self.ui_elements["grp_save"] = self.grp_save
        self.btn_save_frame = ttk.Button(self.grp_save, command=self.save_current_frame)
        self.btn_save_frame.pack(fill="x", pady=2)
        self.ui_elements["btn_save_frame"] = self.btn_save_frame
        self.btn_save_stack = ttk.Button(self.grp_save, command=self.save_stack_thread)
        self.btn_save_stack.pack(fill="x", pady=2)
        self.ui_elements["btn_save_stack"] = self.btn_save_stack

        # === Right Panel ===
        self.frame_right = ttk.Frame(self.main_pane, padding=10)
        self.main_pane.add(self.frame_right, weight=4)

        self.plot_container = ttk.Frame(self.frame_right)
        self.plot_container.pack(fill="both", expand=True)
        self.fig = plt.Figure(figsize=(6, 5), dpi=100)
        self.fig.patch.set_facecolor('#f0f0f0')
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_container)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        self.canvas.mpl_connect('motion_notify_event', self.on_roi_mouse_move)

        self.create_roi_panel(self.frame_right)
        self.create_player_bar(self.frame_right)

    def toggle_language(self):
        self.current_lang = "en" if self.current_lang == "cn" else "cn"
        self.update_language()

    def update_language(self):
        self.root.title(self.t("window_title"))
        for key, widget in self.ui_elements.items():
            try: widget.config(text=self.t(key))
            except: pass
        if self.c1_path is None: self.lbl_c1_path.config(text=self.t("lbl_no_file"))
        if self.c2_path is None: self.lbl_c2_path.config(text=self.t("lbl_no_file"))

    def create_file_row(self, parent, btn_key, cmd, lbl_attr):
        f = ttk.Frame(parent); f.pack(fill="x", pady=2)
        btn = ttk.Button(f, width=15, command=cmd); btn.pack(side="left")
        self.ui_elements[btn_key] = btn
        lbl = ttk.Label(f, text="No File", foreground="gray"); lbl.pack(side="left", padx=5)
        setattr(self, lbl_attr, lbl)

    def create_slider(self, parent, label_key, min_v, max_v, step, variable, is_int=False):
        f = ttk.Frame(parent); f.pack(fill="x", pady=(5,0))
        h = ttk.Frame(f); h.pack(fill="x")
        lbl = ttk.Label(h); lbl.pack(side="left")
        self.ui_elements[label_key] = lbl
        val_lbl = ttk.Label(h, text=str(variable.get()), foreground="blue"); val_lbl.pack(side="right")
        def on_slide(v):
            val = float(v)
            if is_int: val = int(val)
            variable.set(val)
            val_lbl.config(text=str(val))
            if not self.is_playing: self.update_plot()
        s = ttk.Scale(f, from_=min_v, to=max_v, command=on_slide); s.set(variable.get()); s.pack(fill="x")

    def create_bg_slider(self, parent, label_key, min_v, max_v, variable):
        f = ttk.Frame(parent); f.pack(fill="x", pady=(5,0))
        h = ttk.Frame(f); h.pack(fill="x")
        lbl = ttk.Label(h); lbl.pack(side="left")
        self.ui_elements[label_key] = lbl
        val_lbl = ttk.Label(h, text=str(variable.get()), foreground="red"); val_lbl.pack(side="right")
        def on_move(v): val_lbl.config(text=f"{int(float(v))}")
        def on_release(event):
            val = int(self.bg_scale.get())
            variable.set(val)
            self.recalc_background()
            self.update_plot()
        self.bg_scale = ttk.Scale(f, from_=min_v, to=max_v, command=on_move)
        self.bg_scale.set(variable.get()); self.bg_scale.pack(fill="x")
        self.bg_scale.bind("<ButtonRelease-1>", on_release)

    def create_roi_panel(self, parent):
        self.grp_roi = ttk.LabelFrame(parent, padding=5)
        self.grp_roi.pack(fill="x", side="bottom", pady=5)
        self.ui_elements["grp_roi"] = self.grp_roi

        frame = ttk.Frame(self.grp_roi); frame.pack(fill="x", pady=2)
        
        self.btn_draw = ttk.Button(frame, command=self.activate_roi_drawer)
        self.btn_draw.pack(side="left", padx=5)
        self.ui_elements["btn_draw_roi"] = self.btn_draw

        self.btn_clear = ttk.Button(frame, command=self.clear_roi)
        self.btn_clear.pack(side="left", padx=5)
        self.ui_elements["btn_clear_roi"] = self.btn_clear

        self.live_plot_var = tk.BooleanVar(value=False)
        self.chk_live = ttk.Checkbutton(frame, variable=self.live_plot_var)
        self.chk_live.pack(side="left", padx=10)
        self.ui_elements["chk_live_plot"] = self.chk_live

        self.btn_plot = ttk.Button(frame, command=self.plot_roi_curve)
        self.btn_plot.pack(side="left", padx=5)
        self.ui_elements["btn_plot_roi"] = self.btn_plot

        # Row 2: Time Settings
        row2 = ttk.Frame(self.grp_roi); row2.pack(fill="x", pady=2)
        
        lbl_time = ttk.Label(row2); lbl_time.pack(side="left", padx=(5,2))
        self.ui_elements["lbl_interval"] = lbl_time
        
        self.var_interval = tk.DoubleVar(value=1.0)
        ttk.Entry(row2, textvariable=self.var_interval, width=8).pack(side="left")
        
        # New: Time Unit Selection
        lbl_unit = ttk.Label(row2, text="Unit:")
        lbl_unit.pack(side="left", padx=(10, 2))
        self.ui_elements["lbl_unit"] = lbl_unit

        self.combo_unit = ttk.Combobox(row2, values=["s", "m", "h"], width=3, state="readonly")
        self.combo_unit.set("s")
        self.combo_unit.pack(side="left", padx=2)

    def create_player_bar(self, parent):
        pf = ttk.LabelFrame(parent, padding=5); pf.pack(fill="x", side="bottom", pady=5)
        self.ui_elements["lbl_player"] = pf

        row1 = ttk.Frame(pf); row1.pack(fill="x")
        self.var_frame = tk.IntVar(value=0)
        self.lbl_frame = ttk.Label(row1, text="0/0", width=10); self.lbl_frame.pack(side="left")
        self.frame_scale = ttk.Scale(row1, from_=0, to=1, command=self.on_frame_slide)
        self.frame_scale.pack(side="left", fill="x", expand=True, padx=5)

        row2 = ttk.Frame(pf); row2.pack(fill="x", pady=5)
        self.btn_play = ttk.Button(row2, text="▶", width=5, command=self.toggle_play); self.btn_play.pack(side="left")
        lbl_spd = ttk.Label(row2); lbl_spd.pack(side="left", padx=(10,5))
        self.ui_elements["lbl_speed"] = lbl_spd
        
        self.fps_var = tk.StringVar(value="10 FPS")
        ttk.OptionMenu(row2, self.fps_var, "10 FPS", "1 FPS", "5 FPS", "10 FPS", "20 FPS", "Max Speed", command=self.change_fps).pack(side="left")
        
        tb_frame = ttk.Frame(row2); tb_frame.pack(side="right")
        self.toolbar = NavigationToolbar2Tk(self.canvas, tb_frame)
        self.toolbar.update()

    # --- Data Logic ---
    def recalc_background(self):
        if self.data1 is None: return
        try:
            # 这里的计算逻辑已经移到了 processing.py，我们只调用它
            # 但是由于需要缓存 bg1/bg2 给后面的函数用，所以这里调用后保存结果
            p = self.var_bg.get()
            self.cached_bg1 = calculate_background(self.data1, p)
            self.cached_bg2 = calculate_background(self.data2, p)
        except: pass

    def load_data(self):
        try:
            self.root.config(cursor="watch"); self.root.update()
            d1 = tiff.imread(self.c1_path).astype(np.float32)
            d2 = tiff.imread(self.c2_path).astype(np.float32)
            if d1.shape != d2.shape: raise ValueError("Dimensions mismatch!")
            self.data1, self.data2 = d1, d2
            self.recalc_background()
            
            max_f = self.data1.shape[0]-1
            self.frame_scale.configure(to=max_f)
            self.var_frame.set(0); self.frame_scale.set(0)
            
            self.fig.clear()
            self.ax = self.fig.add_subplot(111); self.ax.axis('off')
            self.im_object = self.ax.imshow(np.zeros((d1.shape[1], d1.shape[2])), cmap="jet")
            self.cbar = self.fig.colorbar(self.im_object, ax=self.ax, shrink=0.8, pad=0.02)
            
            self.update_plot()
        except Exception as e: messagebox.showerror("Error", str(e))
        finally: self.root.config(cursor="")

    # 注意：get_processed_frame 现在调用 processing.py 里的纯函数
    def get_processed_frame(self, frame_idx):
        if self.data1 is None: return None
        
        return process_frame_ratio(
            self.data1[frame_idx],
            self.data2[frame_idx],
            self.cached_bg1,
            self.cached_bg2,
            self.var_int_thresh.get(),
            self.var_ratio_thresh.get(),
            int(self.var_smooth.get()),
            self.log_var.get()
        )

    def update_plot(self):
        if self.data1 is None or self.im_object is None: return
        idx = self.var_frame.get()
        img = self.get_processed_frame(idx)
        if img is None: return

        if self.lock_var.get():
            try: vmin, vmax = float(self.entry_vmin.get()), float(self.entry_vmax.get())
            except: vmin, vmax = 0, 1
            mode = "Lock"
        else:
            try: vmin, vmax = np.nanpercentile(img, [5, 95])
            except: vmin, vmax = 0, 1
            if np.isnan(vmin): vmin, vmax = 0, 1
            mode = "Auto"
            self.entry_vmin.config(state="normal"); self.entry_vmax.config(state="normal")
            self.entry_vmin.delete(0,tk.END); self.entry_vmin.insert(0,f"{vmin:.2f}")
            self.entry_vmax.delete(0,tk.END); self.entry_vmax.insert(0,f"{vmax:.2f}")
            self.entry_vmin.config(state="disabled"); self.entry_vmax.config(state="disabled")

        self.im_object.set_data(img)
        self.im_object.set_clim(vmin, vmax)
        self.ax.set_title(f"Frame {idx} | {mode}")
        
        def format_coord(x, y):
            col = int(x + 0.5)
            row = int(y + 0.5)
            rows, cols = img.shape
            if 0 <= col < cols and 0 <= row < rows:
                z = img[row, col]
                return f"[{col}, {row}] Ratio: {z:.4f}"
            return ""
        
        self.ax.format_coord = format_coord
        self.canvas.draw_idle()

    # ... (Rest of GUI methods like update_cmap, activate_roi_drawer ... same as V1.7)
    # 为了节省篇幅，请复制 V1.7 版本中 update_cmap 及其之后的所有方法到这里
    # 注意：在 calc_and_show_curve 中，也要用 process_frame_ratio 或者类似的矢量化方法
    # 其实 V1.7 的 plot_roi_curve 用的是 bulk calculation (对整个ROI slice运算)，这非常高效，保留即可。
    
    # 唯一需要确保的是：如果 plot_roi_curve 里有重复的数学逻辑（比如扣背景），最好也提取出来。
    # 但为了方便，V1.7 的 plot_roi_curve 逻辑可以直接用。
    
    # 请把 V1.7 代码中 update_cmap 到底部的所有代码贴在这里
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
            self.roi_selector.set_active(True)
            self.roi_selector.set_visible(True)
            return
        
        self.roi_selector = RectangleSelector(
            self.ax, self.on_roi_select,
            useblit=True, button=[1], 
            minspanx=5, minspany=5,
            spancoords='pixels', interactive=True
        )
        self.canvas.draw()

    def on_roi_mouse_move(self, event):
        if not self.live_plot_var.get(): return
        if self.is_calculating_roi: return
        if self.roi_selector is None or not self.roi_selector.active: return
        
        if event.button == 1 and event.inaxes == self.ax:
            try:
                xmin, xmax, ymin, ymax = self.roi_selector.extents
                x1, x2 = int(xmin), int(xmax)
                y1, y2 = int(ymin), int(ymax)
                self.roi_coords = (x1, y1, x2, y2)
                self.is_calculating_roi = True
                self.plot_roi_curve()
            except:
                pass

    def clear_roi(self):
        if self.roi_selector:
            self.roi_selector.set_active(False)
            self.roi_selector.set_visible(False)
            self.canvas.draw() 
        self.roi_coords = None

    def on_roi_select(self, eclick, erelease):
        x1, y1 = int(eclick.xdata), int(eclick.ydata)
        x2, y2 = int(erelease.xdata), int(erelease.ydata)
        self.roi_coords = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        
        if self.live_plot_var.get():
            self.is_calculating_roi = True
            self.plot_roi_curve()

    def plot_roi_curve(self):
        if self.data1 is None or self.roi_coords is None: 
            self.is_calculating_roi = False
            return
            
        x1, y1, x2, y2 = self.roi_coords
        h, w = self.data1.shape[1], self.data1.shape[2]
        x1, x2 = max(0, x1), min(w, x2)
        y1, y2 = max(0, y1), min(h, y2)
        if x2 <= x1 or y2 <= y1: 
            self.is_calculating_roi = False
            return
        
        try: interval = float(self.var_interval.get())
        except: interval = 1.0
        
        unit = self.combo_unit.get()

        threading.Thread(target=self.calc_and_show_curve, args=(x1, y1, x2, y2, interval, unit)).start()

    def calc_and_show_curve(self, x1, y1, x2, y2, interval, unit):
        try:
            d1_roi = self.data1[:, y1:y2, x1:x2]
            d2_roi = self.data2[:, y1:y2, x1:x2]
            bg1, bg2 = self.cached_bg1, self.cached_bg2
            d1_roi = np.clip(d1_roi - bg1, 0, None)
            d2_roi = np.clip(d2_roi - bg2, 0, None)
            with np.errstate(divide='ignore', invalid='ignore'):
                ratio_roi = np.divide(d1_roi, d2_roi)
                ratio_roi[d2_roi==0] = np.nan
            if self.log_var.get(): ratio_roi = np.log1p(ratio_roi)
            
            means = np.nanmean(ratio_roi, axis=(1, 2))
            
            mult = 1.0
            if unit == "m": mult = 1.0/60.0
            elif unit == "h": mult = 1.0/3600.0
            
            times = np.arange(len(means)) * interval * mult
            
            self.root.after(0, self.update_plot_window, times, means, unit)
        finally:
            self.is_calculating_roi = False

    def update_plot_window(self, x_data, y_data, unit):
        if self.plot_window is None or not tk.Toplevel.winfo_exists(self.plot_window):
            self.plot_window = Toplevel(self.root)
            self.plot_window.title("ROI Time Course")
            self.plot_window.geometry("700x500")
            
            fig = plt.Figure(figsize=(5, 4), dpi=100)
            self.plot_ax = fig.add_subplot(111)
            self.plot_canvas = FigureCanvasTkAgg(fig, master=self.plot_window)
            self.plot_canvas.get_tk_widget().pack(fill="both", expand=True)
            
            btn_frame = ttk.Frame(self.plot_window)
            btn_frame.pack(side="bottom", pady=5)
            
            btn_copy_all = ttk.Button(btn_frame, text=self.t("btn_copy_all"), 
                                  command=lambda: self.copy_plot_data(x_data, y_data, mode="all"))
            btn_copy_all.pack(side="left", padx=5)
            
            btn_copy_y = ttk.Button(btn_frame, text=self.t("btn_copy_y"), 
                                  command=lambda: self.copy_plot_data(x_data, y_data, mode="y_only"))
            btn_copy_y.pack(side="left", padx=5)
        
        self.plot_ax.clear()
        self.plot_ax.plot(x_data, y_data, 'r-', linewidth=1.5)
        self.plot_ax.set_xlabel(f"Time ({unit})")
        self.plot_ax.set_ylabel("Mean Ratio (Log)" if self.log_var.get() else "Mean Ratio")
        self.plot_ax.grid(True)
        self.plot_canvas.draw()

    def copy_plot_data(self, x_data, y_data, mode="all"):
        try:
            data_str = ""
            if mode == "all":
                data_str = "Time\tRatio\n"
                for x, y in zip(x_data, y_data):
                    data_str += f"{x:.3f}\t{y:.5f}\n"
            else:
                data_str = "Ratio\n"
                for y in y_data:
                    data_str += f"{y:.5f}\n"
            
            self.root.clipboard_clear()
            self.root.clipboard_append(data_str)
            messagebox.showinfo("Success", "Data copied!")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_stack_thread(self):
        if self.data1 is None: return
        threading.Thread(target=self.save_stack_task).start()

    def save_stack_task(self):
        try:
            self.btn_save_stack.config(state="disabled", text="⏳ Saving...")
            ts = datetime.datetime.now().strftime("%H%M%S")
            path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=f"Ratio_Stack_{ts}.tif")
            if not path: self.restore_save_btn(); return

            total_frames = self.data1.shape[0]
            stack_data = []
            for i in range(total_frames):
                if i % 5 == 0: self.btn_save_stack.config(text=f"⏳ {i}/{total_frames}")
                processed = self.get_processed_frame(i)
                stack_data.append(processed.astype(np.float32))
            
            tiff.imwrite(path, np.array(stack_data))
            messagebox.showinfo("Success", f"Saved to:\n{path}")
        except Exception as e: messagebox.showerror("Error", str(e))
        finally: self.restore_save_btn()

    def restore_save_btn(self):
        self.btn_save_stack.config(state="normal", text=self.t("btn_save_stack"))

    def toggle_scale_mode(self):
        if self.lock_var.get():
            self.entry_vmin.config(state="normal"); self.entry_vmax.config(state="normal")
        else:
            self.entry_vmin.config(state="disabled"); self.entry_vmax.config(state="disabled")
        self.update_plot()
        
    def select_c1(self):
        p = filedialog.askopenfilename(filetypes=[("TIFF","*.tif")])
        if p: self.c1_path = p; self.lbl_c1_path.config(text=os.path.basename(p), foreground="black"); self.check_ready()
    def select_c2(self):
        p = filedialog.askopenfilename(filetypes=[("TIFF","*.tif")])
        if p: self.c2_path = p; self.lbl_c2_path.config(text=os.path.basename(p), foreground="black"); self.check_ready()
    def check_ready(self):
        if self.c1_path and self.c2_path: self.btn_load.config(state="normal")
    
    def save_current_frame(self):
        if self.data1 is None: return
        img = self.get_processed_frame(self.var_frame.get())
        path = filedialog.asksaveasfilename(defaultextension=".tif", initialfile=f"Ratio_F{self.var_frame.get()}.tif")
        if path: tiff.imwrite(path, img)

    def on_frame_slide(self, v):
        idx = int(float(v)); self.var_frame.set(idx)
        self.lbl_frame.config(text=f"{idx}/{self.data1.shape[0]-1}")
        if not self.is_playing: self.update_plot()
    
    def toggle_play(self):
        if self.is_playing: self.stop_play()
        else: self.start_play()
    def start_play(self):
        if self.data1 is None: return
        self.is_playing = True; self.btn_play.config(text="⏸"); self.play_next_frame()
    def stop_play(self):
        self.is_playing = False; self.btn_play.config(text="▶")
    def play_next_frame(self):
        if not self.is_playing: return
        curr = self.var_frame.get(); max_f = self.data1.shape[0]-1
        nxt = 0 if curr >= max_f else curr + 1
        self.var_frame.set(nxt); self.frame_scale.set(nxt)
        self.lbl_frame.config(text=f"{nxt}/{max_f}"); self.update_plot()
        delay = 1 if self.fps >= 100 else int(1000/self.fps)
        self.root.after(delay, self.play_next_frame)
    def change_fps(self, v):
        self.fps = 100 if "Max" in v else int(v.split()[0])