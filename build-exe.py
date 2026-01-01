import os
import shutil
import subprocess
import sys
import time
import re
import json

# ==========================================
# 🛠️ 0. 依赖检查与安装 (Auto-install)
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
        print(f"Installing missing dependencies: {', '.join(missing)}...")
        subprocess.run([sys.executable, "-m", "pip", "install", *missing], check=True)

install_deps()

# 正常导入
import requests
from packaging import version
from rich.console import Console, Group
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.theme import Theme
from rich.prompt import Confirm

# ==========================================
# ⚙️ 1. 配置区域
# ==========================================
APP_NAME = "RIA"
REPO_OWNER = "Epivitae"        # 替换为你的 GitHub 用户名
REPO_NAME = "RatioImagingAnalyzer" # 替换为你的仓库名
VERSION_FILE = os.path.join("src", "ria_gui", "_version.py")

# 路径配置
ENTRY_POINT = os.path.join("src", "ria_gui", "main.py") 
SOURCE_DIR = os.path.join("src", "ria_gui") 
ICON_PATH = os.path.join("src", "ria_gui", "assets", "app_256x256.ico")
ASSETS_SRC = os.path.join("src", "ria_gui", "assets")
ASSETS_DST = "assets"
UPX_DIR = r"D:\0_App\upx" 
HOOK_FILE = "rthook_path_fix.py"

# PyInstaller Excludes
EXCLUDES = [
    "matplotlib.tests", "matplotlib.backends.backend_qt5", 
    "matplotlib.backends.backend_qt5agg", "matplotlib.backends.backend_gtk3", 
    "matplotlib.backends.backend_wx", "matplotlib.backends.backend_wxagg",
    "tkinter.test", "unittest"
]

console = Console(theme=Theme({"info": "cyan", "warning": "yellow", "error": "bold red", "success": "bold green"}))

# ==========================================
# 🧬 2. 智能版本控制逻辑
# ==========================================
def get_local_base_version():
    """读取本地基准版本 (from _version.py)"""
    default = "0.0.0"
    if not os.path.exists(VERSION_FILE): return default
    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match: return match.group(1).strip()
    except: pass
    return default

def get_github_latest_tag():
    """获取 GitHub 最新 Release Tag"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("tag_name", "v0.0.0")
    except: 
        console.print("[warning]⚠️ 无法连接 GitHub，将使用本地版本[/]")
    return "v0.0.0"

def calculate_next_version():
    """核心算法: 比较 Local vs Remote 并生成新版本"""
    local_raw = get_local_base_version() # e.g. "v1.7.10"
    remote_raw = get_github_latest_tag() # e.g. "v1.7.10.2"
    
    # 清洗版本号 (移除 'v', '_Stable' 等)
    clean_local = re.sub(r"[^0-9\.]", "", local_raw)
    clean_remote = re.sub(r"[^0-9\.]", "", remote_raw)
    
    # 使用 packaging.version 进行语义化比较
    v_local = version.parse(clean_local)
    v_remote = version.parse(clean_remote)
    
    # 逻辑 A: 本地基准版本更新 (比如手动改了 _version.py 到 1.7.11)
    # 那么新版本直接从 .1 开始 -> 1.7.11.1
    if v_local > v_remote:
        # 只要本地基准比云端大，说明是新的一轮发布
        new_ver = f"{clean_local}.1"
        reason = "本地基准领先 (Local > Remote)"
        
    # 逻辑 B: 本地基准与云端一致，或者是旧的
    # 那么在云端基础上 +1 -> 1.7.10.3
    else:
        # 将云端版本拆解，最后一位 +1
        parts = clean_remote.split('.')
        try:
            last_digit = int(parts[-1])
            new_last = last_digit + 1
            # 重新组合，保持前缀不变
            # 这里的 tricky 点是：如果云端是 1.7.10 (没第四位)，我们要变成 1.7.10.1
            # 如果云端是 1.7.10.2，我们要变成 1.7.10.3
            
            # 判断云端版本是否包含 Patch 号 (通常是 4 位: Major.Minor.Patch.Build)
            if len(parts) >= 4:
                new_ver = ".".join(parts[:-1] + [str(new_last)])
            else:
                # 只有 3 位，加一位
                new_ver = f"{clean_remote}.1"
        except:
            new_ver = f"{clean_local}.1" # fallback
            
        reason = "基于云端递增 (Local <= Remote)"

    return f"v{new_ver}", local_raw, remote_raw, reason

def update_version_file(new_ver):
    """将新版本号写回 _version.py"""
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 正则替换
    new_content = re.sub(
        r'(__version__\s*=\s*["\'])([^"\']*)(["\'])', 
        rf'\g<1>{new_ver}\g<3>', 
        content
    )
    
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)
    return new_ver

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

def clean_artifacts(exe_name):
    trash_dirs = ["build", "dist", "__pycache__"]
    trash_files = [f"{exe_name}.spec", HOOK_FILE]
    for d in trash_dirs: shutil.rmtree(d, ignore_errors=True)
    for f in trash_files: 
        if os.path.exists(f): os.remove(f)

def build():
    console.clear()
    console.print(Panel.fit(f"[bold white]🚀 {APP_NAME} 智能构建工具[/] [dim]Auto-Versioning Enabled[/]", border_style="blue"))

    # --- 版本计算阶段 ---
    with console.status("[bold cyan]正在同步版本信息...[/]"):
        next_ver, v_loc, v_rem, reason = calculate_next_version()
    
    console.print(f"  🔹 本地基准: [dim]{v_loc}[/]")
    console.print(f"  🔹 云端最新: [dim]{v_rem}[/]")
    console.print(f"  🔸 策略判定: [yellow]{reason}[/]")
    console.print(f"  ✅ [bold green]目标版本: {next_ver}[/]\n")
    
    # 交互确认 (防止意外修改版本)
    if not Confirm.ask("是否使用此版本进行构建并更新 _version.py?"):
        console.print("[red]构建已取消[/]")
        sys.exit(0)

    # 更新文件
    update_version_file(next_ver)
    
    # 确定 EXE 名称
    exe_name = f"{APP_NAME}_{next_ver}_Stable"
    
    # --- 开始构建 ---
    create_runtime_hook()
    
    # 构造 PyInstaller 命令 (使用 sys.executable 确保环境正确)
    cmd = [
        sys.executable, "-m", "PyInstaller", # 关键修改：防止找不到 pyinstaller
        "--noconsole", "--onefile", "--windowed",
        f"--name={exe_name}", 
        f"--icon={ICON_PATH}",
        f"--add-data={ASSETS_SRC}{os.pathsep}{ASSETS_DST}",
        f"--paths={SOURCE_DIR}",          
        f"--runtime-hook={HOOK_FILE}",
        "-y"
    ]
    if UPX_DIR and os.path.exists(UPX_DIR): 
        cmd.extend(["--upx-dir", UPX_DIR])
        console.print("[info]⚡ UPX 压缩已启用[/]")
    
    for mod in EXCLUDES: cmd.extend(["--exclude-module", mod])
    cmd.append(ENTRY_POINT)

    # UI 进度条
    progress = Progress(
        SpinnerColumn("dots", style="bold magenta"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console
    )
    
    with Live(progress, console=console, refresh_per_second=10):
        # Step 1
        t1 = progress.add_task("[cyan]清理旧文件...", total=1)
        clean_artifacts(exe_name)
        if os.path.exists(f"{exe_name}.exe"): os.remove(f"{exe_name}.exe")
        create_runtime_hook()
        progress.update(t1, completed=1)
        
        # Step 2
        t2 = progress.add_task("[bold blue]正在编译 (PyInstaller)...", total=None)
        
        # 执行命令 (强制 UTF-8 避免中文乱码)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
            text=True, encoding='utf-8', bufsize=1, env=env
        )
        
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None: break
            # 可选：在这里可以将 line 打印到 debug 日志
        
        if proc.poll() != 0:
            progress.stop()
            console.print("[bold red]❌ 编译失败，请检查代码或环境！[/]")
            sys.exit(1)
            
        progress.update(t2, completed=1, description="[bold green]编译完成！")
        
        # Step 3
        t3 = progress.add_task("[green]移动产物...", total=1)
        dist_file = os.path.join("dist", f"{exe_name}.exe")
        if os.path.exists(dist_file):
            shutil.move(dist_file, f"{exe_name}.exe")
        else:
            console.print("[error]❌ dist 目录为空[/]"); sys.exit(1)
        
        clean_artifacts(exe_name)
        progress.update(t3, completed=1)

    console.print(f"\n[bold green]🎉 构建成功![/] 文件位于: [white]{os.path.abspath(f'{exe_name}.exe')}[/]")
    console.print(f"[dim]提示: _version.py 已自动更新为 {next_ver}[/]")

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    build()