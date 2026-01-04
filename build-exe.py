import os
import shutil
import subprocess
import sys
import time
import re
import datetime
import collections

# ==========================================
# 🛠️ 0. 依赖自动检查
# ==========================================
def install_deps():
    required = ["rich", "requests", "packaging"]
    installed = []
    try:
        import pkg_resources
        installed = {pkg.key for pkg in pkg_resources.working_set}
    except: pass
    
    missing = [pkg for pkg in required if pkg not in installed]
    if missing:
        print(f"正在安装构建工具依赖: {', '.join(missing)}...")
        subprocess.run([sys.executable, "-m", "pip", "install", *missing], check=True)

install_deps()

import requests
from packaging import version
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.prompt import Confirm
from rich.theme import Theme
from rich.live import Live
from rich.text import Text

# ==========================================
# ⚙️ 1. 项目配置 (完全还原原始逻辑)
# ==========================================
APP_NAME = "RIA"
REPO_OWNER = "Epivitae"
REPO_NAME = "RatioImagingAnalyzer"

# 路径定义
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(BASE_DIR, "src", "ria_gui", "_version.py")
ENTRY_POINT = os.path.join(BASE_DIR, "src", "ria_gui", "main.py") 
SOURCE_DIR = os.path.join(BASE_DIR, "src", "ria_gui") 
ICON_PATH = os.path.join(BASE_DIR, "src", "ria_gui", "assets", "app_256x256.ico")
ASSETS_SRC = os.path.join(BASE_DIR, "src", "ria_gui", "assets")
ASSETS_DST = "assets"
UPX_DIR = r"D:\0_App\upx" 
HOOK_FILE = "rthook_path_fix.py"

# [重要修正] 还原为原始的排除列表，不再强制排除 matplotlib 后端，防止运行时崩溃
EXCLUDES = [
    "matplotlib.tests", "tkinter.test"
]

console = Console(theme=Theme({"info": "cyan", "warning": "yellow", "error": "bold red", "success": "bold green"}))

# ==========================================
# 🧬 2. 版本逻辑
# ==========================================
def get_local_version():
    default = "0.0.0"
    if not os.path.exists(VERSION_FILE): return default
    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match: return match.group(1).strip()
    except: pass
    return default

def get_remote_version():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    try:
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            return resp.json().get("tag_name", "v0.0.0")
    except: pass
    return "v0.0.0"

def calculate_build_strategy():
    v_local_str = get_local_version()
    v_remote_str = get_remote_version()

    clean_local = re.sub(r"[^0-9\.]", "", v_local_str)
    clean_remote = re.sub(r"[^0-9\.]", "", v_remote_str)

    try:
        v_loc = version.parse(clean_local)
        v_rem = version.parse(clean_remote)
    except:
        v_loc = version.parse("0.0.0")
        v_rem = version.parse("0.0.0")

    if v_loc > v_rem:
        build_type = "STABLE"
        reason = "🚀 全新版本发布 (Local > Remote)"
        exe_name = f"{APP_NAME}_{v_local_str}_Stable"
    else:
        build_type = "PATCH"
        reason = "🔧 补丁/测试构建 (Local <= Remote)"
        timestamp = datetime.datetime.now().strftime("%Y%m%d")
        exe_name = f"{APP_NAME}_{v_local_str}_Patch_{timestamp}"

    return {
        "local": v_local_str,
        "remote": v_remote_str,
        "type": build_type,
        "reason": reason,
        "exe_name": exe_name
    }

# ==========================================
# 🏗️ 3. 构建流程
# ==========================================
def create_runtime_hook():
    content = """
import sys
import os
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
"""
    with open(HOOK_FILE, "w", encoding="utf-8") as f: f.write(content.strip())

def clean_env():
    trash = ["build", "dist", "__pycache__"]
    for d in trash: shutil.rmtree(d, ignore_errors=True)
    # 仅删除 spec 和 hook，避免误删其他文件
    for f in os.listdir("."):
        if f.endswith(".spec") or f == HOOK_FILE:
            try: os.remove(f)
            except: pass

def build():
    console.clear()
    console.print(Panel.fit(f"[bold white]🚀 {APP_NAME} 打包助手[/]", border_style="blue"))

    with console.status("[bold cyan]正在同步版本信息...[/]"):
        info = calculate_build_strategy()

    grid = f"""
    [bold]版本对照:[/bold]
      🏠 本地版本: [cyan]{info['local']}[/]  (源代码)
      ☁️ 线上版本: [magenta]{info['remote']}[/] (GitHub)
    
    [bold]构建策略:[/bold]
      ⚖️ 判定结果: [yellow]{info['reason']}[/]
      📦 输出文件: [bold green]{info['exe_name']}.exe[/]
    """
    console.print(Panel(grid, title="构建预览", expand=False))

    if not Confirm.ask("\n[bold white]是否确认使用上述配置开始打包?[/]"):
        console.print("[red]已取消构建。[/]")
        sys.exit(0)

    # 1. 准备 Hook (即使 clean 会删，也要先定义好)
    create_runtime_hook()

    # 2. 构造命令 (严格还原原始逻辑)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole", "--onefile", "--windowed",
        f"--name={info['exe_name']}",
        f"--icon={ICON_PATH}",
        f"--add-data={ASSETS_SRC}{os.pathsep}{ASSETS_DST}",
        f"--paths={SOURCE_DIR}",
        f"--runtime-hook={HOOK_FILE}",
        "-y"
    ]
    
    if UPX_DIR and os.path.exists(UPX_DIR):
        cmd.extend(["--upx-dir", UPX_DIR])
    
    # 仅使用基础排除项
    for mod in EXCLUDES: cmd.extend(["--exclude-module", mod])
    cmd.append(ENTRY_POINT)

    # UI 配置
    progress = Progress(
        SpinnerColumn("dots", style="bold magenta"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
    )
    
    # 日志缓冲区
    log_lines = collections.deque(maxlen=15)
    log_panel = Panel("", title="⏳ 初始化...", border_style="dim", height=17)
    layout = Group(progress, log_panel)

    with Live(layout, console=console, refresh_per_second=10) as live:
        # 步骤 1: 清理环境
        t1 = progress.add_task("[cyan]清理环境...", total=1)
        clean_env()
        # [关键] 清理后必须再次创建 Hook，确保它存在于 PyInstaller 运行时
        create_runtime_hook() 
        progress.update(t1, completed=1)

        # 步骤 2: 编译
        t2 = progress.add_task("[bold blue]正在编译 (PyInstaller)...", total=None)
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', bufsize=1, env=env)
        
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None: break
            
            if line:
                clean_line = line.strip()
                if clean_line:
                    log_lines.append(clean_line)
                    log_text = Text("\n".join(log_lines), style="dim white")
                    live.update(Group(progress, Panel(log_text, title="📜 实时日志", border_style="blue", height=17)))

        if proc.poll() != 0:
            progress.stop()
            live.stop()
            console.print("\n[bold red]❌ 编译失败！错误日志：[/]")
            console.print(Panel("\n".join(list(log_lines)), title="Fatal Error", border_style="red"))
            sys.exit(1)
        
        progress.update(t2, completed=1, description="[bold green]编译完成！")

        # 步骤 3: 移动产物
        t3 = progress.add_task("[green]整理产物...", total=1)
        dist_path = os.path.join("dist", f"{info['exe_name']}.exe")
        if os.path.exists(dist_path):
            shutil.move(dist_path, f"{info['exe_name']}.exe")
        clean_env()
        progress.update(t3, completed=1)

    # [修复 SyntaxError] 提前计算路径
    final_path = os.path.abspath(f"{info['exe_name']}.exe")
    console.print(f"\n[bold green]🎉 打包成功![/] 文件已生成: [white]{final_path}[/]")

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    build()