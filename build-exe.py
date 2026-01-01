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
# 🛠️ 0. 辅助函数
# ==========================================
def get_version_from_py():
    version_file = os.path.join("src", "ria_gui", "_version.py")
    default_version = "0.0.0"
    if not os.path.exists(version_file): return default_version
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", content, re.MULTILINE)
            if match: return match.group(1)
    except Exception: pass
    return default_version

# ==========================================
# 💉 1. 运行时钩子 (解决路径问题，不改 main.py)
# ==========================================
HOOK_FILE = "rthook_path_fix.py"

def create_runtime_hook():
    hook_content = """
import sys
import os
# 运行时钩子：确保 EXE 内部能找到 gui 模块
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
"""
    with open(HOOK_FILE, "w", encoding="utf-8") as f:
        f.write(hook_content.strip())

# ==========================================
# 🔧 2. 配置区域
# ==========================================
APP_NAME = "RIA"
RAW_VERSION = get_version_from_py()
clean_version = RAW_VERSION.strip().lstrip("vV") 
VERSION_TAG = f"v{clean_version}_Stable"
EXE_NAME = f"{APP_NAME}_{VERSION_TAG}"

# 路径配置
ENTRY_POINT = os.path.join("src", "ria_gui", "main.py") 
SOURCE_DIR = os.path.join("src", "ria_gui") # 关键：源码目录

ICON_PATH = os.path.join("src", "ria_gui", "assets", "app_256x256.ico")
ASSETS_SRC = os.path.join("src", "ria_gui", "assets")
ASSETS_DST = "assets"
UPX_DIR = r"D:\0_App\upx" 

# [关键修改] 移除了 email, http, xmlrpc，因为 requests 库需要它们
EXCLUDES = [
    "matplotlib.tests", 
    "matplotlib.backends.backend_qt5", 
    "matplotlib.backends.backend_qt5agg",
    "matplotlib.backends.backend_gtk3", 
    "matplotlib.backends.backend_wx", 
    "matplotlib.backends.backend_wxagg",
    "tkinter.test", 
    "unittest",
    # "email",   <-- 删掉这行 (requests 需要)
    # "http",    <-- 删掉这行 (requests 需要)
    # "xmlrpc",  <-- 删掉这行 (安全起见)
]

# ==========================================
# 🎨 3. 初始化 Rich
# ==========================================
custom_theme = Theme({"info": "cyan", "warning": "yellow", "error": "bold red", "success": "bold green"})
console = Console(theme=custom_theme)

def clean_artifacts():
    trash_dirs = ["build", "dist", "__pycache__"]
    trash_files = [f"{EXE_NAME}.spec", HOOK_FILE]
    for d in trash_dirs:
        if os.path.exists(d):
            try: shutil.rmtree(d)
            except: pass 
    for f in trash_files:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

def build():
    console.clear()
    console.print(Panel.fit(f"[bold white]🚀 {APP_NAME} 构建工具[/] [dim]By RIA Team[/]", border_style="blue"))
    
    if not os.path.exists(ENTRY_POINT):
        console.print(f"[error]❌ 找不到入口: {ENTRY_POINT}[/]"); sys.exit(1)
    
    console.print(f"[info]📦 版本:[/] [bold green]{VERSION_TAG}[/]")
    console.print(f"[info]💾 输出:[/] [bold white]{EXE_NAME}.exe[/]\n")

    use_upx = False
    if UPX_DIR and os.path.exists(UPX_DIR):
        use_upx = True
        console.print(f"[success]✅ 检测到 UPX 加速[/]")
    else:
        console.print("[warning]⚠️ 跳过 UPX 压缩[/]")

    # 1. 生成钩子
    create_runtime_hook()

    # 2. 构造命令
    cmd = [
        "pyinstaller", "--noconsole", "--onefile", "--windowed",
        f"--name={EXE_NAME}", f"--icon={ICON_PATH}",
        f"--add-data={ASSETS_SRC}{os.pathsep}{ASSETS_DST}",
        f"--paths={SOURCE_DIR}",          
        f"--runtime-hook={HOOK_FILE}",    
    ]
    if use_upx: cmd.extend(["--upx-dir", UPX_DIR])
    for mod in EXCLUDES: cmd.extend(["--exclude-module", mod])
    cmd.append(ENTRY_POINT)

    # UI 流程
    job_progress = Progress(
        SpinnerColumn("dots", style="bold magenta"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TimeElapsedColumn(),
    )
    log_text = Text("等待任务启动...", style="dim white")
    log_panel = Panel(log_text, title="[bold blue]构建日志[/]", border_style="blue", height=5, padding=(0, 1))
    display_group = Group(log_panel, job_progress)

    with Live(display_group, console=console, refresh_per_second=10):
        # Step 1
        task_clean = job_progress.add_task("[cyan]Step 1/3: 清理环境", total=1)
        clean_artifacts()
        if os.path.exists(f"{EXE_NAME}.exe"): os.remove(f"{EXE_NAME}.exe")
        create_runtime_hook() 
        time.sleep(0.5)
        job_progress.update(task_clean, completed=1)

        # Step 2
        task_build = job_progress.add_task("[bold blue]Step 2/3: 编译中...", total=None)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', bufsize=1)
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None: break
            if line:
                clean_line = line.strip()
                if clean_line:
                    display_line = (clean_line[:80] + "...") if len(clean_line) > 80 else clean_line
                    log_text.plain = f"{display_line}"
        if process.poll() != 0:
            job_progress.stop()
            console.print(Panel(f"[error]❌ 构建失败！[/]", title="Fatal Error", border_style="red"))
            sys.exit(1)
        job_progress.update(task_build, completed=1, description="[bold green]Step 2/3: 编译完成")

        # Step 3
        task_final = job_progress.add_task("[green]Step 3/3: 最终处理", total=1)
        dist_path = os.path.join("dist", f"{EXE_NAME}.exe")
        if os.path.exists(dist_path):
            shutil.move(dist_path, f"{EXE_NAME}.exe")
        else:
            console.print("[error]❌ dist 目录为空[/]"); sys.exit(1)
        
        clean_artifacts() 
        time.sleep(0.5)
        job_progress.update(task_final, completed=1)

    console.print(f"\n[bold green]🎉 成功: {os.path.abspath(f'{EXE_NAME}.exe')}[/]")

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    try: import rich
    except ImportError: subprocess.run([sys.executable, "-m", "pip", "install", "rich"])
    build()