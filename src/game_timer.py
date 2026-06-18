"""
游戏内资源计时器
- 跟踪游戏时间，在资源刷新前 15 秒语音 + 控制台提醒
- 神符: 每 2 分钟 (首次 2:00)
- 莲花: 每 3 分钟 (首次 3:00)
- 经验符: 每 7 分钟 (首次 7:00)
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class TimerEvent:
    """计时器事件"""
    label: str           # 资源名 (中文)
    spawn_time: float    # 刷新时的游戏时间（秒）
    seconds_left: int    # 距离刷新剩余秒数


class GameTimer:
    """追踪游戏内资源刷新时间"""

    # (资源名, 间隔秒数, 首次刷新秒数)
    SCHEDULES = [
        ("中路神符", 2 * 60, 2 * 60),          # 每2分钟，首次2:00
        ("莲花",     3 * 60, 3 * 60),          # 每3分钟，首次3:00
        ("经验符",   7 * 60, 7 * 60),          # 每7分钟，首次7:00
        ("魔方",    20 * 60, 20 * 60),         # 每20分钟，首次20:00
        ("魔晶",    999999, 15 * 60),          # 15分钟首次补货，仅一次
    ]

    # 提前提醒秒数
    WARNING_SECONDS = 15

    def __init__(self):
        # 记录已提醒过的刷新时间点 (label, spawn_time) 防止重复
        self._notified: set = set()

    def update(self, game_time: float) -> List[TimerEvent]:
        """
        根据当前游戏时间，返回需要提醒的资源事件列表。
        每个刷新点只提醒一次。
        """
        events: List[TimerEvent] = []

        for label, interval, first_spawn in self.SCHEDULES:
            # 中路神符和莲花 7 分钟后不再提示
            if label in ("中路神符", "莲花") and game_time >= 7 * 60:
                continue
            # 计算下一个刷新时间点
            next_spawn = self._next_spawn(game_time, interval, first_spawn)
            if next_spawn is None:
                continue

            seconds_left = next_spawn - game_time

            # 在提醒窗口内 (0 ~ WARNING_SECONDS 秒)
            if 0 <= seconds_left <= self.WARNING_SECONDS:
                key = (label, next_spawn)
                if key not in self._notified:
                    self._notified.add(key)
                    events.append(TimerEvent(
                        label=label,
                        spawn_time=next_spawn,
                        seconds_left=int(seconds_left),
                    ))

        return events

    def reset(self) -> None:
        """新游戏开始时重置"""
        self._notified.clear()

    @staticmethod
    def _next_spawn(game_time: float, interval: int, first_spawn: int) -> Optional[float]:
        """计算最近的下一个刷新时间点"""
        if first_spawn > game_time:
            return float(first_spawn)
        # 自首次刷新后，过了多少个间隔
        intervals_passed = int((game_time - first_spawn) // interval) + 1
        return float(first_spawn + intervals_passed * interval)
