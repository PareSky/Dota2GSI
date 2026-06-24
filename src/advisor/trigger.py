"""AI 教练触发条件与冷却状态机。"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from advisor.extractor import StateExtractor
from tts import hero_cn_name


@dataclass
class TriggerDecision:
    should_query: bool
    clock_time: float = -1
    recently_killed: Dict[int, List[str]] = field(default_factory=dict)


class TriggerController:
    COOLDOWN_SECONDS = 20
    SCORE_DELAY_SECONDS = 5
    WARMUP_SECONDS = 60

    def __init__(
        self,
        interval_minutes: int,
        extractor: StateExtractor,
    ):
        self._interval_minutes = interval_minutes
        self._extractor = extractor
        self.reset()

    def reset(self) -> None:
        self.last_bucket = -1
        self._last_scores = (-1, -1)
        self._score_change_time = -1
        self.last_query_time = -1
        self._last_frame_heroes: Dict[int, set] = {}
        self._recently_killed: Dict[int, List[str]] = {}

    def evaluate(self, data: Dict[str, Any]) -> TriggerDecision:
        clock_time = data.get("map", {}).get("clock_time", -1)
        if clock_time < self.WARMUP_SECONDS:
            return TriggerDecision(False, clock_time)

        map_info = data.get("map", {})
        current_scores = (
            map_info.get("radiant_score", 0),
            map_info.get("dire_score", 0),
        )
        if self._last_scores != (-1, -1) and current_scores != self._last_scores:
            current_heroes = self._extractor.extract_hero_names(data)
            for team in (2, 3):
                disappeared = (
                    self._last_frame_heroes.get(team, set())
                    - current_heroes.get(team, set())
                )
                for hero_name in disappeared:
                    cn = hero_cn_name(hero_name)
                    if cn not in self._recently_killed.get(team, []):
                        self._recently_killed.setdefault(team, []).append(cn)
            if self._score_change_time > 0:
                print(
                    f"  [AI Advisor] 比分再次变化 {self._last_scores} "
                    f"→ {current_scores}，重新计时 5 秒"
                )
            else:
                killed = [
                    name
                    for names in self._recently_killed.values()
                    for name in names
                ]
                print(
                    f"  [AI Advisor] 比分变化 {self._last_scores} "
                    f"→ {current_scores}，检测到死亡: "
                    f"{killed if killed else '未能识别'}，5 秒后查询 AI"
                )
            self._score_change_time = clock_time
        self._last_scores = current_scores

        interval_seconds = self._interval_minutes * 60
        adjusted_time = clock_time - 5
        current_bucket = (
            int(adjusted_time / interval_seconds)
            if adjusted_time >= 0
            else -1
        )
        timer_trigger = (
            current_bucket >= 1 and current_bucket > self.last_bucket
        )
        score_trigger = (
            self._score_change_time > 0
            and clock_time - self._score_change_time
            >= self.SCORE_DELAY_SECONDS
        )

        if not timer_trigger and not score_trigger:
            if (
                self.last_bucket == -1
                and current_bucket == 1
                and clock_time > interval_seconds - 60
            ):
                print(
                    f"  [AI Advisor] 将在 "
                    f"{interval_seconds // 60} 分钟后首次查询 AI..."
                )
            self._update_last_frame(data)
            return TriggerDecision(False, clock_time)

        if (
            self.last_query_time > 0
            and clock_time - self.last_query_time < self.COOLDOWN_SECONDS
        ):
            remaining = self.COOLDOWN_SECONDS - (
                clock_time - self.last_query_time
            )
            if score_trigger:
                self._score_change_time = -1
                self._recently_killed = {}
                print(
                    f"  [AI Advisor] 比分触发但冷却中"
                    f"（剩余 {remaining:.0f}s），跳过"
                )
            if timer_trigger:
                self.last_bucket = current_bucket
            self._update_last_frame(data)
            return TriggerDecision(False, clock_time)

        if timer_trigger:
            self.last_bucket = current_bucket
        self._score_change_time = -1
        recently_killed = self._recently_killed
        self._recently_killed = {}
        return TriggerDecision(
            True,
            clock_time,
            recently_killed,
        )

    def complete(
        self,
        data: Dict[str, Any],
        succeeded: bool,
    ) -> None:
        if succeeded:
            self.last_query_time = data.get("map", {}).get("clock_time", -1)
        self._update_last_frame(data)

    def _update_last_frame(self, data: Dict[str, Any]) -> None:
        self._last_frame_heroes = self._extractor.extract_hero_names(data)
