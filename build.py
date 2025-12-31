import os
import shutil
import subprocess
import sys
import time
import re
from rich.console import Console, Group
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.theme import Theme

# ==========================================
# 🛠️ 0. 辅助函数：自动获取版本号
# ==========================================
def get_version_from_py():
    """从 src/ria_gui/_version.py 提取 __version__"""
    # 路径指向 src/ria_gui/_version.py
    version_file = os.path.join("src", "ria_gui", "_version.py")
    default_version = "0.0.0"
    
    if not os.path.exists(version_file):
        return default_version

    try:
        with open(version_file, "r", encoding="utf-8") as f:
            content = f.read()
            # 正则匹配 __version__ = "..."
            match = re.search(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", content, re.MULTILINE)
            if match:
                return match.group(1)
    except Exception:
        pass
            
    return default_version

# ==========================================
# 🔧 1. 配置区域 (参数化配置)
# ==========================================

APP_NAME = "RIA"
RAW_VERSION = get_version_from_py()

# [关键修改] 清洗版本号：去掉可能存在的 v 前缀，防止 "vv1.7.10"
clean_version = RAW_VERSION.strip().lstrip("vV") 
VERSION_TAG = f"v{clean_version}_Stable"
EXE_NAME = f"{APP_NAME}_{VERSION_TAG}"

# [路径配置] 适配 src/ria_gui/ 结构
ENTRY_POINT = os.path.join("src", "ria_gui", "main.py") 
ICON_PATH = os.path.join("src", "ria_gui", "assets", "app_256x256.ico")
ASSETS_SRC = os.path.join("src", "ria_gui", "assets")
ASSETS_DST = "assets"

# UPX 压缩路径
UPX_DIR = r"D:\0_App\upx" 

# 排除的模块
EXCLUDES = [
    "matplotlib.tests",
    "matplotlib.backends.backend_qt5",
    "matplotlib.backends.backend_qt5agg",
    "matplotlib.backends.backend_gtk3",
    "matplotlib.backends.backend_wx",
    "matplotlib.backends.backend_wxagg",
    "tkinter.test",
    "unittest",
    "email",
    "http",
    "xmlrpc",
]

# ==========================================
# 🎨 2. 初始化 Rich
# ==========================================
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
})
console = Console(theme=custom_theme)

def clean_artifacts():
    """清理构建产生的临时文件"""
    trash_dirs = ["build", "dist", "__pycache__"]
    trash_files = [f"{EXE_NAME}.spec"]

    for d in trash_dirs:
        if os.path.exists(d):
            try: shutil.rmtree(d)
            except: pass 

    for f in trash_files:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

def build():
    # 1. 打印静态 Header
    console.clear()
    console.print(Panel.fit(f"[bold white]🚀 {APP_NAME} 构建工具[/] [dim]By RIA Team[/]", border_style="blue"))
    
    # 2. 预检查
    if not os.path.exists(ENTRY_POINT):
        console.print(f"[error]❌ 错误: 找不到入口文件: {ENTRY_POINT}[/]")
        sys.exit(1)
    if not os.path.exists(ICON_PATH):
        console.print(f"[error]❌ 错误: 找不到图标文件: {ICON_PATH}[/]")
        sys.exit(1)
    
    console.print(f"[info]📦 识别版本:[/] [dim]{RAW_VERSION}[/]")
    console.print(f"[info]🏷️  最终标签:[/] [bold green]{VERSION_TAG}[/]")
    console.print(f"[info]💾 输出文件:[/] [bold white]{EXE_NAME}.exe[/]\n")

    # 3. 准备命令
    use_upx = False
    if UPX_DIR and os.path.exists(UPX_DIR):
        use_upx = True
        console.print(f"[success]✅ 检测到 UPX 加速压缩[/]")
    else:
        console.print("[warning]⚠️ 跳过 UPX 压缩[/]")

    cmd = [
        "pyinstaller", "--noconsole", "--onefile", "--windowed",
        f"--name={EXE_NAME}", f"--icon={ICON_PATH}",
        f"--add-data={ASSETS_SRC}{os.pathsep}{ASSETS_DST}",
    ]
    if use_upx: cmd.extend(["--upx-dir", UPX_DIR])
    for mod in EXCLUDES: cmd.extend(["--exclude-module", mod])
    cmd.append(ENTRY_POINT)

    # ==================================================
    # 🖥️ UI 布局构建区域
    # ==================================================
    
    job_progress = Progress(
        SpinnerColumn("dots", style="bold magenta"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TimeElapsedColumn(),
    )

    log_text = Text("等待任务启动...", style="dim white")
    
    log_panel = Panel(
        log_text,
        title="[bold blue]构建日志[/]",
        border_style="blue",
        height=5, 
        padding=(0, 1)
    )

    display_group = Group(log_panel, job_progress)

    with Live(display_group, console=console, refresh_per_second=10):
        
        # --- 阶段 1: 清理 ---
        task_clean = job_progress.add_task("[cyan]Step 1/3: 清理环境", total=1)
        log_text.plain = "正在移除 build/dist 文件夹..."
        clean_artifacts()
        if os.path.exists(f"{EXE_NAME}.exe"): os.remove(f"{EXE_NAME}.exe")
        time.sleep(0.5)
        job_progress.update(task_clean, completed=1)

        # --- 阶段 2: 编译 ---
        task_build = job_progress.add_task("[bold blue]Step 2/3: PyInstaller 编译核心", total=None)
        
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            encoding='utf-8',
            bufsize=1
        )
        
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            
            if line:
                clean_line = line.strip()
                if clean_line:
                    # 更新 Log 面板，截断过长字符
                    display_line = (clean_line[:80] + "...") if len(clean_line) > 80 else clean_line
                    log_text.plain = f"{display_line}"
        
        if process.poll() != 0:
            job_progress.stop()
            console.print(Panel(f"[error]❌ 构建失败！[/]", title="Fatal Error", border_style="red"))
            sys.exit(1)
        
        log_text.plain = "编译成功，准备打包..."
        job_progress.update(task_build, completed=1, description="[bold green]Step 2/3: 编译完成")

        # --- 阶段 3: 搬运 ---
        task_final = job_progress.add_task("[green]Step 3/3: 最终处理", total=1)
        dist_path = os.path.join("dist", f"{EXE_NAME}.exe")
        
        if os.path.exists(dist_path):
            log_text.plain = f"移动文件: {dist_path} -> ./"
            shutil.move(dist_path, f"{EXE_NAME}.exe")
        else:
            console.print("[error]❌ dist 目录为空[/]")
            sys.exit(1)

        clean_artifacts()
        time.sleep(0.5)
        log_text.plain = "所有任务已完成。"
        job_progress.update(task_final, completed=1)

    # 4. 结束摘要
    console.print("\n")
    console.print(Panel(
        f"[bold green]🎉 构建成功！[/]\n"
        f"文件: [underline]{os.path.abspath(f'{EXE_NAME}.exe')}[/]\n"
        f"大小: [cyan]{os.path.getsize(f'{EXE_NAME}.exe') / (1024*1024):.2f} MB[/]",
        title="Summary", border_style="green"
    ))

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    try: import rich
    except ImportError: subprocess.run([sys.executable, "-m", "pip", "install", "rich"])
    build()