"""
main.py — 全能文档格式工厂 入口

使用方式:
    python main.py

打包 EXE:
    pyinstaller --onefile --windowed --name=FormatConverter main.py
"""

import multiprocessing
import sys
import os

# 确保项目根目录在 sys.path 中（方便 PyInstaller 打包后也能找到模块）
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def main():
    # PyInstaller freeze_support（必须放在最前面）
    multiprocessing.freeze_support()

    # 初始化字体检测
    from core.font_detector import init_font
    init_font()

    # 启动 GUI
    from gui.app import App
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()