"""运行时资源路径工具，兼容源码运行和 PyInstaller 打包。"""

import os
import sys


def resource_path(*parts: str) -> str:
    """返回打包资源的绝对路径。"""
    if getattr(sys, "frozen", False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.abspath(os.path.join(base_dir, *parts))
