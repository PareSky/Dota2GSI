"""非阻塞的玩家分路选择窗口。

Tkinter 在独立进程中运行，避免它的 mainloop 阻塞 Flask 请求线程。
"""

import multiprocessing
import queue
from typing import Callable, Optional


def _show_role_dialog(result_queue) -> None:
    import tkinter as tk

    result = ""
    root = None

    try:
        root = tk.Tk()
        root.title("Dota 2 GSI - 选择分路")
        root.resizable(False, False)
        root.configure(bg="#1e1e2e")

        def choose(role: str) -> None:
            nonlocal result
            result = role
            root.destroy()

        tk.Label(
            root,
            text="选择你的分路",
            font=("Microsoft YaHei", 14, "bold"),
            fg="#cdd6f4",
            bg="#1e1e2e",
        ).pack(pady=(15, 12))

        btn_frame = tk.Frame(root, bg="#1e1e2e")
        btn_frame.pack(pady=(0, 15))
        roles = [
            ("1号位\n(大哥)", "#f38ba8", "1"),
            ("2号位\n(中单)", "#fab387", "2"),
            ("3号位\n(劣势路)", "#a6e3a1", "3"),
            ("4号位\n(劣势路辅助)", "#89b4fa", "4"),
            ("5号位\n(优势路辅助)", "#cba6f7", "5"),
        ]
        for label, color, role_id in roles:
            tk.Button(
                btn_frame,
                text=label,
                font=("Microsoft YaHei", 10),
                width=12,
                height=3,
                bg=color,
                fg="#1e1e2e",
                activebackground=color,
                command=lambda selected=role_id: choose(selected),
            ).pack(side=tk.LEFT, padx=3)

        root.update_idletasks()
        root.geometry(f"{root.winfo_reqwidth()}x{root.winfo_reqheight()}")
        root.attributes("-topmost", True)
        root.focus_force()
        root.mainloop()
    except Exception as exc:
        print(f"[Role Selector] 无法显示分路选择窗口: {exc}")
    finally:
        result_queue.put(result)


class RoleSelector:
    """管理分路选择子进程，并以轮询方式返回选择结果。"""

    def __init__(self, process_factory: Optional[Callable] = None):
        self._result_queue = multiprocessing.Queue()
        self._process_factory = process_factory or multiprocessing.Process
        self._process = None

    def request_selection(self) -> None:
        if self._process is not None and self._process.is_alive():
            return

        self._discard_old_results()
        self._process = self._process_factory(
            target=_show_role_dialog,
            args=(self._result_queue,),
        )
        self._process.daemon = True
        self._process.start()

    def poll_result(self) -> Optional[str]:
        try:
            result = self._result_queue.get_nowait()
        except queue.Empty:
            return None
        return result or None

    def _discard_old_results(self) -> None:
        while True:
            try:
                self._result_queue.get_nowait()
            except queue.Empty:
                return
