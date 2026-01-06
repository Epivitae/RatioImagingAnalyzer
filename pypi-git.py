import os
import re
import sys
import shutil
import subprocess

# ==========================================
# 🛠️ 0. 依赖自动检查
# ==========================================
def install_deps():
    required = ["rich", "requests", "packaging", "build", "twine"]
    installed = []
    try:
        import pkg_resources
        installed = {pkg.key for pkg in pkg_resources.working_set}
    except: pass

    missing = [pkg for pkg in required if pkg not in installed]
    if missing:
        print(f"正在安装发布工具依赖: {', '.join(missing)}...")
        subprocess.run([sys.executable, "-m", "pip", "install", *missing], check=True)

install_deps()

import requests
from packaging import version
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.prompt import Confirm, Prompt

# ================= 配置区 =================
PACKAGE_NAME = "ria-gui"
VERSION_FILE = "src/ria_gui/_version.py"
PYPROJECT_FILE = "pyproject.toml"
console = Console()
# ==========================================

def get_local_base_version():
    if not os.path.exists(VERSION_FILE):
        raise FileNotFoundError(f"版本文件不存在: {VERSION_FILE}")
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
            if not versions:
                return "0.0.0"
            versions.sort(key=version.parse)
            return versions[-1]
        elif response.status_code == 404:
            console.print("[dim]包尚未发布到 PyPI[/dim]")
            return "0.0.0"
    except requests.exceptions.Timeout:
        console.print("[yellow]⚠️ PyPI 请求超时，使用默认版本[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠️ PyPI 查询失败: {e}[/yellow]")
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

def update_version_file(new_version):
    """同时更新 _version.py 文件"""
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = re.sub(r'(__version__\s*=\s*["\'])([^"\']+)(["\'])', rf'\g<1>{new_version}\g<3>', content)
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)

def check_git_status():
    """检查 Git 状态"""
    try:
        # 检查是否有未提交的更改
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
        has_changes = bool(result.stdout.strip())

        # 获取当前分支
        result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, check=True)
        current_branch = result.stdout.strip() or "main"

        return {"has_changes": has_changes, "branch": current_branch}
    except Exception as e:
        console.print(f"[yellow]⚠️ Git 状态检查失败: {e}[/yellow]")
        return {"has_changes": False, "branch": "unknown"}

def run_git_commands(new_version):
    try:
        git_status = check_git_status()
        current_branch = git_status["branch"]
        console.print(f"[dim]当前分支: {current_branch}[/dim]")

        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"chore: bump version to {new_version}"], check=True)
        subprocess.run(["git", "tag", "-a", f"v{new_version}", "-m", f"Release v{new_version}"], check=True)
        subprocess.run(["git", "push", "origin", current_branch, "--tags"], check=True)
        console.print(f"[dim]✅ 已自动同步 Git: Commit, Tag (v{new_version}) & Push to {current_branch}[/dim]")
    except subprocess.CalledProcessError as e:
        console.print(f"[yellow]⚠️ Git 操作失败: {e}[/yellow]")
        console.print("[dim]提示: 可能需要先配置 git 凭据或检查网络连接[/dim]")
    except Exception as e:
        console.print(f"[yellow]⚠️ Git 操作异常: {e}[/yellow]")

def cleanup_artifacts():
    folders = ["dist", "build", "src/ria_gui.egg-info"]
    for folder in folders:
        if os.path.exists(folder):
            shutil.rmtree(folder, ignore_errors=True)

def check_prerequisites():
    """预检查必要条件"""
    errors = []

    # 检查必要文件
    if not os.path.exists(VERSION_FILE):
        errors.append(f"版本文件不存在: {VERSION_FILE}")
    if not os.path.exists(PYPROJECT_FILE):
        errors.append(f"配置文件不存在: {PYPROJECT_FILE}")
    if not os.path.exists("src/ria_gui"):
        errors.append("源码目录不存在: src/ria_gui")

    # 检查 twine 配置
    pypirc = os.path.expanduser("~/.pypirc")
    if not os.path.exists(pypirc):
        console.print("[dim]提示: ~/.pypirc 不存在，上传时需要手动输入 Token[/dim]")

    return errors

def main():
    # 切换到脚本所在目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    console.print(Panel.fit("[bold magenta]RIA / 莉丫[/bold magenta] - PyPI-GitHub 发布系统", border_style="magenta"))

    # 预检查
    errors = check_prerequisites()
    if errors:
        for e in errors:
            console.print(f"[red]❌ {e}[/red]")
        sys.exit(1)

    # 1. 获取版本信息
    with console.status("[bold green]正在同步云端版本...") as status:
        local_base = get_local_base_version()
        online_last = get_pypi_version(PACKAGE_NAME)
        next_release = calculate_next_version(local_base, online_last)
        git_status = check_git_status()

    table = Table(show_header=False, box=None)
    table.add_row("本地基准:", f"[cyan]{local_base}[/cyan]")
    table.add_row("线上最高:", f"[yellow]{online_last}[/yellow]")
    table.add_row("目标版本:", f"[bold green]{next_release}[/bold green]")
    table.add_row("当前分支:", f"[blue]{git_status['branch']}[/blue]")
    if git_status['has_changes']:
        table.add_row("未提交更改:", "[yellow]有[/yellow]")
    console.print(table)

    # 允许用户修改目标版本
    custom_ver = Prompt.ask(f"\n输入自定义版本号 (回车使用 {next_release})", default=next_release)
    if custom_ver != next_release:
        next_release = custom_ver
        console.print(f"[cyan]使用自定义版本: {next_release}[/cyan]")

    # --- 交互操作验证 ---
    do_pypi = Confirm.ask(f"\n📦 是否要发布到 [bold blue]PyPI[/bold blue] ({next_release})?")
    do_git = Confirm.ask(f"🐙 是否要同步到 [bold blue]Git {git_status['branch']}[/bold blue] (Commit/Tag/Push)?")

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

        # 步骤 1: 更新版本号
        t1 = progress.add_task("[cyan]同步版本号", total=2)
        update_pyproject(next_release)
        progress.advance(t1)
        update_version_file(next_release)
        progress.advance(t1)

        # 步骤 2: 构建
        t3 = progress.add_task("[magenta]打包构建 Wheel", total=1)
        cleanup_artifacts()
        res = subprocess.run([sys.executable, "-m", "build"], capture_output=True, text=True, encoding="utf-8")
        if res.returncode != 0:
            progress.stop()
            console.print(Panel(res.stderr or res.stdout, title="Build Error", border_style="red"))
            sys.exit(1)
        progress.advance(t3)

        # 步骤 3: 发布到 PyPI
        if do_pypi:
            t4 = progress.add_task("[green]发布至 PyPI", total=1)
            progress.stop()
            if Confirm.ask(f"\n[bold red]⚠️ 最后的警告：[/bold red] 确定要把 {next_release} 推送到 PyPI 吗?"):
                console.print("[blue]🔑 开始上传 (如需 Token 请输入):[/blue]")
                upload_res = subprocess.run([sys.executable, "-m", "twine", "upload", "dist/*"])
                if upload_res.returncode == 0:
                    progress.start()
                    progress.advance(t4)
                else:
                    console.print("\n[red]❌ 上传失败。[/red]")
                    console.print("[dim]提示: 使用 --username __token__ --password <token> 进行认证[/dim]")
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
    if do_git: summary.add_row(f"🐙 [white]Git:[/white] [blue]已同步至 {git_status['branch']} 分支并打标 v{next_release}[/blue]")

    console.print("\n")
    console.print(Panel(summary, border_style="green", title="Summary", expand=True))

if __name__ == "__main__":
    main()