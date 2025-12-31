import os
import re
import sys
import shutil
import subprocess
import requests
from packaging import version
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.prompt import Confirm

# ================= 配置区 =================
PACKAGE_NAME = "ria-gui"
VERSION_FILE = "src/ria_gui/_version.py"
PYPROJECT_FILE = "pyproject.toml"
console = Console()
# ==========================================

def get_local_base_version():
    """从 _version.py 读取基准版本号"""
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if match: return match.group(1).strip()
    raise ValueError("Missing __version__ in _version.py")

def get_pypi_version(package_name):
    """从 PyPI 获取线上最高版本号"""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            versions = list(response.json()["releases"].keys())
            versions.sort(key=version.parse)
            return versions[-1]
    except: pass
    return "0.0.0"

def calculate_next_version(base_ver, pypi_ver):
    """计算下一个版本号逻辑"""
    pure_base = base_ver.lstrip('v').strip()
    pure_pypi = pypi_ver.lstrip('v').strip()
    v_base, v_pypi = version.parse(pure_base), version.parse(pure_pypi)
    
    # 如果本地基准已手动提升
    if v_base > v_pypi:
        return f"{pure_base}.1"
    
    # 基于线上版本末位递增
    pypi_parts = pure_pypi.split('.')
    try:
        last_num = int(pypi_parts[-1])
        return ".".join(pypi_parts[:-1] + [str(last_num + 1)])
    except:
        return f"{pure_pypi}.1"

def update_pyproject(new_version):
    """同步版本号到 pyproject.toml"""
    with open(PYPROJECT_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = re.sub(
        r'(^version\s*=\s*["\'])([^"\']+)(["\'])', 
        rf'\g<1>{new_version}\g<3>', 
        content, 
        flags=re.MULTILINE
    )
    with open(PYPROJECT_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)

def run_git_commands(new_version):
    """执行 Git 自动化工作流"""
    try:
        # 1. 添加所有变更
        subprocess.run(["git", "add", "."], check=True)
        # 2. 提交变更
        subprocess.run(["git", "commit", "-m", f"chore: bump version to {new_version}"], check=True)
        # 3. 创建本地标签
        subprocess.run(["git", "tag", "-a", f"v{new_version}", "-m", f"Release v{new_version}"], check=True)
        # 4. 推送到远程仓库 (含标签)
        subprocess.run(["git", "push", "origin", "main", "--tags"], check=True)
        console.print(f"[dim]已自动同步 Git: Commit, Tag (v{new_version}) & Push[/dim]")
    except Exception as e:
        console.print(f"[yellow]⚠️ Git 操作部分失败 (请检查是否有未配置的远程仓库): {e}[/yellow]")

def cleanup_artifacts():
    """清理构建产生的临时文件"""
    folders = ["dist", "build", "src/ria_gui.egg-info"]
    for folder in folders:
        if os.path.exists(folder):
            shutil.rmtree(folder, ignore_errors=True)
    console.print("[dim]已清理构建产生的临时文件夹。[/dim]")

def main():
    console.print(Panel.fit("[bold magenta]RIA / 莉丫[/bold magenta] - 终极自动化发布系统", border_style="magenta"))

    # 1. 预检阶段
    with console.status("[bold green]正在同步云端版本...") as status:
        local_base = get_local_base_version()
        online_last = get_pypi_version(PACKAGE_NAME)
        next_release = calculate_next_version(local_base, online_last)

    # 2. 信息确认
    info_table = Table(show_header=False, box=None)
    info_table.add_row("本地基准:", f"[cyan]{local_base}[/cyan]")
    info_table.add_row("线上最高:", f"[yellow]{online_last}[/yellow]")
    info_table.add_row("目标版本:", f"[bold green]{next_release}[/bold green]")
    console.print(info_table)
    
    if not Confirm.ask(f"\n🚀 确认以版本 [bold green]{next_release}[/bold green] 发布到 PyPI 吗?"):
        console.print("[red]已取消发布。[/red]")
        sys.exit(0)

    console.print("-" * 45)

    # 3. 执行任务
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        console=console,
        transient=False
    ) as progress:
        
        # 步骤 1: 更新配置
        t1 = progress.add_task("[cyan]同步 pyproject.toml", total=1)
        update_pyproject(next_release)
        progress.advance(t1)

        # 步骤 2: 预清理
        t2 = progress.add_task("[yellow]准备构建环境", total=1)
        cleanup_artifacts()
        progress.advance(t2)

        # 步骤 3: 构建
        t3 = progress.add_task("[magenta]正在执行打包构建", total=1)
        res = subprocess.run("python -m build", shell=True, capture_output=True, text=True, encoding="utf-8")
        if res.returncode != 0:
            progress.stop()
            console.print(Panel(res.stderr, title="Build Error", border_style="red"))
            sys.exit(1)
        progress.advance(t3)

        # 步骤 4: 上传
        t4 = progress.add_task("[green]上传至 PyPI", total=1)
        progress.stop()  # 暂停进度条以允许 Token 输入交互
        
        console.print("\n[bold blue]🔑 请输入 PyPI API Token 完成上传:[/bold blue]")
        upload_res = subprocess.run("python -m twine upload dist/*", shell=True)
        
        if upload_res.returncode == 0:
            progress.start()
            progress.advance(t4)
            progress.stop()  # 停止进度条以执行 Git 命令

            # 4. 后续自动化操作
            run_git_commands(next_release)
            cleanup_artifacts()

            # 5. 成功面板
            summary = Table.grid(padding=1)
            summary.add_row(f"✅ [bold green]发布成功![/bold green]")
            summary.add_row(f"📦 [white]安装命令: [/white] [bold cyan]pip install {PACKAGE_NAME}=={next_release}[/bold cyan]")
            summary.add_row(f"🔗 [white]PyPI 地址: [/white] [blue]https://pypi.org/project/{PACKAGE_NAME}/{next_release}/[/blue]")
            
            console.print("\n")
            console.print(Panel(summary, border_style="green", title="Summary", expand=True))
        else:
            console.print("\n[red]❌ 上传失败，请检查网络或版本冲突。[/red]")
            sys.exit(1)

if __name__ == "__main__":
    main()