"""AI 教练后台执行器。

GSI 请求线程只提交最新游戏帧；AiAdvisor.update() 及其网络请求在后台线程执行。
"""

import queue
import threading
from typing import Any, Callable, Dict, Optional

from ai_advisor import AdvisorEvent, AiAdvisor


class AiAdvisorWorker:
    """在单独线程中串行运行 AiAdvisor，并只保留最新待处理帧。"""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        on_event: Optional[Callable[[AdvisorEvent], None]] = None,
        advisor: Optional[AiAdvisor] = None,
    ):
        self._advisor = advisor or AiAdvisor(config or {})
        self._on_event = on_event or (lambda event: None)
        self._commands: queue.Queue = queue.Queue()
        self._latest_data = None
        self._generation = 0
        self._data_lock = threading.Lock()
        self._wake = threading.Event()
        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            name="AiAdvisorWorker",
            daemon=True,
        )
        self._thread.start()

    def submit(self, data: Dict[str, Any]) -> None:
        """提交一帧数据；后台忙碌时用新帧替换尚未处理的旧帧。"""
        with self._data_lock:
            self._latest_data = (self._generation, data)
        self._wake.set()

    def set_role(self, role: str) -> None:
        self._commands.put(("set_role", role))
        self._wake.set()

    def reset(self) -> None:
        with self._data_lock:
            self._generation += 1
            self._latest_data = None
        self._commands.put(("reset", None))
        self._wake.set()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._wake.set()
        self._thread.join(timeout=1)

    def _run(self) -> None:
        while self._running:
            self._wake.wait()
            self._wake.clear()

            self._run_commands()
            pending = self._take_latest_data()
            if pending is None:
                continue
            generation, data = pending

            try:
                events = self._advisor.update(data)
                if not self._is_current_generation(generation):
                    continue
                for event in events:
                    self._on_event(event)
            except Exception as exc:
                print(f"[AI Advisor Worker] 处理失败: {exc}")

    def _run_commands(self) -> None:
        while True:
            try:
                command, value = self._commands.get_nowait()
            except queue.Empty:
                return

            if command == "reset":
                self._advisor.reset()
            elif command == "set_role":
                self._advisor.set_role(value)

    def _take_latest_data(self):
        with self._data_lock:
            data = self._latest_data
            self._latest_data = None
            return data

    def _is_current_generation(self, generation: int) -> bool:
        with self._data_lock:
            return generation == self._generation
