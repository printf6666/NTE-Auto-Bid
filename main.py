# -*- coding: utf-8 -*-
"""异环自动竞拍 · 入口

    python main.py          → 打开 1280×720 挂机任务窗口
    双击 run_as_admin.bat    → 同上，且自动提权
"""
import sys

from app import main as gui_main


if __name__ == "__main__":
    sys.exit(gui_main())
