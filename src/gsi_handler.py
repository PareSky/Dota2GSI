"""
GSI 数据处理模块
- 接收并解析 Dota 2 推送的 JSON 数据
- 按游戏时间分流：新游戏 → 新日志文件
- 支持控制台美化输出 + 文件结构化日志
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from vision_tracker import VisionTracker, VisionEvent
from tts import hero_cn_name, speak
from game_timer import GameTimer, TimerEvent
from ai_advisor import AdvisorEvent
from ai_worker import AiAdvisorWorker
from role_selector import RoleSelector


class GSIHandler:
    """处理 Dota 2 GSI 推送的每一帧数据"""

    def __init__(
        self,
        config: Dict[str, Any],
        ai_worker: Optional[AiAdvisorWorker] = None,
        role_selector: Optional[RoleSelector] = None,
    ):
        log_cfg = config.get("logging", {})
        self.log_dir: str = log_cfg.get("log_dir", "./logs")
        self.console_pretty: bool = log_cfg.get("console_pretty_print", True)
        self.console_max_depth: int = log_cfg.get("console_max_depth", 0)
        self.session_file: bool = log_cfg.get("session_file", True)
        self.json_lines: bool = log_cfg.get("json_lines", True)

        # 视野追踪
        vision_cfg = config.get("vision", {})
        self.vision_enabled: bool = vision_cfg.get("enabled", True)
        self.vision_event_log: str = vision_cfg.get("event_log_file", "./logs/vision_events.jsonl")
        self._vision_tracker = VisionTracker() if self.vision_enabled else None
        self._game_timer = GameTimer()

        # AI 教练
        advisor_cfg = config.get("ai_advisor", {})
        self.advisor_enabled: bool = advisor_cfg.get("enabled", False)
        self._ai_worker = None
        self._role_selector = None
        if self.advisor_enabled:
            self._ai_worker = ai_worker or AiAdvisorWorker(
                config=advisor_cfg,
                on_event=self._on_advisor_event,
            )
            self._role_selector = role_selector or RoleSelector()

        self._session_started: bool = False
        self._session_file_path: Optional[str] = None
        self._last_daytime: Optional[bool] = None  # 上一帧是否为白天
        self._last_write_time: float = -1  # 上次写入日志的游戏时间
        self._last_game_state: str = ""  # 上一帧的 game_state

        os.makedirs(self.log_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------

    def handle(self, raw_body: bytes) -> Dict[str, Any]:
        """处理一次 POST 请求"""
        data = json.loads(raw_body.decode("utf-8"))

        game_time = self._extract_game_time(data)

        # 检测新游戏开始：game_state 变为 GAME_IN_PROGRESS
        game_state = data.get("map", {}).get("game_state", "")
        if game_state == "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS" and self._last_game_state != "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS":
            self._start_new_session()
        self._last_game_state = game_state

        # 视野追踪
        if self._vision_tracker:
            minimap = data.get("minimap", {})
            player_team = data.get("player", {}).get("team_name", "")
            map_info = data.get("map", {})
            events = self._vision_tracker.update(
                minimap, player_team, game_time,
                radiant_score=map_info.get("radiant_score", 0),
                dire_score=map_info.get("dire_score", 0),
            )
            for evt in events:
                self._on_vision_event(evt)

        # 资源计时器（死亡时不播报）
        if self._game_timer:
            timer_events = self._game_timer.update(game_time)
            hero_alive = data.get("hero", {}).get("alive", True)
            if hero_alive:
                for te in timer_events:
                    self._on_timer_event(te)

        # AI 教练建议：仅提交最新帧，网络请求在后台线程中执行
        if self._ai_worker:
            role = self._role_selector.poll_result() if self._role_selector else None
            if role:
                self._ai_worker.set_role(role)
            self._ai_worker.submit(data)

        # 昼夜检测
        daytime = data.get("map", {}).get("daytime")
        if daytime is not None:
            if self._last_daytime is True and daytime is False:
                self._on_night_fall()
            self._last_daytime = daytime

        # 控制台输出
        if self.console_pretty:
            self._print_to_console(data)

        # 文件日志
        self._write_to_file(data)

        return data

    # ------------------------------------------------------------------
    # 会话管理
    # ------------------------------------------------------------------

    def _start_new_session(self) -> None:
        """开始新的日志会话"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gsi_session_{ts}.jsonl"
        self._session_file_path = os.path.join(self.log_dir, filename)
        self._session_started = True

        # 新游戏重置视野追踪和计时器
        if self._vision_tracker:
            self._vision_tracker.reset()
        if self._game_timer:
            self._game_timer.reset()
        if self._ai_worker:
            self._ai_worker.reset()
        self._last_daytime = None
        self._last_write_time = -1
        self._last_game_state = "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS"

        print(f"\n{'='*60}")
        print(f"🆕 新游戏会话: {filename}")
        print(f"{'='*60}\n")

        # 分路窗口在独立进程中运行，不阻塞当前 GSI 请求
        if self._role_selector:
            self._role_selector.request_selection()

    # ------------------------------------------------------------------
    # 控制台输出
    # ------------------------------------------------------------------

    def _print_to_console(self, data: Dict[str, Any]) -> None:
        """美化打印到控制台（仅摘要行，完整 JSON 见日志文件）"""
        now = datetime.now().strftime("%H:%M:%S")
        summary = self._build_summary(data)
        # print(f"[{now}] {summary}")

    def _build_summary(self, data: Dict[str, Any]) -> str:
        """构建一行摘要信息"""
        parts: list[str] = []

        # 游戏时间
        map_info = data.get("map", {})
        gt = map_info.get("clock_time", None)
        if gt is not None:
            mins = int(gt // 60)
            secs = int(gt % 60)
            parts.append(f"⏱ {mins:02d}:{secs:02d}")

        # 玩家信息
        player = data.get("player", {})
        hero = data.get("hero", {})
        hero_name = hero.get("name", player.get("hero_name", ""))
        if hero_name:
            parts.append(f"🦸 {hero_name}")

        # KDA
        kills = player.get("kills", 0)
        deaths = player.get("deaths", 0)
        assists = player.get("assists", 0)
        parts.append(f"⚔ {kills}/{deaths}/{assists}")

        # 等级
        lvl = hero.get("level", None)
        if lvl is not None:
            parts.append(f"⬆ Lv.{lvl}")

        # 金钱
        gold = player.get("gold", None)
        if gold is not None:
            parts.append(f"💰 {gold}")

        # 比分
        radiant_score = map_info.get("radiant_score", 0)
        dire_score = map_info.get("dire_score", 0)
        parts.append(f"🏆 {radiant_score}-{dire_score}")

        # 建筑状态
        buildings = data.get("buildings", {})
        if buildings:
            bld = self._buildings_summary(buildings)
            if bld:
                parts.append(f"🏗 {bld}")

        # 地图状态
        game_state = map_info.get("game_state", "")
        if game_state:
            parts.append(f"📊 {game_state}")

        return " | ".join(parts)

    @staticmethod
    def _buildings_summary(buildings: dict) -> str:
        """建筑状态摘要：统计双方存活塔数"""
        parts = []
        for team in ("radiant", "dire"):
            team_b = buildings.get(team, {})
            towers = team_b.get("towers", {})
            if towers:
                alive = sum(1 for t in towers.values() if t.get("health", 0) > 0)
                parts.append(f"{team[:1].upper()}{alive}")
        return "/".join(parts) if parts else ""

    # ------------------------------------------------------------------
    # 文件日志
    # ------------------------------------------------------------------

    def _write_to_file(self, data: Dict[str, Any]) -> None:
        """写入日志文件（每分钟最多一次）"""
        if not self.json_lines or not self._session_file_path:
            return
        game_time = data.get("map", {}).get("clock_time", -1)
        if game_time < 0:
            return
        # 距上次写入不足 60 秒 → 跳过
        if self._last_write_time >= 0 and (game_time - self._last_write_time) < 60:
            return
        self._last_write_time = game_time
        with open(self._session_file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # 视野事件
    # ------------------------------------------------------------------

    def _on_vision_event(self, event: VisionEvent) -> None:
        """视野变化事件：打印到控制台 + 写入事件日志 + 语音（仅前 10 分钟）"""
        # 10 分钟后不再提示
        if event.game_time > 600:
            return

        # 控制台打印
        print(f"  >>> {event}")

        # 写入事件日志
        event_path = os.path.join(self.log_dir, "vision_events.jsonl")
        with open(event_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "event": event.event_type,
                "hero": event.hero_name,
                "xpos": event.xpos,
                "ypos": event.ypos,
                "game_time": event.game_time,
                "timestamp": event.timestamp,
            }, ensure_ascii=False) + "\n")

        # 语音提示
        if event.event_type == "LEFT":
            name = hero_cn_name(event.hero_name)
            speak(f"{name} miss")
        elif event.event_type == "MASS_LEFT":
            speak("敌方多人消失")

    # ------------------------------------------------------------------
    # 资源计时器
    # ------------------------------------------------------------------

    def _on_timer_event(self, event: TimerEvent) -> None:
        """资源即将刷新：控制台 + 语音"""
        msg = f"{event.label} 准备刷新"
        print(f"  ⏰ {msg}")
        speak(msg)

    def _on_advisor_event(self, event: AdvisorEvent) -> None:
        """AI 教练建议：控制台打印分析 + 语音朗读指令"""
        # if event.analysis_text:
        #     print(f"  📊 {event.analysis_text}")
        if event.advice_text:
            speak(event.advice_text)

    def _on_night_fall(self) -> None:
        """进入夜晚：控制台 + 语音"""
        print("  🌙 进入夜晚")
        speak("夜晚降临")

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_game_time(data: Dict[str, Any]) -> float:
        """从数据中提取游戏时间（秒）"""
        return data.get("map", {}).get("clock_time", -1.0)

    @staticmethod
    def _truncate_depth(obj: Any, max_depth: int, current: int = 0) -> Any:
        """限制嵌套深度，防止刷屏"""
        if max_depth <= 0:
            return obj
        if isinstance(obj, dict):
            if current >= max_depth:
                return f"<dict:{len(obj)} keys>"
            return {k: GSIHandler._truncate_depth(v, max_depth, current + 1) for k, v in obj.items()}
        if isinstance(obj, list):
            if current >= max_depth:
                return f"<list:{len(obj)} items>"
            return [GSIHandler._truncate_depth(v, max_depth, current + 1) for v in obj[:5]]  # 只展示前5项
        return obj
