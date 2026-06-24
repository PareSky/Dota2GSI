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
from vision_tracker import VisionTracker


def minimap_frame(enemy_visible: bool):
    frame = {
        "self": {
            "image": "minimap_herocircle_self",
            "team": 2,
            "name": "npc_dota_hero_lina",
        },
    }
    if enemy_visible:
        frame["enemy"] = {
            "image": "minimap_enemyicon",
            "team": 3,
            "name": "npc_dota_hero_axe",
            "xpos": 100,
            "ypos": 200,
        }
    return frame


class VisionTrackerStateTests(unittest.TestCase):
    def test_enemy_returning_during_leave_delay_does_not_enter_again(self):
        tracker = VisionTracker()
        first = tracker.update(minimap_frame(True), "radiant", 10)
        tracker.update(minimap_frame(False), "radiant", 11)
        returned = tracker.update(minimap_frame(True), "radiant", 12)
        self.assertEqual([event.event_type for event in first], ["ENTERED"])
        self.assertEqual(returned, [])


class GameTimerStateTests(unittest.TestCase):
    def test_dead_player_does_not_consume_timer_notification(self):
        with tempfile.TemporaryDirectory() as log_dir:
            handler = GSIHandler(
                {
                    "logging": {"log_dir": log_dir},
                    "vision": {"enabled": False},
                    "ai_advisor": {"enabled": False},
                }
            )
            events = []
            handler._on_timer_event = events.append
            dead_frame = {"map": {"clock_time": 105}, "hero": {"alive": False}}
            alive_frame = {"map": {"clock_time": 110}, "hero": {"alive": True}}
            with redirect_stdout(io.StringIO()):
                handler.handle(json.dumps(dead_frame).encode("utf-8"))
                handler.handle(json.dumps(alive_frame).encode("utf-8"))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].spawn_time, 120.0)


if __name__ == "__main__":
    unittest.main()
