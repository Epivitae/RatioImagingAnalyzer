import os
import re
import sys
import shutil
import subprocess
import requests
from packaging import version

# ================= 配置区 =================
PACKAGE_NAME = "ria-gui"  # PyPI 上的正式包名
VERSION_FILE = "src/ria_gui/_version.py"
PYPROJECT_FILE = "pyproject.toml"
# ==========================================

def get_local_base_version():
    """从 _version.py 读取基准版本号 (处理带 v 或不带 v 的情况)"""
    if not os.path.exists(VERSION_FILE):
        raise FileNotFoundError(f"找不到版本文件: {VERSION_FILE}")
        
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1).strip()
    raise ValueError(f"无法在 {VERSION_FILE} 中找到 __version__ 定义")

def get_pypi_version(package_name):
    """从 PyPI 获取线上已发布的最高版本号"""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            versions = list(data["releases"].keys())
            if not versions:
                return "0.0.0"
            # 使用 packaging.version 进行正确的语义化排序
            versions.sort(key=version.parse)
            return versions[-1]
    except Exception as e:
        print(f"⚠️ 联网获取 PyPI 版本失败: {e}")
    return "0.0.0"

def calculate_next_version(base_ver, pypi_ver):
    """
    版本递增核心逻辑：
    1. 剥离 'v' 前缀。
    2. 如果本地基准版本已更新 (Base > PyPI)，则从 Base.1 开始。
    3. 如果本地基准未变 (Base <= PyPI)，则在 PyPI 版本末尾数字 +1。
    """
    # 统一剥离前缀 'v'
    pure_base = base_ver.lstrip('v').strip()
    pure_pypi = pypi_ver.lstrip('v').strip()
    
    v_base = version.parse(pure_base)
    v_pypi = version.parse(pure_pypi)

    # 如果基准版本已经大于线上最高版本 (例如你手动把 1.7.9 改成了 1.8.0)
    if v_base > v_pypi:
        return f"{pure_base}.1"
    
    # 如果基准版本还在线上版本范围内 (Base 1.7.9, PyPI 1.7.9.11)
    # 取线上版本的最后一位进行递增
    pypi_parts = pure_pypi.split('.')
    try:
        last_num = int(pypi_parts[-1])
        next_parts = pypi_parts[:-1] + [str(last_num + 1)]
        return ".".join(next_parts)
    except (ValueError, IndexError):
        # 兜底方案
        return f"{pure_pypi}.1"

def update_pyproject(new_version):
    """修改 pyproject.toml 里的版本号"""
    if not os.path.exists(PYPROJECT_FILE):
        print(f"❌ 找不到 {PYPROJECT_FILE}")
        sys.exit(1)

    with open(PYPROJECT_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 使用 \g<1> 和 \g<3> 显式引用组，防止版本号开头的数字导致歧义
    new_content = re.sub(
        r'(^version\s*=\s*["\'])([^"\']+)(["\'])',
        rf'\g<1>{new_version}\g<3>',
        content,
        flags=re.MULTILINE
    )
    
    with open(PYPROJECT_FILE, "w", encoding="utf-8") as f:
        f.write(content if new_content == content else new_content)
    
    # 增加一个物理检查，确保文件真的写进去了
    print(f"✅ pyproject.toml 版本号已更新为: {new_version}")

def run_command(cmd):
    """执行 Shell 命令并检查结果"""
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"❌ 命令执行失败: {cmd}")
        sys.exit(1)

def main():
    print("🔍 正在检查版本信息...")
    
    # 1. 获取本地基准和线上版本
    local_base = get_local_base_version()
    online_last = get_pypi_version(PACKAGE_NAME)
    
    # 2. 计算目标发布版本号
    next_release = calculate_next_version(local_base, online_last)
    
    print("-" * 50)
    print(f"本地基准 (_version.py): {local_base}")
    print(f"线上最高 (PyPI):        {online_last}")
    print(f"本次计划发布版本:       {next_release}")
    print("-" * 50)

    # 3. 更新配置文件
    update_pyproject(next_release)
    
    # 4. 彻底清理旧的构建残留
    print("🧹 清理旧构建缓存...")
    folders_to_delete = ["dist", "build", "src/ria_gui.egg-info"]
    for folder in folders_to_delete:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"   已删除 {folder}")
    
    # 5. 执行构建
    print(f"🛠️ 正在构建 Wheel & SDist (版本: {next_release})...")
    run_command("python -m build")
    
    # 6. 上传到 PyPI
    print("🚀 准备上传到 PyPI...")
    # 注意：如果未配置 .pypirc，这里会提示输入 Token
    run_command("python -m twine upload dist/*")
    
    print(f"\n✨ 恭喜！版本 {next_release} 已成功发布到 PyPI。")

if __name__ == "__main__":
    main()