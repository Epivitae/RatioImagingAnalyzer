import os
import sys
import shutil
import subprocess
import re
import glob
import collections
from datetime import datetime

# ==========================================
# 🛠️ 0. 环境自检
# ==========================================
def check_and_install_deps():
    required = ["rich", "requests", "packaging", "build", "twine", "pyinstaller"]
    missing = []
    
    result = subprocess.run([sys.executable, "-m", "pip", "list", "--format=freeze"], 
                          capture_output=True, text=True)
    installed = {line.split('==')[0].lower() for line in result.stdout.splitlines()}
    
    for pkg in required:
        if pkg.lower() not in installed:
            missing.append(pkg)

    if missing:
        print(f"正在安装缺失依赖: {', '.join(missing)}...")
        subprocess.run([sys.executable, "-m", "pip", "install", *missing], check=True)
        print("✅ 依赖安装完成，正在重启脚本...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

check_and_install_deps()

import requests
from packaging import version
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.live import Live
from rich.text import Text

console = Console()

# ==========================================
# ⚙️ 1. 全局配置
# ==========================================
CONFIG = {
    "app_name": "RIA",
    "package_name": "ria-gui",
    
    "base_dir": os.path.dirname(os.path.abspath(__file__)),
    "version_file": os.path.join("src", "ria_gui", "_version.py"),
    "pyproject_file": "pyproject.toml",
    "zenodo_template": ".zenodo.template.json", # 新增模板
    "zenodo_output": ".zenodo.json",            # 新增输出
    
    "source_dir": os.path.join("src", "ria_gui"),
    "entry_point": os.path.join("src", "ria_gui", "main.py"),
    "icon_path": os.path.join("src", "ria_gui", "assets", "app_256x256.ico"),
    "assets_src": os.path.join("src", "ria_gui", "assets"),
    "upx_dir": r"D:\0_App\upx", 
    "hook_file": "rthook_path_fix.py",
    "excludes": [
        "matplotlib.tests", "tkinter.test", "test",
        "aicsimageio", "bioformats_jar", "javabridge", 
        "xsdata", "pydantic", "imagecodecs" 
    ]
}

# ==========================================
# 🧬 2. 核心版本管理 (真理源)
# ==========================================
def get_local_version():
    """读取 _version.py 中的版本号"""
    if not os.path.exists(CONFIG["version_file"]):
        return "0.0.0"
    with open(CONFIG["version_file"], "r", encoding="utf-8") as f:
        content = f.read()
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if match: return match.group(1).strip()
    return "0.0.0"

def generate_zenodo_json(new_ver):
    """根据模板生成 .zenodo.json"""
    if not os.path.exists(CONFIG["zenodo_template"]):
        console.print(f"[yellow]⚠️ 未找到 {CONFIG['zenodo_template']}，跳过 Zenodo 元数据生成[/]")
        return

    with open(CONFIG["zenodo_template"], "r", encoding="utf-8") as f:
        content = f.read()
    
    # 替换版本号
    new_content = content.replace("{{VERSION}}", new_ver)
    
    with open(CONFIG["zenodo_output"], "w", encoding="utf-8") as f:
        f.write(new_content)
    console.print(f"[green]✅ Zenodo 元数据已更新 (v{new_ver})[/]")

def update_version_files(new_ver):
    """同时更新 _version.py, pyproject.toml 和 .zenodo.json"""
    # 1. 更新 _version.py
    with open(CONFIG["version_file"], "r", encoding="utf-8") as f:
        content = f.read()
    new_content = re.sub(r'(__version__\s*=\s*["\'])([^"\']+)(["\'])', rf'\g<1>{new_ver}\g<3>', content)
    with open(CONFIG["version_file"], "w", encoding="utf-8") as f:
        f.write(new_content)
        
    # 2. 更新 pyproject.toml
    with open(CONFIG["pyproject_file"], "r", encoding="utf-8") as f:
        content = f.read()
    new_content = re.sub(r'(^version\s*=\s*["\'])([^"\']+)(["\'])', rf'\g<1>{new_ver}\g<3>', content, flags=re.MULTILINE)
    with open(CONFIG["pyproject_file"], "w", encoding="utf-8") as f:
        f.write(new_content)
    
    # 3. 更新 .zenodo.json (新增)
    generate_zenodo_json(new_ver)
    
    console.print(f"[green]✅ 所有版本文件已同步为: {new_ver}[/]")

def ensure_version_sync(action_name="构建"):
    """交互式确认版本"""
    current_ver = get_local_version()
    console.print(f"[dim]当前代码版本: {current_ver}[/dim]")
    target_ver = Prompt.ask(f"请输入本次 {action_name} 的目标版本号", default=current_ver)
    
    # 无论是否变化，都重新生成一遍 .zenodo.json 以防模板有改动
    if target_ver != current_ver:
        update_version_files(target_ver)
    else:
        generate_zenodo_json(target_ver)
    
    return target_ver

# ==========================================
# 🏗️ 3. 模块 A: 构建 Lite EXE
# ==========================================
def create_runtime_hook():
    content = """
import sys
import os
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
    src_path = os.path.join(base_path, 'src')
    if os.path.exists(src_path) and src_path not in sys.path:
        sys.path.insert(0, src_path)
"""
    with open(CONFIG["hook_file"], "w", encoding="utf-8") as f:
        f.write(content.strip())

def build_exe_workflow():
    console.rule("[bold cyan]🔨 构建 Lite 版 EXE[/]")
    
    final_ver = ensure_version_sync(action_name="打包")
    exe_name = f"{CONFIG['app_name']}_v{final_ver}_Lite"
    
    use_upx = False
    upx_path = CONFIG["upx_dir"]
    if os.path.exists(upx_path): use_upx = True
    else:
        sys_upx = shutil.which("upx")
        if sys_upx:
            upx_path = os.path.dirname(sys_upx)
            use_upx = True

    table = Table(show_header=False, box=None)
    table.add_row("目标版本:", f"[bold green]{final_ver}[/]")
    table.add_row("输出文件:", f"[yellow]{exe_name}.exe[/]")
    table.add_row("UPX 压缩:", "[green]启用[/]" if use_upx else "[dim]未启用[/]")
    console.print(Panel(table, title="构建配置"))

    if not Confirm.ask("确认开始构建?"): return

    create_runtime_hook()
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole", "--onefile", "--windowed", "--clean",
        f"--name={exe_name}",
        f"--paths={CONFIG['source_dir']}",
        f"--runtime-hook={CONFIG['hook_file']}",
        "-y"
    ]
    
    if os.path.exists(CONFIG["icon_path"]): cmd.append(f"--icon={CONFIG['icon_path']}")
    if os.path.exists(CONFIG["assets_src"]): cmd.append(f"--add-data={CONFIG['assets_src']}{os.pathsep}assets")
    if use_upx: cmd.extend(["--upx-dir", upx_path])
    for mod in CONFIG["excludes"]: cmd.extend(["--exclude-module", mod])
    cmd.append(CONFIG["entry_point"])

    log_lines = collections.deque(maxlen=10)
    def get_log_panel(): return Panel(Text("\n".join(log_lines), style="dim"), title="PyInstaller 日志", height=12)

    with Live(get_log_panel(), refresh_per_second=10) as live:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
            text=True, encoding='utf-8', cwd=CONFIG["base_dir"]
        )
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None: break
            if line:
                log_lines.append(line.strip())
                live.update(get_log_panel())
                
    if process.returncode == 0:
        src = os.path.join("dist", f"{exe_name}.exe")
        dst = os.path.join(CONFIG["base_dir"], f"{exe_name}.exe")
        if os.path.exists(src):
            shutil.move(src, dst)
            size_mb = os.path.getsize(dst) / (1024 * 1024)
            console.print(f"\n[bold green]🎉 构建成功! 大小: {size_mb:.1f} MB[/]")
            console.print(f"📂 输出: [white]{dst}[/]")
        else: console.print("[red]❌ 未找到输出文件[/]")
    else: console.print("[bold red]❌ 构建失败[/]")
    
    if os.path.exists(CONFIG["hook_file"]): os.remove(CONFIG["hook_file"])

# ==========================================
# 🚀 4. 模块 B: 发布版本
# ==========================================
def get_pypi_version(package_name):
    try:
        url = f"https://pypi.org/pypi/{package_name}/json"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            releases = list(resp.json()["releases"].keys())
            if releases:
                releases.sort(key=lambda x: version.parse(x))
                return releases[-1]
    except: pass
    return "0.0.0"

def release_workflow():
    console.rule("[bold magenta]🚀 发布新版本 (PyPI + Git + Zenodo)[/]")
    
    local_ver = get_local_version()
    pypi_ver = get_pypi_version(CONFIG["package_name"])
    
    try:
        v_local = version.parse(local_ver)
        v_pypi = version.parse(pypi_ver)
        base = max(v_local, v_pypi)
        parts = base.base_version.split('.')
        parts[-1] = str(int(parts[-1]) + 1)
        suggested_ver = ".".join(parts)
    except: suggested_ver = local_ver

    table = Table(show_header=False, box=None)
    table.add_row("本地版本:", local_ver)
    table.add_row("PyPI 版本:", pypi_ver)
    table.add_row("建议版本:", f"[bold green]{suggested_ver}[/]")
    console.print(Panel(table, title="版本信息"))

    target_ver = ensure_version_sync(action_name="发布")
    
    steps = []
    if Confirm.ask("📦 发布到 PyPI?"): steps.append("pypi")
    if Confirm.ask("🐙 同步到 Git (Tag)?"): steps.append("git")
    
    if not steps: return

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), TaskProgressColumn(), console=console
    ) as progress:
        
        if "pypi" in steps:
            task_build = progress.add_task("[magenta]构建 Wheel...", total=1)
            cleanup_all(silent=True)
            subprocess.run([sys.executable, "-m", "build"], capture_output=True, check=True)
            progress.advance(task_build)
            
            progress.stop()
            console.print("[blue]准备上传 PyPI...[/]")
            subprocess.run([sys.executable, "-m", "twine", "upload", "dist/*"], check=False)
            progress.start()
            
        if "git" in steps:
            task_git = progress.add_task("[blue]Git 同步...", total=1)
            try:
                # 关键：将 .zenodo.json 加入 git add 列表
                files_to_add = [CONFIG["version_file"], CONFIG["pyproject_file"]]
                if os.path.exists(CONFIG["zenodo_output"]):
                    files_to_add.append(CONFIG["zenodo_output"])
                
                subprocess.run(["git", "add"] + files_to_add, check=True)
                subprocess.run(["git", "commit", "-m", f"chore: bump version to {target_ver}"], check=True)
                subprocess.run(["git", "tag", "-a", f"v{target_ver}", "-m", f"Release v{target_ver}"], check=True)
                
                branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True).stdout.strip() or "main"
                subprocess.run(["git", "push", "origin", branch, "--tags"], check=True)
            except Exception as e:
                console.print(f"[red]Git 失败: {e}[/]")
            progress.advance(task_git)
            
    cleanup_all(silent=True)
    console.print(f"\n[bold green]✅ 发布完成! 当前版本: {target_ver}[/]")

# ==========================================
# 🧹 5. 清理逻辑
# ==========================================
def cleanup_all(silent=False):
    targets = [
        "dist", "build", "__pycache__",
        f"src/{CONFIG['package_name'].replace('-', '_')}.egg-info"
    ]
    for t in targets:
        if os.path.exists(t): shutil.rmtree(t, ignore_errors=True)
            
    spec_files = glob.glob(os.path.join(CONFIG["base_dir"], "*.spec"))
    for f in spec_files:
        try: os.remove(f)
        except: pass
        
    if not silent: console.print("[green]🧹 环境清理完成[/]")

# ==========================================
# 🖥️ 主菜单
# ==========================================
def main():
    if os.path.basename(os.getcwd()) == "ria_gui": os.chdir("../..")
        
    while True:
        console.clear()
        console.print(Panel.fit(f"[bold white]RIA 开发工具箱[/] [dim]({get_local_version()})[/]", border_style="blue"))
        print("1. 🔨 构建 Lite 版 EXE")
        print("2. 🚀 发布新版本 (PyPI + Git + Zenodo)")
        print("3. 🧹 清理构建垃圾")
        print("0. 🚪 退出")
        
        choice = Prompt.ask("请选择", choices=["0", "1", "2", "3"], default="1")
        if choice == "1": build_exe_workflow()
        elif choice == "2": release_workflow()
        elif choice == "3": cleanup_all()
        elif choice == "0": 
            console.print("[yellow]Bye![/]")
            sys.exit(0)
            
        if not Confirm.ask("\n🔙 返回主菜单?", default=True): sys.exit(0)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(0)