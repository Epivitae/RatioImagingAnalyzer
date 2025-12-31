# src/plot_window.py
import tkinter as tk
from tkinter import ttk, Toplevel
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np

# --- Define Color Palettes ---
COLOR_PALETTES = {
    "Standard": ['#FF3333', '#33FF33', '#3388FF', '#FFFF33', '#FF33FF', '#33FFFF', '#FF8833'], # 经典亮色
    "Deep":     ['#D62728', '#2CA02C', '#1F77B4', '#FF7F0E', '#9467BD', '#8C564B', '#E377C2'], # 深沉 (Matplotlib默认)
    "Paper":    ['#000000', '#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00'], # 论文专用 (色盲友好)
    "Magenta":  ['#8B008B', '#FF00FF', '#BA55D3', '#9370DB', '#4B0082', '#C71585', '#DB7093'], # [New] 洋红/紫色系
    "Ocean":    ['#000080', '#0000CD', '#4169E1', '#1E90FF', '#00BFFF', '#20B2AA', '#5F9EA0'], # [New] 海洋蓝系
    "Sunset":   ['#FF4500', '#FF8C00', '#FFD700', '#C71585', '#6A5ACD', '#DC143C'],           # [New] 落日暖色
    "Gray":     ['#000000', '#555555', '#888888', '#BBBBBB']                                   # 灰度
}
PALETTE_NAMES = list(COLOR_PALETTES.keys())

class ROIPlotWindow:
    def __init__(self, parent_root):
        """
        初始化绘图窗口管理器。
        parent_root: 主程序的 root 窗口
        """
        self.parent_root = parent_root
        self.window = None  # Toplevel 实例
        
        # --- 绘图状态数据 ---
        self.data_cache = None 
        
        # --- 绘图参数 ---
        self.plot_mode = "ratio" # ratio, num, den, combo
        self.font_size = 10
        self.cached_ylim = None 
        self.current_palette_idx = 0 
        
        # 使用 BooleanVar 绑定 UI 状态
        self.var_grid = None 
        self.var_lock_y = None
        self.var_legend = None 
        
        # --- 内部组件 ---
        self.fig = None
        self.ax = None
        self.ax_right = None
        self.canvas = None
        
    def is_open(self):
        return self.window is not None and tk.Toplevel.winfo_exists(self.window)

    def focus(self):
        if self.is_open():
            self.window.lift()

    def update_data(self, x, series_list, unit, is_log, do_norm, ratio_mode_label=("Ch1", "Ch2")):
        self.data_cache = {
            "x": x,
            "series": series_list,
            "unit": unit,
            "is_log": is_log,
            "do_norm": do_norm,
            "labels": ratio_mode_label
        }
        
        if not self.is_open():
            self._create_ui()
        
        self._refresh_plot()

    def _create_ui(self):
        self.window = Toplevel(self.parent_root)
        self.window.title("ROI Analysis")
        # [修改 1] 设置为更紧凑的 580x630
        self.window.geometry("580x630") 
        
        # 初始化变量
        if self.var_grid is None: self.var_grid = tk.BooleanVar(value=True)
        if self.var_lock_y is None: self.var_lock_y = tk.BooleanVar(value=False)
        if self.var_legend is None: self.var_legend = tk.BooleanVar(value=True)

        # 1. 顶部：绘图区
        plot_frame = ttk.Frame(self.window)
        plot_frame.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        
        self.fig = plt.Figure(figsize=(5, 4), dpi=100) # 稍微调小默认尺寸以适应新窗口
        self.fig.patch.set_facecolor('#FFFFFF')
        self.ax = self.fig.add_subplot(111)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()
        
        # 2. 底部：控制面板区 (Main Container)
        ctrl_frame = ttk.Frame(self.window, padding=5)
        ctrl_frame.pack(side="bottom", fill="x")
        
        # === ROW 1: View Channels & Color ===
        row1 = ttk.Frame(ctrl_frame)
        row1.pack(side="top", fill="x", pady=(0, 3))
        
        fr_view = ttk.LabelFrame(row1, text="View Channels", padding=5)
        fr_view.pack(side="left", fill="x", expand=True) 
        
        fr_view_inner = ttk.Frame(fr_view)
        fr_view_inner.pack(anchor="center")

        self.btn_ratio = ttk.Button(fr_view_inner, text="Ratio", width=6, command=lambda: self._set_mode("ratio"))
        self.btn_ratio.pack(side="left", padx=3)
        
        self.btn_num = ttk.Button(fr_view_inner, text="Ch1", width=8, command=lambda: self._set_mode("num"))
        self.btn_num.pack(side="left", padx=3)
        
        self.btn_den = ttk.Button(fr_view_inner, text="Ch2", width=8, command=lambda: self._set_mode("den"))
        self.btn_den.pack(side="left", padx=3)
        
        self.btn_combo = ttk.Button(fr_view_inner, text="Combo", width=7, command=lambda: self._set_mode("combo"))
        self.btn_combo.pack(side="left", padx=3)

        # Color Palette Button
        ttk.Separator(fr_view_inner, orient="vertical").pack(side="left", fill="y", padx=5)
        self.btn_color = ttk.Button(fr_view_inner, text="🎨 Color", width=7, style="Compact.TButton", command=self._cycle_palette)
        self.btn_color.pack(side="left", padx=2)

        # === ROW 2: Settings & Export ===
        row2 = ttk.Frame(ctrl_frame)
        row2.pack(side="top", fill="x", pady=(3, 0))
        
        # --- 分区 B: 绘图参数 (左侧) ---
        fr_param = ttk.LabelFrame(row2, text="Plot Settings", padding=5)
        fr_param.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        fr_param_inner = ttk.Frame(fr_param)
        fr_param_inner.pack(anchor="center")

        # 字体 A- A+
        ttk.Button(fr_param_inner, text="A-", width=3, style="Compact.TButton", command=lambda: self._change_font(-1)).pack(side="left", padx=1)
        ttk.Button(fr_param_inner, text="A+", width=3, style="Compact.TButton", command=lambda: self._change_font(1)).pack(side="left", padx=1)
        
        ttk.Separator(fr_param_inner, orient="vertical").pack(side="left", fill="y", padx=5)
        
        # 开关按钮
        self.btn_grid = ttk.Checkbutton(
            fr_param_inner, text="Grid", variable=self.var_grid, 
            style="Toggle.TButton", width=5, command=self._refresh_plot
        )
        self.btn_grid.pack(side="left", padx=2)
        
        self.btn_legend = ttk.Checkbutton(
            fr_param_inner, text="Leg.", variable=self.var_legend, # 缩写 Legend 为 Leg. 以适应窄窗口
            style="Toggle.TButton", width=5, command=self._refresh_plot
        )
        self.btn_legend.pack(side="left", padx=2)
        
        self.btn_lock_y = ttk.Checkbutton(
            fr_param_inner, text="Lock Y", variable=self.var_lock_y, 
            style="Toggle.TButton", width=6, command=self._toggle_lock_y
        )
        self.btn_lock_y.pack(side="left", padx=2)

        # --- 分区 C: 数据导出 (右侧) ---
        fr_data = ttk.LabelFrame(row2, text="Export Data", padding=5)
        fr_data.pack(side="right", fill="both", expand=True)
        
        fr_data_inner = ttk.Frame(fr_data)
        fr_data_inner.pack(anchor="center")
        
        self.btn_copy_all = ttk.Button(fr_data_inner, text="📄 All", width=6, command=lambda: self._copy_data("all"))
        self.btn_copy_all.pack(side="left", padx=3)
        
        self.btn_copy_y = ttk.Button(fr_data_inner, text="📉 Y", width=6, command=lambda: self._copy_data("y_only"))
        self.btn_copy_y.pack(side="left", padx=3)

    def _set_mode(self, mode):
        self.plot_mode = mode
        self._refresh_plot()

    def _change_font(self, delta):
        self.font_size = max(6, min(24, self.font_size + delta))
        self._refresh_plot()

    def _cycle_palette(self):
        self.current_palette_idx = (self.current_palette_idx + 1) % len(PALETTE_NAMES)
        self._refresh_plot()

    def _toggle_lock_y(self):
        if self.var_lock_y.get():
            self.cached_ylim = self.ax.get_ylim()
        else:
            self.cached_ylim = None
            self._refresh_plot()

    def _refresh_plot(self):
        if not self.data_cache: return
        
        d = self.data_cache
        x = d['x']; series_list = d['series']; unit = d['unit']
        is_log = d['is_log']; do_norm = d['do_norm']; labels = d['labels']
        label_num, label_den = labels[0], labels[1]

        # 1. 更新按钮文字
        self.btn_num.config(text=f"{label_num}") # 缩短文字
        self.btn_den.config(text=f"{label_den}")
        
        # 2. 高亮当前模式按钮
        for btn, mode in [(self.btn_ratio, "ratio"), (self.btn_num, "num"), (self.btn_den, "den"), (self.btn_combo, "combo")]:
            if mode == self.plot_mode:
                btn.state(['pressed']) 
            else:
                btn.state(['!pressed'])

        # 3. 清理绘图
        self.ax.clear()
        if self.ax_right:
            self.ax_right.remove()
            self.ax_right = None

        # 4. 设置字体
        import matplotlib
        matplotlib.rcParams.update({'font.size': self.font_size})

        # 5. Get Color Palette
        palette_name = PALETTE_NAMES[self.current_palette_idx]
        colors = COLOR_PALETTES[palette_name]

        # 6. 绘图逻辑
        if self.plot_mode == "combo":
            use_dual = not do_norm
            target_ax_sec = self.ax.twinx() if use_dual else self.ax
            self.ax_right = target_ax_sec if use_dual else None
            
            self.ax.set_axisbelow(True) # Grid at bottom
            
            lines = []
            for i, s in enumerate(series_list):
                c = colors[i % len(colors)]
                
                l1, = self.ax.plot(x, s['means'], color=c, linestyle='-', linewidth=2, label=f"ROI {s['id']} Ratio")
                lines.append(l1)
                
                l2, = target_ax_sec.plot(x, s['means_num'], color=c, linestyle='--', linewidth=1, alpha=0.7, label=f"ROI {s['id']} {label_num}")
                lines.append(l2)
                
                l3, = target_ax_sec.plot(x, s['means_den'], color=c, linestyle=':', linewidth=1, alpha=0.7, label=f"ROI {s['id']} {label_den}")
                lines.append(l3)
                
                if 'means_aux' in s:
                    for k, aux in enumerate(s['means_aux']):
                        la, = target_ax_sec.plot(x, aux, color='gray', linestyle='-.', linewidth=1, alpha=0.5, label=f"ROI {s['id']} Aux{k+1}")
                        lines.append(la)
            
            self.ax.set_ylabel(r"$\Delta R / R_0$" if do_norm else "Ratio")
            if use_dual: target_ax_sec.set_ylabel("Intensity")
            
            if self.var_legend.get():
                labs = [l.get_label() for l in lines]
                self.ax.legend(lines, labs, loc='best', fontsize='small')

        else:
            # Single Modes
            key_map = {"ratio": "means", "num": "means_num", "den": "means_den"}
            data_key = key_map.get(self.plot_mode, "means")
            
            for i, s in enumerate(series_list):
                c = colors[i % len(colors)]
                self.ax.plot(x, s[data_key], color=c, label=f"ROI {s['id']}", linewidth=1.5)
            
            if self.plot_mode == "ratio" and is_log:
                self.ax.set_yscale('log')
            else:
                self.ax.set_yscale('linear')
                
            if self.plot_mode == "ratio":
                ylabel = r"$\Delta R / R_0$" if do_norm else f"Ratio ({label_num}/{label_den})"
            elif self.plot_mode == "num":
                ylabel = r"$\Delta F / F_0$" if do_norm else f"Intensity ({label_num})"
            elif self.plot_mode == "den":
                ylabel = r"$\Delta F / F_0$" if do_norm else f"Intensity ({label_den})"
            self.ax.set_ylabel(ylabel)
            
            if self.var_legend.get():
                self.ax.legend(loc='best', fontsize='small')

        # 7. 通用设置
        self.ax.set_xlabel(f"Time ({unit})")
        
        if self.var_grid.get():
            self.ax.grid(True, which="both", alpha=0.3)
        else:
            self.ax.grid(False)
        
        if self.var_lock_y.get() and self.cached_ylim:
            self.ax.set_ylim(self.cached_ylim)
        
        self.fig.tight_layout()
        self.canvas.draw()

    def _copy_data(self, mode):
        if not self.data_cache: return
        d = self.data_cache
        x = d['x']; series = d['series']
        
        content = ""
        header = "Time"
        
        if self.plot_mode == "combo":
            for s in series:
                header += f"\tR_{s['id']}\tN_{s['id']}\tD_{s['id']}"
                if 'means_aux' in s:
                    for k in range(len(s['means_aux'])): header += f"\tA{k+1}_{s['id']}"
        else:
            header += "".join([f"\tROI_{s['id']}" for s in series])

        content += header + "\n"
        
        for i in range(len(x)):
            row = f"{x[i]:.3f}"
            for s in series:
                if self.plot_mode == "combo":
                    row += f"\t{s['means'][i]:.5f}\t{s['means_num'][i]:.5f}\t{s['means_den'][i]:.5f}"
                    if 'means_aux' in s:
                        for aux in s['means_aux']: row += f"\t{aux[i]:.5f}"
                else:
                    key = {"ratio": "means", "num": "means_num", "den": "means_den"}.get(self.plot_mode, "means")
                    row += f"\t{s[key][i]:.5f}"
            content += row + "\n"
            
        self.window.clipboard_clear()
        self.window.clipboard_append(content)
        
        btn = self.btn_copy_all if mode == "all" else self.btn_copy_y
        original_text = btn.cget("text")
        
        btn.config(text="✔", style="Success.TButton")
        self.window.after(1000, lambda: btn.config(text=original_text, style="TButton"))