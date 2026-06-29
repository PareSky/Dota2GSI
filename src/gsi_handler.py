"""
GSI 数据处理模块
- 接收并解析 Dota 2 推送的 JSON 数据
- 检测新游戏并管理会话状态
- 按配置写入结构化日志
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from vision_tracker import VisionTracker, VisionEvent
from tts import (
    clear_pending_speech,
    configure_speech,
    hero_cn_name,
    speak,
)
from game_timer import GameTimer, TimerEvent
from ai_advisor import AdvisorEvent
from ai_worker import AiAdvisorWorker
from role_selector import RoleSelector
from speech_policy import SpeechSettings, compose_advisor_speech


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
        self.session_file: bool = log_cfg.get("session_file", True)

        # 视野追踪
        vision_cfg = config.get("vision", {})
        self.vision_enabled: bool = vision_cfg.get("enabled", True)
        self._vision_tracker = VisionTracker() if self.vision_enabled else None
        self._game_timer = GameTimer()

        # TTS 语音配置
        tts_cfg = config.get("tts", {})
        configure_speech(tts_cfg)
        self._speech_settings = SpeechSettings.from_config(tts_cfg)

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

        self._session_file_path: Optional[str] = None
        self._last_daytime: Optional[bool] = None  # 上一帧是否为白天
        self._last_write_time: float = -1  # 上次写入日志的游戏时间
        self._last_matchid: Optional[str] = None  # 上一帧的 matchid（用于检测新游戏）

        os.makedirs(self.log_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------

    def handle(self, raw_body: bytes) -> Dict[str, Any]:
        """处理一次 POST 请求"""
        data = json.loads(raw_body.decode("utf-8"))

        game_time = self._extract_game_time(data)

        # 检测新游戏开始：以 map.matchid 判断是否同一局
        matchid = data.get("map", {}).get("matchid")
        is_new_game = (
            matchid is not None
            and matchid != self._last_matchid
        )
        if is_new_game:
            self._start_new_session()
        if matchid is not None:
            self._last_matchid = matchid

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
            hero_alive = data.get("hero", {}).get("alive", True)
            if hero_alive:
                timer_events = self._game_timer.update(game_time)
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

        # 文件日志
        self._write_to_file(data)

        return data

    # ------------------------------------------------------------------
    # 会话管理
    # ------------------------------------------------------------------

    def _start_new_session(self) -> None:
        """开始新的日志会话"""
        clear_pending_speech("advisor")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gsi_session_{ts}.jsonl"
        self._session_file_path = (
            os.path.join(self.log_dir, filename)
            if self.session_file
            else None
        )

        # 新游戏重置视野追踪和计时器
        if self._vision_tracker:
            self._vision_tracker.reset()
        if self._game_timer:
            self._game_timer.reset()
        if self._ai_worker:
            self._ai_worker.reset()
        self._last_daytime = None
        self._last_write_time = -1

        print(f"\n{'='*60}")
        print(f"🆕 新游戏会话: {filename}")
        print(f"{'='*60}\n")

        # 分路窗口在独立进程中运行，不阻塞当前 GSI 请求
        if self._role_selector:
            self._role_selector.request_selection()

    # ------------------------------------------------------------------
    # 文件日志
    # ------------------------------------------------------------------

    def _write_to_file(self, data: Dict[str, Any]) -> None:
        """写入日志文件（每分钟最多一次）"""
        if not self._session_file_path:
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
        if event.advice_text:
            text = compose_advisor_speech(
                analysis=event.analysis_text,
                command=event.advice_text,
                item=event.item_text,
                speech_level=event.speech_level,
                settings=self._speech_settings,
            )
            if text:
                speak(text, category="advisor")

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
