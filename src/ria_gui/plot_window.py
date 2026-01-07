# src/plot_window.py
import tkinter as tk
from tkinter import ttk, Toplevel
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
from gui_components import RiaToolbar

# --- Define Color Palettes ---
COLOR_PALETTES = {
    "Standard": ['#FF3333', '#33FF33', '#3388FF', '#FFFF33', '#FF33FF', '#33FFFF', '#FF8833'], # 经典亮色
    "Deep":     ['#D62728', '#2CA02C', '#1F77B4', '#FF7F0E', '#9467BD', '#8C564B', '#E377C2'], # 深沉 (Matplotlib默认)
    "Paper":    ['#000000', '#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00'], # 论文专用 (色盲友好)
    "Magenta":  ['#8B008B', '#FF00FF', '#BA55D3', '#9370DB', '#4B0082', '#C71585', '#DB7093'], # 洋红/紫色系
    "Ocean":    ['#000080', '#0000CD', '#4169E1', '#1E90FF', '#00BFFF', '#20B2AA', '#5F9EA0'], # 海洋蓝系
    "Sunset":   ['#FF4500', '#FF8C00', '#FFD700', '#C71585', '#6A5ACD', '#DC143C'],           # 落日暖色
    "Gray":     ['#000000', '#555555', '#888888', '#BBBBBB']                                   # 灰度
}
PALETTE_NAMES = list(COLOR_PALETTES.keys())

class ROIPlotWindow:
    def __init__(self, parent_root):
        """
        初始化绘图窗口管理器。
        """
        self.parent_root = parent_root
        self.window = None  # Toplevel 实例
        
        # --- 绘图状态数据 ---
        self.data_cache = None 
        
        # --- 绘图参数 ---
        self.plot_mode = "ratio" # ratio, num, den, combo, aux_0, aux_1...
        self.font_size = 10
        self.cached_ylim = None 
        self.current_palette_idx = 0 

        self.preset_grid = True
        self.preset_lock_y = False
        self.preset_legend = True
        
        # UI 状态变量
        self.var_grid = None 
        self.var_lock_y = None
        self.var_legend = None 
        
        # --- 内部组件 ---
        self.fig = None
        self.ax = None
        self.ax_right = None
        self.canvas = None
        self.toolbar = None          # [新增] 保存工具栏引用
        self.fr_view_inner = None
        self.mode_buttons = {} 

        # [新增] 默认主题颜色 (浅色)
        self.current_theme_colors = {
            "bg": "#F0F2F5", 
            "plot_bg": "#FFFFFF", 
            "plot_fg": "#000000",
            "toolbar_bg": "#F0F0F0"
        }


    def get_settings(self):
        """导出当前窗口的设置状态"""
        # 如果窗口没开，就只保存基础参数；如果开了，保存 UI 上的实时状态
        is_open = self.is_open()
        
        return {
            "is_open": is_open,
            "plot_mode": self.plot_mode,
            "font_size": self.font_size,
            "palette_idx": self.current_palette_idx,
            # 如果变量存在就取变量值，否则取预设值
            "grid": self.var_grid.get() if self.var_grid else self.preset_grid,
            "lock_y": self.var_lock_y.get() if self.var_lock_y else self.preset_lock_y,
            "legend": self.var_legend.get() if self.var_legend else self.preset_legend
        }

    def apply_settings(self, settings):
        """应用设置 (在打开窗口前调用)"""
        if not settings: return
        
        self.plot_mode = settings.get("plot_mode", "ratio")
        self.font_size = settings.get("font_size", 10)
        self.current_palette_idx = settings.get("palette_idx", 0)
        
        # 更新预设值，这样下次 _create_ui 时就会用这些值
        self.preset_grid = settings.get("grid", True)
        self.preset_lock_y = settings.get("lock_y", False)
        self.preset_legend = settings.get("legend", True)
        
        # 如果窗口已经开着，直接更新变量并刷新
        if self.is_open():
            if self.var_grid: self.var_grid.set(self.preset_grid)
            if self.var_lock_y: self.var_lock_y.set(self.preset_lock_y)
            if self.var_legend: self.var_legend.set(self.preset_legend)
            self._refresh_plot()


    def is_open(self):
        return self.window is not None and tk.Toplevel.winfo_exists(self.window)

    def focus(self):
        if self.is_open():
            self.window.lift()

    def apply_theme(self, colors):
        """
        [新增] 接收来自主程序的颜色字典，更新窗口和绘图样式。
        colors: dict, e.g. {"bg":..., "text":..., "plot_bg":..., "plot_fg":...}
        """
        # 1. 保存颜色配置 (以便下次 _create_ui 或 _refresh_plot 时使用)
        self.current_theme_colors = colors

        # 2. 如果窗口开着，立即刷新
        if self.is_open():
            # A. 窗口背景
            self.window.configure(bg=colors["bg"])
            
            # B. Matplotlib Figure & Axes
            if self.fig:
                bg = colors["plot_bg"]
                fg = colors["plot_fg"]
                
                self.fig.patch.set_facecolor(bg)
                
                # 刷新图表内容 (这会自动重新应用坐标轴颜色)
                self._refresh_plot()
            
            # C. Toolbar 背景 (防止黑色图标看不见)
            if self.toolbar:
                tb_bg = colors.get("toolbar_bg", "#F0F0F0")
                try:
                    self.toolbar.config(background=tb_bg)
                    self.toolbar._message_label.config(background=tb_bg, foreground="black") # 坐标信息始终黑字
                except: pass

    def update_data(self, x, series_list, unit, is_log, do_norm, channel_info):
        """
        channel_info: dict, 包含 labels, has_ratio, aux_labels 等
        """
        self.data_cache = {
            "x": x,
            "series": series_list,
            "unit": unit,
            "is_log": is_log,
            "do_norm": do_norm,
            "info": channel_info
        }
        
        if not self.is_open():
            self._create_ui()
        
        # 每次数据更新都重建按钮 (适应通道数变化)
        self._rebuild_channel_buttons()
        self._refresh_plot()

    def _create_ui(self):
        self.window = Toplevel(self.parent_root)
        self.window.title("ROI Analysis")
        self.window.geometry("620x630")

        self.mode_buttons = {}
        
        # [修改] 应用当前窗口背景色
        self.window.configure(bg=self.current_theme_colors["bg"])
        
        # 初始化变量
        if self.var_grid is None: self.var_grid = tk.BooleanVar(value=self.preset_grid)
        if self.var_lock_y is None: self.var_lock_y = tk.BooleanVar(value=self.preset_lock_y)
        if self.var_legend is None: self.var_legend = tk.BooleanVar(value=self.preset_legend)

        
        # 1. 顶部：绘图区
        plot_frame = ttk.Frame(self.window)
        plot_frame.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        
        self.fig = plt.Figure(figsize=(5, 4), dpi=100)
        
        # [修改] 应用当前绘图背景色
        self.fig.patch.set_facecolor(self.current_theme_colors["plot_bg"])
        
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(self.current_theme_colors["plot_bg"])
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # =========================================================
        # [修改] 使用自定义 RiaToolbar 替换默认工具栏
        # =========================================================
        # 定义命名规则: Curve_Analysis_[Mode].png
        def get_curve_name():
            # 动态获取当前的 plot_mode (如 ratio, num, combo...)
            return f"Curve_Analysis_{self.plot_mode}.png"

        self.toolbar = RiaToolbar(self.canvas, plot_frame, name_generator=get_curve_name)
        
        # 配置工具栏颜色 (适配深色模式)
        tb_bg = self.current_theme_colors.get("toolbar_bg", "#F0F0F0")
        self.toolbar.config(background=tb_bg)
        self.toolbar._message_label.config(background=tb_bg, foreground="black")
        self.toolbar.update()
        # =========================================================
        
        # 2. 底部：控制面板区 (Main Container)
        ctrl_frame = ttk.Frame(self.window, padding=5)
        ctrl_frame.pack(side="bottom", fill="x")
        
        # === ROW 1: View Channels & Color ===
        row1 = ttk.Frame(ctrl_frame)
        row1.pack(side="top", fill="x", pady=(0, 3))
        
        fr_view = ttk.LabelFrame(row1, text="View Channels", padding=5)
        fr_view.pack(side="left", fill="x", expand=True) 
        
        self.fr_view_inner = ttk.Frame(fr_view)
        self.fr_view_inner.pack(anchor="center", fill="x")

        # === ROW 2: Settings & Export ===
        row2 = ttk.Frame(ctrl_frame)
        row2.pack(side="top", fill="x", pady=(3, 0))
        
        # --- 分区 B: 绘图参数 (左侧) ---
        fr_param = ttk.LabelFrame(row2, text="Plot Settings", padding=5)
        fr_param.pack(side="left", fill="both", expand=True, padx=(0, 5))
        fr_param_inner = ttk.Frame(fr_param)
        fr_param_inner.pack(anchor="center")

        ttk.Button(fr_param_inner, text="A-", width=3, style="Compact.TButton", command=lambda: self._change_font(-1)).pack(side="left", padx=1)
        ttk.Button(fr_param_inner, text="A+", width=3, style="Compact.TButton", command=lambda: self._change_font(1)).pack(side="left", padx=1)
        ttk.Separator(fr_param_inner, orient="vertical").pack(side="left", fill="y", padx=5)
        
        self.btn_grid = ttk.Checkbutton(fr_param_inner, text="Grid", variable=self.var_grid, style="Toggle.TButton", width=5, command=self._refresh_plot)
        self.btn_grid.pack(side="left", padx=2)
        
        self.btn_legend = ttk.Checkbutton(fr_param_inner, text="Leg.", variable=self.var_legend, style="Toggle.TButton", width=5, command=self._refresh_plot)
        self.btn_legend.pack(side="left", padx=2)
        
        self.btn_lock_y = ttk.Checkbutton(fr_param_inner, text="Lock Y", variable=self.var_lock_y, style="Toggle.TButton", width=6, command=self._toggle_lock_y)
        self.btn_lock_y.pack(side="left", padx=2)

        # --- 分区 C: 数据导出 (右侧) ---
        fr_data = ttk.LabelFrame(row2, text="Export Data", padding=5)
        fr_data.pack(side="right", fill="both", expand=True)
        fr_data_inner = ttk.Frame(fr_data)
        fr_data_inner.pack(anchor="center")
        
        self.btn_copy_time = ttk.Button(fr_data_inner, text="📄 Table", width=14, 
                                        command=lambda: self._copy_data(with_time=True))
        self.btn_copy_time.pack(side="left", padx=3)
        
        self.btn_copy_data = ttk.Button(fr_data_inner, text="📉 Data Only", width=14, 
                                        command=lambda: self._copy_data(with_time=False))
        self.btn_copy_data.pack(side="left", padx=3)

        # 首次创建时应用颜色
        self.apply_theme(self.current_theme_colors)



    def _rebuild_channel_buttons(self):
        """根据数据动态生成通道按钮"""
        if not self.data_cache or not self.fr_view_inner: return
        
        # 1. 清除旧按钮
        for child in self.fr_view_inner.winfo_children():
            child.destroy()
        self.mode_buttons = {}

        info = self.data_cache['info']
        labels = info.get("labels", ("Ch1", "Ch2"))
        aux_labels = info.get("aux_labels", [])
        has_ratio = info.get("has_ratio", True)

        def add_btn(text, mode, width=None):
            w = width if width else len(text) + 2
            btn = ttk.Button(self.fr_view_inner, text=text, width=w, 
                           command=lambda m=mode: self._set_mode(m))
            btn.pack(side="left", padx=2)
            self.mode_buttons[mode] = btn

        # 2. Ratio (如果是双通道)
        if has_ratio:
            add_btn("Ratio", "ratio", 6)

        # 3. Ch1 / Ch2
        add_btn(labels[0], "num", 6) # Ch1
        if has_ratio and len(labels) > 1:
            add_btn(labels[1], "den", 6) # Ch2

        # 4. Aux Channels
        for i, aux_name in enumerate(aux_labels):
            add_btn(aux_name, f"aux_{i}", 6)

        # 5. 分隔符和 Combo / Color
        ttk.Separator(self.fr_view_inner, orient="vertical").pack(side="left", fill="y", padx=5)
        add_btn("Combo", "combo", 7)
        
        btn_color = ttk.Button(self.fr_view_inner, text="🎨 Color", width=8, style="Compact.TButton", command=self._cycle_palette)
        btn_color.pack(side="left", padx=2)

        # 6. 状态检查
        if self.plot_mode == "ratio" and not has_ratio:
            self.plot_mode = "num"
        
        self._update_button_states()
    
    def _update_button_states(self):
        # 遍历字典时要小心，如果中途字典变了或者组件没了
        for mode, btn in self.mode_buttons.items():
            try:
                # ✅ [修复] 增加 winfo_exists() 检查，或者直接用 try-except 捕获 TclError
                if not btn.winfo_exists():
                    continue

                if mode == self.plot_mode:
                    btn.state(['pressed']) 
                else:
                    btn.state(['!pressed'])
            except tk.TclError:
                # 忽略“invalid command name”错误
                pass
            except Exception as e:
                print(f"Button state update error: {e}")
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
        is_log = d['is_log']; do_norm = d['do_norm']
        info = d['info']
        
        self._update_button_states()

        # 1. 清空 Axes
        self.ax.clear()
        if self.ax_right:
            self.ax_right.remove()
            self.ax_right = None

        # 2. [关键] 恢复坐标轴颜色 (clear会重置样式，必须重设)
        bg = self.current_theme_colors["plot_bg"]
        fg = self.current_theme_colors["plot_fg"]

        def style_ax(ax):
            ax.set_facecolor(bg)
            ax.spines['bottom'].set_color(fg)
            ax.spines['top'].set_color(fg)
            ax.spines['left'].set_color(fg)
            ax.spines['right'].set_color(fg)
            ax.xaxis.label.set_color(fg)
            ax.yaxis.label.set_color(fg)
            ax.tick_params(axis='x', colors=fg)
            ax.tick_params(axis='y', colors=fg)
            ax.title.set_color(fg)

        style_ax(self.ax)

        # 3. 准备绘图参数
        import matplotlib
        matplotlib.rcParams.update({'font.size': self.font_size})
        palette_name = PALETTE_NAMES[self.current_palette_idx]
        colors = COLOR_PALETTES[palette_name]
        
        labels = info.get("labels", ("Ch1", "Ch2"))
        label_num, label_den = labels[0], labels[1]

        # 4. 绘图逻辑
        if self.plot_mode == "combo":
            use_dual = not do_norm
            target_ax_sec = self.ax.twinx() if use_dual else self.ax
            self.ax_right = target_ax_sec if use_dual else None
            
            # 如果是双轴，也要设置右轴的颜色
            if self.ax_right: style_ax(self.ax_right)
            
            self.ax.set_axisbelow(True)
            
            lines = []
            for i, s in enumerate(series_list):
                c = colors[i % len(colors)]
                
                label_main = "Ratio" if info.get("has_ratio") else "Intensity"
                l1, = self.ax.plot(x, s['means'], color=c, linestyle='-', linewidth=2, label=f"ROI {s['id']} {label_main}")
                lines.append(l1)
                
                l2, = target_ax_sec.plot(x, s['means_num'], color=c, linestyle='--', linewidth=1, alpha=0.7, label=f"ROI {s['id']} {label_num}")
                lines.append(l2)
                
                if info.get("has_ratio"): 
                    l3, = target_ax_sec.plot(x, s['means_den'], color=c, linestyle=':', linewidth=1, alpha=0.7, label=f"ROI {s['id']} {label_den}")
                    lines.append(l3)
                
                if 'means_aux' in s:
                    for k, aux_data in enumerate(s['means_aux']):
                        label_aux = info['aux_labels'][k] if k < len(info['aux_labels']) else f"Aux{k+1}"
                        la, = target_ax_sec.plot(x, aux_data, color=c, linestyle='-.', linewidth=1, alpha=0.5, label=f"ROI {s['id']} {label_aux}")
                        lines.append(la)
            
            self.ax.set_ylabel(r"$\Delta R / R_0$" if do_norm else "Ratio")
            if use_dual: target_ax_sec.set_ylabel("Intensity")
            
            if self.var_legend.get():
                labs = [l.get_label() for l in lines]
                leg = self.ax.legend(lines, labs, loc='best', fontsize='small')
                # 设置图例文字颜色
                for text in leg.get_texts(): text.set_color(fg)

        else:
            # Single Modes
            ylabel = "Value"
            for i, s in enumerate(series_list):
                c = colors[i % len(colors)]
                data_to_plot = None
                
                if self.plot_mode == "ratio":
                    data_to_plot = s['means']
                    ylabel = r"$\Delta R / R_0$" if do_norm else f"Ratio ({label_num}/{label_den})"
                elif self.plot_mode == "num":
                    data_to_plot = s['means_num']
                    ylabel = r"$\Delta F / F_0$" if do_norm else f"Intensity ({label_num})"
                elif self.plot_mode == "den":
                    data_to_plot = s['means_den']
                    ylabel = r"$\Delta F / F_0$" if do_norm else f"Intensity ({label_den})"
                elif self.plot_mode.startswith("aux_"):
                    try:
                        idx = int(self.plot_mode.split("_")[1])
                        if idx < len(s['means_aux']):
                            data_to_plot = s['means_aux'][idx]
                            aux_name = info['aux_labels'][idx] if idx < len(info['aux_labels']) else f"Ch{idx+3}"
                            ylabel = r"$\Delta F / F_0$" if do_norm else f"Intensity ({aux_name})"
                    except: pass
                
                if data_to_plot is not None:
                    self.ax.plot(x, data_to_plot, color=c, label=f"ROI {s['id']}", linewidth=1.5)

            if self.plot_mode == "ratio" and is_log: self.ax.set_yscale('log')
            else: self.ax.set_yscale('linear')
                
            self.ax.set_ylabel(ylabel)
            if self.var_legend.get(): 
                leg = self.ax.legend(loc='best', fontsize='small')
                for text in leg.get_texts(): text.set_color(fg)

        # 5. 通用设置
        self.ax.set_xlabel(f"Time ({unit})")
        if self.var_grid.get(): self.ax.grid(True, which="both", alpha=0.3)
        else: self.ax.grid(False)
        if self.var_lock_y.get() and self.cached_ylim: self.ax.set_ylim(self.cached_ylim)
        self.fig.tight_layout()
        self.canvas.draw()


    def _copy_data(self, with_time=True):
        """
        导出数据逻辑
        """
        if not self.data_cache: return
        d = self.data_cache
        x = d['x']; series = d['series']; info = d['info']
        unit = d['unit']
        
        data_label = "Value"
        if self.plot_mode == "ratio": data_label = "Ratio"
        elif self.plot_mode == "num": data_label = info['labels'][0]
        elif self.plot_mode == "den": data_label = info['labels'][1]
        elif self.plot_mode.startswith("aux_"):
            try:
                idx = int(self.plot_mode.split("_")[1])
                data_label = info['aux_labels'][idx]
            except: data_label = "Aux"
        elif self.plot_mode == "combo": data_label = "Combo"

        content = ""
        header_parts = []
        if with_time: header_parts.append(f"Time({unit})")
        
        if self.plot_mode == "combo":
            for s in series:
                header_parts.append(f"R_{s['id']}")
                header_parts.append(f"N_{s['id']}")
                if info.get("has_ratio"): header_parts.append(f"D_{s['id']}")
        else:
            for s in series:
                header_parts.append(f"ROI_{s['id']}_{data_label}")
        
        content += "\t".join(header_parts) + "\n"
        
        for i in range(len(x)):
            row_parts = []
            if with_time: row_parts.append(f"{x[i]:.4f}")
            
            for s in series:
                if self.plot_mode == "combo":
                    row_parts.append(f"{s['means'][i]:.5f}")     
                    row_parts.append(f"{s['means_num'][i]:.5f}") 
                    if info.get("has_ratio"): 
                        row_parts.append(f"{s['means_den'][i]:.5f}") 
                else:
                    val = 0.0
                    if self.plot_mode == "ratio": val = s['means'][i]
                    elif self.plot_mode == "num": val = s['means_num'][i]
                    elif self.plot_mode == "den": val = s['means_den'][i]
                    elif self.plot_mode.startswith("aux_"):
                        try:
                            idx = int(self.plot_mode.split("_")[1])
                            val = s['means_aux'][idx][i]
                        except: val = 0.0
                    row_parts.append(f"{val:.5f}")
            
            content += "\t".join(row_parts) + "\n"
            
        self.window.clipboard_clear()
        self.window.clipboard_append(content)
        
        target_btn = self.btn_copy_time if with_time else self.btn_copy_data
        original_text = target_btn.cget("text")
        target_btn.config(text="✔", style="Success.TButton")
        
        def restore():
            try:
                if target_btn.winfo_exists():
                    target_btn.config(text=original_text, style="TButton")
            except: pass
        self.window.after(1000, restore)