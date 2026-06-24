import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

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


if __name__ == "__main__":
    unittest.main()
