import sys
import os

def launch_ria():
    """
    Bootstrap script to launch RIA (Liya) from the project root.
    """
    # 1. 获取当前脚本所在的绝对路径 (项目根目录)
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # 2. 定位到 src 目录
    src_path = os.path.join(project_root, 'src')
    
    # 3. 将 src 加入到 Python 的搜索路径最前面
    # 这样 Python 就能找到 'ria_gui' 这个包
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    try:
        # 4. 导入你的 main 函数
        # 根据之前的上下文，你的包结构是 src/ria_gui/main.py
        # 所以这里的导入路径是 ria_gui.main
        from ria_gui.main import main
        
        # 5. 启动应用
        main()
        
    except ImportError as e:
        print("❌ Launch Error: Could not import the application.")
        print(f"Details: {e}")
        print(f"\nDebug Info:")
        print(f"  - Project Root: {project_root}")
        print(f"  - Search Path (sys.path[0]): {sys.path[0]}")
        print("  - Expected file: src/ria_gui/main.py")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nUser interrupted execution.")
        sys.exit(0)

if __name__ == "__main__":
    launch_ria()