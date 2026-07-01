import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from ai_advisor import AdvisorEvent
from gsi_handler import GSIHandler


class FakeAiWorker:
    def __init__(self):
        self.calls = []

    def submit(self, data):
        self.calls.append(("submit", data["map"]["clock_time"]))

    def reset(self):
        self.calls.append(("reset", None))

    def set_role(self, role):
        self.calls.append(("role", role))


class FakeRoleSelector:
    def __init__(self, result=None):
        self.result = result
        self.requests = 0

    def request_selection(self):
        self.requests += 1

    def poll_result(self):
        result = self.result
        self.result = None
        return result


class GSIHandlerAsyncTests(unittest.TestCase):
    def test_new_session_uses_async_services(self):
        ai_worker = FakeAiWorker()
        role_selector = FakeRoleSelector(result="2")
        with tempfile.TemporaryDirectory() as log_dir:
            handler = GSIHandler(
                {
                    "logging": {"log_dir": log_dir},
                    "vision": {"enabled": False},
                    "ai_advisor": {"enabled": True},
                },
                ai_worker=ai_worker,
                role_selector=role_selector,
            )
            payload = {
                "map": {
                    "clock_time": 1,
                    "game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
                },
                "hero": {"alive": True},
            }
            with redirect_stdout(io.StringIO()):
                handler.handle(json.dumps(payload).encode("utf-8"))
        self.assertEqual(role_selector.requests, 1)
        self.assertEqual(
            ai_worker.calls,
            [("reset", None), ("role", "2"), ("submit", 1)],
        )


def make_event(level):
    return AdvisorEvent(
        advice_text="控盾逼团",
        analysis_text="我方团战更强，应主动控制肉山区域。",
        fight_text="后排边缘输出，等先手后进场",
        item_text="黑皇杖",
        game_time=900,
        timestamp="2026-06-25T00:00:00",
        speech_level=level,
    )


class GSIHandlerAdvisorSpeechTests(unittest.TestCase):
    def test_brief_excludes_analysis(self):
        with tempfile.TemporaryDirectory() as log_dir:
            handler = GSIHandler(
                {
                    "logging": {"log_dir": log_dir},
                    "vision": {"enabled": False},
                    "ai_advisor": {"enabled": False},
                }
            )
            with (
                patch("gsi_handler.configure_speech") as mock_configure,
                patch("gsi_handler.speak") as mock_speak,
            ):
                handler._on_advisor_event(make_event("brief"))
            mock_speak.assert_called_once()
            text = mock_speak.call_args[0][0]
            self.assertIn("控盾逼团", text)
            self.assertIn("团战思路：后排边缘输出，等先手后进场", text)
            self.assertIn("出装建议：黑皇杖", text)
            self.assertNotIn("战略分析", text)
            self.assertLess(
                text.index("团战思路"),
                text.index("出装建议"),
            )
            self.assertEqual(mock_speak.call_args[1]["category"], "advisor")

    def test_full_includes_all_sections(self):
        with tempfile.TemporaryDirectory() as log_dir:
            handler = GSIHandler(
                {
                    "logging": {"log_dir": log_dir},
                    "vision": {"enabled": False},
                    "ai_advisor": {"enabled": False},
                }
            )
            with (
                patch("gsi_handler.configure_speech") as mock_configure,
                patch("gsi_handler.speak") as mock_speak,
            ):
                handler._on_advisor_event(make_event("full"))
            mock_speak.assert_called_once()
            text = mock_speak.call_args[0][0]
            self.assertIn("战略分析", text)
            self.assertIn("战术指令", text)
            self.assertIn("团战思路", text)
            self.assertIn("出装建议", text)
            self.assertLess(
                text.index("团战思路"),
                text.index("出装建议"),
            )
            self.assertLess(
                text.index("出装建议"),
                text.index("战略分析"),
            )
            self.assertEqual(mock_speak.call_args[1]["category"], "advisor")

    def test_configure_speech_receives_tts_config(self):
        with tempfile.TemporaryDirectory() as log_dir:
            tts_cfg = {
                "rate": 4,
                "full_max_seconds": 25,
                "estimated_chars_per_second": 7,
                "timeout_buffer_seconds": 8,
            }
            with patch("gsi_handler.configure_speech") as mock_configure:
                GSIHandler(
                    {
                        "logging": {"log_dir": log_dir},
                        "vision": {"enabled": False},
                        "ai_advisor": {"enabled": False},
                        "tts": tts_cfg,
                    }
                )
            mock_configure.assert_called_once_with(tts_cfg)

    def test_new_session_clears_pending_advisor(self):
        with tempfile.TemporaryDirectory() as log_dir:
            handler = GSIHandler(
                {
                    "logging": {"log_dir": log_dir},
                    "vision": {"enabled": False},
                    "ai_advisor": {"enabled": False},
                }
            )
            payload = {
                "map": {
                    "clock_time": 1,
                    "game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
                },
                "hero": {"alive": True},
            }
            with (
                patch("gsi_handler.clear_pending_speech") as mock_clear,
                redirect_stdout(io.StringIO()),
            ):
                handler.handle(json.dumps(payload).encode("utf-8"))
            mock_clear.assert_called_once_with("advisor")


if __name__ == "__main__":
    unittest.main()
