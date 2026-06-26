"""运行时资源路径工具，兼容源码运行和 PyInstaller 打包。"""

import os
import sys


def resource_path(*parts: str) -> str:
    """返回打包资源的绝对路径（始终读取 bundled 版本，源码运行时回到项目根目录）。"""
    if getattr(sys, "frozen", False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.abspath(os.path.join(base_dir, *parts))


def editable_resource_path(*parts: str) -> str:
    """返回可编辑资源的路径。

    打包后优先查找 exe 同目录下的副本（用户可编辑），
    不存在时回退到 bundled 版本。源码运行时直接返回源码路径。
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        external_path = os.path.abspath(os.path.join(exe_dir, *parts))
        if os.path.exists(external_path):
            return external_path
        return resource_path(*parts)
    else:
        return resource_path(*parts)
