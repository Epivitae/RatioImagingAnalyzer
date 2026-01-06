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
    required = ["rich", "requests", "packaging", "pyinstaller"]
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
from rich.prompt import Confirm, Prompt
from rich.theme import Theme
from rich.live import Live
from rich.text import Text
from rich.table import Table

# ==========================================
# ⚙️ 1. 项目配置
# ==========================================
APP_NAME = "RIA"
REPO_OWNER = "Epivitae"
REPO_NAME = "RatioImagingAnalyzer"

# 路径定义 - 使用脚本所在目录作为基准
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(BASE_DIR, "src", "ria_gui")
VERSION_FILE = os.path.join(SOURCE_DIR, "_version.py")
ENTRY_POINT = os.path.join(SOURCE_DIR, "main.py")
ICON_PATH = os.path.join(SOURCE_DIR, "assets", "app_256x256.ico")
ASSETS_SRC = os.path.join(SOURCE_DIR, "assets")
ASSETS_DST = "assets"
UPX_DIR = r"D:\0_App\upx"  # UPX 压缩工具路径 (可选)
HOOK_FILE = "rthook_path_fix.py"

# ==========================================
# ✂️ 排除列表 - 轻量版不包含的模块
# ==========================================
EXCLUDES = [
    # 测试模块
    "matplotlib.tests",
    "tkinter.test",
    "test",
    # 重型依赖 (OIR/ND2 支持)
    "aicsimageio",
    "bioformats_jar",
    "javabridge",
    "xsdata",
    "pydantic",
    "imagecodecs",
    # 注意: 不要排除 unittest，matplotlib 需要它
]

console = Console(theme=Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green"
}))

# ==========================================
# 🧬 2. 版本逻辑
# ==========================================
def get_local_version():
    default = "0.0.0"
    if not os.path.exists(VERSION_FILE):
        console.print(f"[warning]⚠️ 版本文件不存在: {VERSION_FILE}[/warning]")
        return default
    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match: return match.group(1).strip()
    except Exception as e:
        console.print(f"[warning]⚠️ 读取版本失败: {e}[/warning]")
    return default

def get_remote_version():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("tag_name", "v0.0.0")
        elif resp.status_code == 404:
            return "v0.0.0"  # 没有发布版本
    except requests.exceptions.Timeout:
        console.print("[dim]GitHub API 超时，跳过版本比较[/dim]")
    except Exception as e:
        console.print(f"[dim]GitHub API 查询失败: {e}[/dim]")
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
        reason = "🚀 全新版本发布"
        exe_name = f"{APP_NAME}_{v_local_str}_Lite"
    else:
        build_type = "PATCH"
        reason = "🔧 补丁/测试构建"
        timestamp = datetime.datetime.now().strftime("%Y%m%d")
        exe_name = f"{APP_NAME}_{v_local_str}_Lite_{timestamp}"

    return {
        "local": v_local_str,
        "remote": v_remote_str,
        "type": build_type,
        "reason": reason,
        "exe_name": exe_name
    }

# ==========================================
# 🔍 3. 预检查
# ==========================================
def check_prerequisites():
    """检查构建必要条件"""
    errors = []
    warnings = []

    # 检查源码目录
    if not os.path.exists(SOURCE_DIR):
        errors.append(f"源码目录不存在: {SOURCE_DIR}")

    # 检查入口文件
    if not os.path.exists(ENTRY_POINT):
        errors.append(f"入口文件不存在: {ENTRY_POINT}")

    # 检查图标文件
    if not os.path.exists(ICON_PATH):
        warnings.append(f"图标文件不存在: {ICON_PATH}")

    # 检查资源目录
    if not os.path.exists(ASSETS_SRC):
        warnings.append(f"资源目录不存在: {ASSETS_SRC}")

    # 检查 UPX (可选)
    if UPX_DIR and not os.path.exists(UPX_DIR):
        warnings.append(f"UPX 目录不存在: {UPX_DIR} (将跳过压缩)")

    return errors, warnings

# ==========================================
# 🏗️ 4. 构建流程
# ==========================================
def create_runtime_hook():
    """创建运行时钩子，确保打包后的路径正确"""
    content = """
import sys
import os
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
    # 确保 src 目录被识别
    src_path = os.path.join(base_path, 'src')
    if os.path.exists(src_path) and src_path not in sys.path:
        sys.path.insert(0, src_path)
"""
    with open(HOOK_FILE, "w", encoding="utf-8") as f:
        f.write(content.strip())

def clean_env():
    """清理构建环境"""
    trash = ["build", "dist", "__pycache__"]
    for d in trash:
        shutil.rmtree(d, ignore_errors=True)
    for f in os.listdir("."):
        if f.endswith(".spec") or f == HOOK_FILE:
            try: os.remove(f)
            except: pass

def build():
    # 切换到脚本目录
    os.chdir(BASE_DIR)

    console.clear()
    console.print(Panel.fit(f"[bold white]🚀 {APP_NAME} 轻量版打包助手[/]", border_style="blue"))

    # 预检查
    errors, warnings = check_prerequisites()
    if errors:
        for e in errors:
            console.print(f"[error]❌ {e}[/error]")
        sys.exit(1)
    for w in warnings:
        console.print(f"[warning]⚠️ {w}[/warning]")

    # 获取版本信息
    with console.status("[bold cyan]正在同步版本信息...[/]"):
        info = calculate_build_strategy()

    # 显示构建预览
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("🏠 本地版本:", f"[cyan]{info['local']}[/]")
    table.add_row("☁️ 远程版本:", f"[dim]{info['remote']}[/]")
    table.add_row("📦 输出文件:", f"[bold green]{info['exe_name']}.exe[/]")
    table.add_row("🧪 构建类型:", f"[yellow]{info['type']}[/] - {info['reason']}")
    table.add_row("✂️ 排除模块:", f"[red]{len(EXCLUDES)} 个重型依赖[/]")

    console.print(Panel(table, title="构建预览", expand=False))

    # 允许用户修改输出文件名
    custom_name = Prompt.ask(f"\n输入自定义文件名 (回车使用默认)", default=info['exe_name'])
    if custom_name != info['exe_name']:
        info['exe_name'] = custom_name

    if not Confirm.ask("\n[bold white]是否确认开始打包?[/]"):
        console.print("[red]已取消构建。[/]")
        sys.exit(0)

    # 构建命令
    create_runtime_hook()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--windowed",
        "--clean",
        f"--name={info['exe_name']}",
        f"--paths={SOURCE_DIR}",
        f"--runtime-hook={HOOK_FILE}",
        "-y"
    ]

    # 添加图标 (如果存在)
    if os.path.exists(ICON_PATH):
        cmd.append(f"--icon={ICON_PATH}")

    # 添加资源目录 (如果存在)
    if os.path.exists(ASSETS_SRC):
        cmd.append(f"--add-data={ASSETS_SRC}{os.pathsep}{ASSETS_DST}")

    # 添加 UPX 压缩 (如果存在)
    if UPX_DIR and os.path.exists(UPX_DIR):
        cmd.extend(["--upx-dir", UPX_DIR])

    # 应用排除模块
    for mod in EXCLUDES:
        cmd.extend(["--exclude-module", mod])

    cmd.append(ENTRY_POINT)

    # 进度显示
    progress = Progress(
        SpinnerColumn("dots", style="bold magenta"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
    )

    log_lines = collections.deque(maxlen=15)
    log_panel = Panel("", title="⏳ 初始化...", border_style="dim", height=17)
    layout = Group(progress, log_panel)

    with Live(layout, console=console, refresh_per_second=10) as live:
        # 清理环境
        t1 = progress.add_task("[cyan]清理环境...", total=1)
        clean_env()
        create_runtime_hook()
        progress.update(t1, completed=1)

        # 编译
        t2 = progress.add_task("[bold blue]正在编译 (轻量版)...", total=None)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            bufsize=1,
            env=env
        )

        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                clean_line = line.strip()
                if clean_line:
                    log_lines.append(clean_line)
                    log_text = Text("\n".join(log_lines), style="dim white")
                    live.update(Group(progress, Panel(log_text, title="📜 实时日志", border_style="blue", height=17)))

        if proc.poll() != 0:
            progress.stop()
            live.stop()
            console.print("\n[bold red]❌ 编译失败！[/]")
            console.print("[dim]请检查上方日志获取详细错误信息[/dim]")
            sys.exit(1)

        progress.update(t2, completed=1, description="[bold green]编译完成！")

        # 整理产物
        t3 = progress.add_task("[green]整理产物...", total=1)
        dist_path = os.path.join("dist", f"{info['exe_name']}.exe")
        final_path = os.path.join(BASE_DIR, f"{info['exe_name']}.exe")

        if os.path.exists(dist_path):
            shutil.move(dist_path, final_path)

        clean_env()
        progress.update(t3, completed=1)

    # 成功信息
    if os.path.exists(final_path):
        file_size = os.path.getsize(final_path) / (1024 * 1024)
        console.print(f"\n[bold green]🎉 打包成功![/]")
        console.print(f"📁 文件: [white]{final_path}[/]")
        console.print(f"📊 大小: [cyan]{file_size:.1f} MB[/]")
    else:
        console.print(f"\n[yellow]⚠️ 输出文件未找到: {final_path}[/]")

if __name__ == "__main__":
    build()