"""AI 提示词与建议 JSONL 日志。"""

import json
import os
from datetime import datetime
from typing import Optional


class AdvisorLogger:
    def __init__(self, log_dir: str):
        self._log_dir = log_dir
        self._prompt_log_path: Optional[str] = None
        self._advice_log_path: Optional[str] = None
        os.makedirs(log_dir, exist_ok=True)

    def log_prompt(
        self,
        user_message: str,
        system_prompt: str,
        game_time_minutes: int,
        history_section: str,
    ) -> None:
        separator = "=" * 60
        print(f"\n{separator}")
        print(
            f"🤖 发送给 AI 的提示词 "
            f"(游戏时间 {game_time_minutes}:00):"
        )
        print(
            f"   System: ({len(system_prompt)} 字符, 来自 AIPromt.md)"
        )
        print("   User:")
        for line in user_message.split("\n"):
            print(f"     {line}")
        print(f"{separator}\n")

        log_message = user_message
        if history_section:
            log_message = user_message.replace(history_section, "\n")
        if self._prompt_log_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._prompt_log_path = os.path.join(
                self._log_dir,
                f"ai_prompts_{ts}.jsonl",
            )

        entry = {
            "game_time_minutes": game_time_minutes,
            "system_prompt_length": len(system_prompt),
            "user_message": log_message,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        with open(self._prompt_log_path, "a", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def log_advice(
        self,
        advice: str,
        game_time: float,
        analysis: str = "",
    ) -> None:
        if self._advice_log_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._advice_log_path = os.path.join(
                self._log_dir,
                f"ai_advices_{ts}.jsonl",
            )
        mins = int(game_time // 60)
        secs = int(game_time % 60)
        entry = {
            "game_time": f"{mins}:{secs:02d}",
            "analysis": analysis,
            "command": advice,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        with open(self._advice_log_path, "a", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def reset(self) -> None:
        self._prompt_log_path = None
        self._advice_log_path = None
