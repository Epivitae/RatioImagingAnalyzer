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
    raise ValueError("Missing __version__ in _version.py")

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
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"chore: bump version to {new_version}"], check=True)
        subprocess.run(["git", "tag", "-a", f"v{new_version}", "-m", f"Release v{new_version}"], check=True)
        subprocess.run(["git", "push", "origin", "main", "--tags"], check=True)
        console.print(f"[dim]✅ 已自动同步 Git: Commit, Tag (v{new_version}) & Push[/dim]")
    except Exception as e:
        console.print(f"[yellow]⚠️ Git 操作失败: {e}[/yellow]")

def cleanup_artifacts():
    folders = ["dist", "build", "src/ria_gui.egg-info"]
    for folder in folders:
        if os.path.exists(folder):
            shutil.rmtree(folder, ignore_errors=True)

def main():
    console.print(Panel.fit("[bold magenta]RIA / 莉丫[/bold magenta] - 终极自动化发布系统", border_style="magenta"))

    # 1. 预检
    with console.status("[bold green]正在同步云端版本...") as status:
        local_base = get_local_base_version()
        online_last = get_pypi_version(PACKAGE_NAME)
        next_release = calculate_next_version(local_base, online_last)

    table = Table(show_header=False, box=None)
    table.add_row("本地基准:", f"[cyan]{local_base}[/cyan]")
    table.add_row("线上最高:", f"[yellow]{online_last}[/yellow]")
    table.add_row("目标版本:", f"[bold green]{next_release}[/bold green]")
    console.print(table)
    
    # --- 交互操作验证 ---
    do_pypi = Confirm.ask(f"\n📦 是否要发布到 [bold blue]PyPI[/bold blue] ({next_release})?")
    do_git = Confirm.ask(f"🐙 是否要同步到 [bold git]Git Main[/bold git] (Commit/Tag/Push)?")

    if not do_pypi and not do_git:
        console.print("[yellow]未选择任何操作，退出脚本。[/yellow]")
        sys.exit(0)

    console.print("-" * 45)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        console=console
    ) as progress:
        
        # 步骤 1: 始终更新配置（因为是计算出的新版本）
        t1 = progress.add_task("[cyan]同步 pyproject.toml", total=1)
        update_pyproject(next_release)
        progress.advance(t1)

        # 步骤 2: 构建
        t3 = progress.add_task("[magenta]打包构建 Wheel", total=1)
        cleanup_artifacts()
        res = subprocess.run("python -m build", shell=True, capture_output=True, text=True, encoding="utf-8")
        if res.returncode != 0:
            progress.stop()
            console.print(Panel(res.stderr, title="Build Error", border_style="red"))
            sys.exit(1)
        progress.advance(t3)

        # 步骤 3: 发布到 PyPI
        if do_pypi:
            t4 = progress.add_task("[green]发布至 PyPI", total=1)
            progress.stop() 
            if Confirm.ask(f"\n[bold red]⚠️ 最后的警告：[/bold red] 确定要把 {next_release} 推送到 PyPI 吗?"):
                console.print("[blue]🔑 请输入 Token 完成上传:[/blue]")
                upload_res = subprocess.run("python -m twine upload dist/*", shell=True)
                if upload_res.returncode == 0:
                    progress.start()
                    progress.advance(t4)
                else:
                    console.print("\n[red]❌ 上传失败。[/red]")
                    sys.exit(1)
            else:
                console.print("[yellow]跳过 PyPI 上传。[/yellow]")
                progress.start()
                progress.advance(t4)

        # 步骤 4: 同步 Git
        if do_git:
            t5 = progress.add_task("[blue]同步 Git 仓库", total=1)
            progress.stop()
            run_git_commands(next_release)
            progress.start()
            progress.advance(t5)

        cleanup_artifacts()

    # 5. 成功面板
    summary = Table.grid(padding=1)
    summary.add_row(f"✅ [bold green]流程结束![/bold green]")
    if do_pypi: summary.add_row(f"📦 [white]PyPI:[/white] [blue]https://pypi.org/project/{PACKAGE_NAME}/{next_release}/[/blue]")
    if do_git: summary.add_row(f"🐙 [white]Git:[/white] [blue]已同步至远程仓库并打标[/blue]")
    
    console.print("\n")
    console.print(Panel(summary, border_style="green", title="Summary", expand=True))

if __name__ == "__main__":
    main()