import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import yaml

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from gsi_handler import GSIHandler
from vision_tracker import VisionEvent


def game_frame(clock_time=1):
    return {
        "map": {
            "clock_time": clock_time,
            "game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
        },
        "hero": {"alive": True},
    }


class LoggingConfigTests(unittest.TestCase):
    def make_handler(self, log_dir, session_file):
        return GSIHandler(
            {
                "logging": {"log_dir": log_dir, "session_file": session_file},
                "vision": {"enabled": False},
                "ai_advisor": {"enabled": False},
            }
        )

    def test_session_file_true_creates_and_writes_session_log(self):
        with tempfile.TemporaryDirectory() as log_dir:
            handler = self.make_handler(log_dir, True)
            with redirect_stdout(io.StringIO()):
                handler.handle(json.dumps(game_frame()).encode("utf-8"))
            session_logs = list(Path(log_dir).glob("gsi_session_*.jsonl"))
        self.assertEqual(len(session_logs), 1)

    def test_session_file_false_does_not_create_session_log(self):
        with tempfile.TemporaryDirectory() as log_dir:
            handler = self.make_handler(log_dir, False)
            with redirect_stdout(io.StringIO()):
                handler.handle(json.dumps(game_frame()).encode("utf-8"))
            session_logs = list(Path(log_dir).glob("gsi_session_*.jsonl"))
            session_path = handler._session_file_path
        self.assertEqual(session_logs, [])
        self.assertIsNone(session_path)

    def test_vision_events_use_log_dir(self):
        with tempfile.TemporaryDirectory() as log_dir:
            handler = GSIHandler(
                {
                    "logging": {"log_dir": log_dir},
                    "vision": {"enabled": True},
                    "ai_advisor": {"enabled": False},
                }
            )
            event = VisionEvent(
                event_type="ENTERED",
                hero_name="npc_dota_hero_axe",
                xpos=1,
                ypos=2,
                game_time=10,
                timestamp="2026-06-24T00:00:00",
            )
            with redirect_stdout(io.StringIO()):
                handler._on_vision_event(event)
            event_log_exists = (Path(log_dir) / "vision_events.jsonl").exists()
        self.assertTrue(event_log_exists)


class TtsConfigTests(unittest.TestCase):
    def test_repo_config_yaml_has_tts_defaults(self):
        config_path = Path(__file__).resolve().parents[1] / "config.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.assertEqual(
            config["tts"],
            {
                "rate": 4,
                "full_max_seconds": 25,
                "estimated_chars_per_second": 7,
                "timeout_buffer_seconds": 8,
            },
        )


if __name__ == "__main__":
    unittest.main()
