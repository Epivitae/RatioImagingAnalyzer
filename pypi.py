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
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if match: return match.group(1).strip()
    raise ValueError("Missing __version__")

def get_pypi_version(package_name):
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
    pure_base = base_ver.lstrip('v').strip()
    pure_pypi = pypi_ver.lstrip('v').strip()
    v_base, v_pypi = version.parse(pure_base), version.parse(pure_pypi)
    if v_base > v_pypi: return f"{pure_base}.1"
    pypi_parts = pure_pypi.split('.')
    try:
        last_num = int(pypi_parts[-1])
        return ".".join(pypi_parts[:-1] + [str(last_num + 1)])
    except: return f"{pure_pypi}.1"

def update_pyproject(new_version):
    with open(PYPROJECT_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = re.sub(r'(^version\s*=\s*["\'])([^"\']+)(["\'])', rf'\g<1>{new_version}\g<3>', content, flags=re.MULTILINE)
    with open(PYPROJECT_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)

def run_git_commands(new_version):
    """自动提交版本更新并打标签"""
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"chore: bump version to {new_version}"], check=True)
        subprocess.run(["git", "tag", "-a", f"v{new_version}", "-m", f"Release v{new_version}"], check=True)
        console.print(f"[dim]已自动完成 Git Commit & Tag (v{new_version})[/dim]")
    except Exception as e:
        console.print(f"[yellow]⚠️ Git 操作失败 (可能是没有变动或未配置 git): {e}[/yellow]")

def main():
    console.print(Panel.fit("[bold magenta]RIA / 莉丫[/bold magenta] - 终极自动化发布", border_style="magenta"))

    # 1. 预检
    with console.status("[bold green]正在获取版本信息...") as status:
        local_base = get_local_base_version()
        online_last = get_pypi_version(PACKAGE_NAME)
        next_release = calculate_next_version(local_base, online_last)

    # 2. 信息展示
    table = Table(show_header=False, box=None)
    table.add_row("本地基准:", f"[cyan]{local_base}[/cyan]")
    table.add_row("线上最高:", f"[yellow]{online_last}[/yellow]")
    table.add_row("目标版本:", f"[bold green]{next_release}[/bold green]")
    console.print(table)
    
    if not Confirm.ask(f"\n确定要发布版本 [bold green]{next_release}[/bold green] 吗?"):
        console.print("[red]操作已取消。[/red]")
        sys.exit(0)

    console.print("-" * 40)

    # 3. 执行流程
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        console=console
    ) as progress:
        
        t1 = progress.add_task("[cyan]同步配置文件...", total=1)
        update_pyproject(next_release)
        progress.advance(t1)

        t2 = progress.add_task("[yellow]清理旧构建...", total=1)
        for folder in ["dist", "build", "src/ria_gui.egg-info"]:
            shutil.rmtree(folder, ignore_errors=True)
        progress.advance(t2)

        t3 = progress.add_task("[magenta]执行 Build...", total=1)
        res = subprocess.run("python -m build", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            console.print(Panel(res.stderr, title="Build Error", border_style="red"))
            sys.exit(1)
        progress.advance(t3)

        t4 = progress.add_task("[green]上传 PyPI...", total=1)
        progress.stop() # 必须停止以接受输入
        
        console.print("\n[bold blue]🔑 请输入您的 PyPI Token 进行验证:[/bold blue]")
        upload_res = subprocess.run("python -m twine upload dist/*", shell=True)
        
        if upload_res.returncode == 0:
            progress.start()
            progress.advance(t4)
            progress.stop() # 再次停止以执行 git
            
            # 自动 Git 同步
            run_git_commands(next_release)
            
            # 最终成功面板
            summary = Table.grid(padding=1)
            summary.add_row(f"✅ [bold green]发布成功![/bold green]")
            summary.add_row(f"📦 [white]安装命令: [/white] [bold cyan]pip install {PACKAGE_NAME}=={next_release}[/bold cyan]")
            summary.add_row(f"🔗 [white]链接: [/white] [blue]https://pypi.org/project/{PACKAGE_NAME}/{next_release}/[/blue]")
            
            console.print("\n")
            console.print(Panel(summary, border_style="green", title="Summary"))
        else:
            console.print("\n[red]❌ 上传失败，脚本终止。[/red]")
            sys.exit(1)

if __name__ == "__main__":
    main()