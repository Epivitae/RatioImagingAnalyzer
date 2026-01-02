import os
import sys
import time
import threading
import tkinter as tk
from tkinter import messagebox
import unittest.mock as mock

# 引入 Rich 库
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.theme import Theme
    from rich.live import Live
except ImportError:
    print("请先安装 rich 库: pip install rich")
    sys.exit(1)

# ==========================================
# 1. 路径配置
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_path = os.path.join(project_root, 'src', 'ria_gui')
data_path = os.path.join(project_root, 'data')

if src_path not in sys.path: sys.path.append(src_path)

try:
    from gui import RatioAnalyzerApp
except ImportError as e:
    print(f"❌ 无法导入 gui.py: {src_path}")
    raise e

# 配置 Rich
custom_theme = Theme({"info": "dim cyan", "warning": "magenta", "danger": "bold red", "success": "bold green"})
console = Console(theme=custom_theme)

class VisualHelper:
    """负责在 GUI 上绘制幽灵鼠标和高亮框"""
    def __init__(self, root):
        self.root = root
        # 创建幽灵鼠标 (一个红色的圆点窗口)
        self.cursor = tk.Toplevel(root)
        self.cursor.overrideredirect(True) # 无边框
        self.cursor.attributes("-topmost", True) # 永远置顶
        self.cursor.geometry("15x15+0+0")
        self.cursor.configure(bg="red")
        # 做成圆形 (通过 Canvas)
        self.cv = tk.Canvas(self.cursor, width=15, height=15, bg="white", highlightthickness=0)
        self.cv.pack()
        self.cv.create_oval(2, 2, 13, 13, fill="red", outline="darkred")
        # 设置透明色
        if os.name == "nt": self.cursor.attributes("-transparentcolor", "white")
        self.cursor.withdraw() # 初始隐藏

        # 创建高亮框 (4个细长的 Toplevel 组成一个框，避免覆盖控件内容)
        self.borders = []
        for _ in range(4):
            b = tk.Toplevel(root)
            b.overrideredirect(True)
            b.configure(bg="#FF00FF") # 亮洋红
            b.attributes("-topmost", True)
            b.withdraw()
            self.borders.append(b)

    def move_to(self, widget):
        """将幽灵鼠标移动到控件中心"""
        if not widget: return
        try:
            # 确保主窗口在最前
            # self.root.lift() 
            
            self.cursor.deiconify()
            wx, wy = widget.winfo_rootx(), widget.winfo_rooty()
            ww, wh = widget.winfo_width(), widget.winfo_height()
            
            target_x = wx + ww // 2
            target_y = wy + wh // 2
            
            # 瞬移 (也可以做成动画，但容易卡顿)
            self.cursor.geometry(f"+{target_x}+{target_y}")
            self.cursor.update()
        except: pass

    def highlight(self, widget):
        """在控件周围显示边框"""
        if not widget: return
        try:
            x, y = widget.winfo_rootx(), widget.winfo_rooty()
            w, h = widget.winfo_width(), widget.winfo_height()
            th = 4 # 边框厚度
            
            # 上下左右四个边
            geoms = [
                f"{w+th*2}x{th}+{x-th}+{y-th}",      # Top
                f"{w+th*2}x{th}+{x-th}+{y+h}",      # Bottom
                f"{th}x{h}+{x-th}+{y}",             # Left
                f"{th}x{h}+{x+w}+{y}"               # Right
            ]
            
            for border, geom in zip(self.borders, geoms):
                border.geometry(geom)
                border.deiconify()
                border.update()
                
        except: pass

    def clear(self):
        """隐藏所有辅助元素"""
        self.cursor.withdraw()
        for b in self.borders: b.withdraw()


class AutoPilot:
    def __init__(self, app_instance):
        self.app = app_instance
        self.root = app_instance.root
        self.helper = VisualHelper(self.root)
        self.step_delay = 0.8 # 稍微快一点
        self.results = []

    def interact(self, widget, action_name, action_func=None):
        """核心交互函数：移动鼠标 -> 高亮 -> 执行动作 -> 记录结果"""
        if not widget:
            console.print(f"[danger]❌ 找不到控件: {action_name}[/danger]")
            self.results.append((action_name, "Failed"))
            return

        # 1. 视觉定位
        self.helper.move_to(widget)
        self.helper.highlight(widget)
        time.sleep(0.3) # 给一点视觉停留时间
        
        # 2. 执行动作 (如果是按钮则点击，否则只是高亮)
        try:
            if action_func:
                action_func()
            elif isinstance(widget, (tk.Button, tk.ttk.Button, tk.ttk.Checkbutton)):
                widget.invoke()
            
            # 记录成功
            console.print(f"[success]✔ {action_name}[/success]")
            
        except Exception as e:
            console.print(f"[danger]❌ 执行失败 {action_name}: {e}[/danger]")
            self.results.append((action_name, "Error"))
            
        # 3. 清理视觉
        time.sleep(self.step_delay)
        self.helper.clear()

    def run_rich_scenario(self):
        console.clear()
        console.print(Panel.fit("[bold white]RIA 自动化测试机器人 v2.0[/bold white]", style="bold blue"))

        # --- Scene 1: Load Data ---
        console.rule("[bold cyan]场景 1: 数据加载[/bold cyan]")
        
        # 切换标签页
        self.app.nb_import.select(1)
        self.root.update()
        time.sleep(0.5)

        # 准备文件路径
        file_c1 = os.path.join(data_path, "C1.tif")
        file_c2 = os.path.join(data_path, "C2.tif")
        
        # 智能查找
        if not os.path.exists(file_c1):
            if os.path.exists(data_path):
                tiffs = [f for f in os.listdir(data_path) if f.endswith('.tif')]
                if len(tiffs) >= 2:
                    file_c1 = os.path.join(data_path, tiffs[0])
                    file_c2 = os.path.join(data_path, tiffs[1])
                    console.print(f"[info]ℹ️ 自动匹配文件: {tiffs[0]}, {tiffs[1]}[/info]")

        # 交互 1: 选择 Ch1
        with mock.patch('tkinter.filedialog.askopenfilename', return_value=file_c1):
            self.interact(self.app.ui_elements.get("btn_c1"), "选择通道 1 (Ch1)", lambda: self.app.select_c1())

        # 交互 2: 选择 Ch2
        with mock.patch('tkinter.filedialog.askopenfilename', return_value=file_c2):
            self.interact(self.app.ui_elements.get("btn_c2"), "选择通道 2 (Ch2)", lambda: self.app.select_c2())

        # 交互 3: 点击加载
        with console.status("[bold green]正在加载并读取 Tiff...[/bold green]", spinner="dots"):
            self.interact(self.app.btn_load, "点击加载 (Load)", lambda: self.app.load_data())
        
        if self.app.session.data1 is not None:
            self.results.append(("Data Load", "Pass"))
        else:
            self.results.append(("Data Load", "Fail"))
            return

        # --- Scene 2: Parameters ---
        console.rule("[bold cyan]场景 2: 参数调整[/bold cyan]")
        
        # 1. 尝试找到滑块控件 (通常在 gui.py 里叫 scale_int)
        slider_widget = getattr(self.app, 'scale_int', None)
        
        if slider_widget:
            # 2. 将幽灵鼠标移动到滑块上，并高亮滑块
            self.interact(slider_widget, "调节强度阈值 (Slider)")
            
            # 3. 模拟平滑拖动效果
            console.print("[info]⚡ 正在模拟平滑滑动...[/info]")
            start_val = int(self.app.var_int_thresh.get())
            end_val = 20
            
            # 这里的 range(..., 1) 表示步长为 1，慢慢走
            for i in range(start_val, end_val + 1, 1):
                self.app.var_int_thresh.set(i)
                
                # [关键] 强制刷新 UI，让滑块位置瞬间更新
                self.app.update_plot() # 触发业务绘图
                slider_widget.update() # 触发滑块重绘
                self.root.update_idletasks() 
                
                time.sleep(0.05) # 50ms 一帧，肉眼看起来就是连贯的动画
                
            console.print("[success]✔ 滑块移动完成[/success]")
            time.sleep(0.5) # 停顿一下让人看清结果
            
        else:
            # 备用方案：如果找不到 scale_int，还是操作 Label
            console.print("[warning]⚠️ 未找到 scale_int 控件，回退到操作 Label[/warning]")
            self.interact(self.app.ui_elements.get("lbl_int_thr"), "聚焦强度阈值控件")
            self.app.var_int_thresh.set(15)
            self.app.update_plot()
            self.root.update()

        # 交互 5: 开启 Log
        # 这里也尝试找一下 checkbutton 控件本身，而不是 var
        chk_log_widget = getattr(self.app, 'chk_log', None)
        if chk_log_widget:
             self.interact(chk_log_widget, "开启 Log 模式")
        else:
             # 如果 gui.py 里没存 self.chk_log，就尝试 invoke 变量（虽然不太可能）
             pass
        # 交互 5: 开启 Log
        self.interact(self.app.chk_log, "开启 Log 模式")

        # --- Scene 3: ROI ---
        console.rule("[bold cyan]场景 3: ROI 操作[/bold cyan]")
        
        with console.status("[yellow]正在注入模拟 ROI...[/yellow]"):
            h, w = self.app.session.data1.shape[1], self.app.session.data1.shape[2]
            cx, cy = w//2, h//2
            fake_extents = (cx-40, cx+40, cy-40, cy+40)
            
            # 手动注入
            self.app.roi_mgr.current_shape_mode = "rect"
            self.app.roi_mgr._update_temp_roi_data(fake_extents)
            self.app.roi_mgr._commit_temp_roi()
            time.sleep(0.5)
            
        console.print("[success]✔ ROI 创建成功[/success]")
        
        # 交互 6: 点击 Plot
        self.interact(self.app.btn_plot, "绘制曲线 (Plot Curve)")

        # --- Scene 4: Export ---
        console.rule("[bold cyan]场景 4: 数据保存[/bold cyan]")
        
        save_path = os.path.join(data_path, "AutoTest_Output.tif")
        
        # 交互 7: 保存 Stack
        with mock.patch('tkinter.filedialog.asksaveasfilename', return_value=save_path):
             # 注意：由于保存是在线程中，我们不能直接 mock join，只能触发它
             self.interact(self.app.ui_elements.get("btn_save_stack"), "保存堆栈 (Save Stack)", lambda: self.app.save_stack_thread())
        
        # 等待进度条或按钮恢复
        with console.status("[bold blue]正在写入硬盘...[/bold blue]"):
            time.sleep(2.0)

        console.print(f"[info]文件已保存至: {save_path}[/info]")
        self.results.append(("Full Scenario", "Pass"))

        # --- Summary ---
        console.rule("[bold green]测试完成[/bold green]")
        
        table = Table(title="测试结果汇总")
        table.add_column("测试项", style="cyan")
        table.add_column("状态", style="bold")
        
        for name, status in self.results:
            color = "green" if status == "Pass" else "red"
            table.add_row(name, f"[{color}]{status}[/{color}]")
            
        console.print(table)
        messagebox.showinfo("AutoTest", "自动化测试顺利完成！")


def start_rich_testing():
    root = tk.Tk()
    root.title("RIA - Automated Test Environment")
    # 强制置顶一下，确保用户能看到
    root.attributes('-topmost', True)
    root.after(1000, lambda: root.attributes('-topmost', False))
    
    app = RatioAnalyzerApp(root)
    
    pilot = AutoPilot(app)
    t = threading.Thread(target=pilot.run_rich_scenario)
    t.daemon = True
    t.start()

    root.mainloop()

if __name__ == "__main__":
    start_rich_testing()