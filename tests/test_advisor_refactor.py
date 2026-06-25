import hashlib
import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from ai_advisor import AiAdvisor, AdvisorEvent


def sample_data(clock_time=65, radiant_score=1, dire_score=2):
    return {
        "map": {
            "clock_time": clock_time,
            "radiant_score": radiant_score,
            "dire_score": dire_score,
        },
        "player": {
            "team_name": "radiant",
            "kills": 3,
            "deaths": 1,
            "assists": 4,
            "last_hits": 20,
            "denies": 2,
            "gpm": 400,
            "xpm": 500,
            "gold": 1200,
        },
        "hero": {
            "name": "npc_dota_hero_lina",
            "level": 8,
            "health_percent": 75,
            "mana_percent": 60,
        },
        "items": {
            "slot0": {"name": "item_blink", "cooldown": 5},
        },
        "abilities": {
            "ability0": {
                "name": "lina_dragon_slave",
                "level": 4,
                "cooldown": 3,
            },
        },
        "minimap": {
            "self": {
                "image": "minimap_herocircle_self",
                "team": 2,
                "name": "npc_dota_hero_lina",
                "xpos": -1544,
                "ypos": -1408,
            },
            "enemy": {
                "image": "minimap_enemyicon",
                "team": 3,
                "name": "npc_dota_hero_axe",
                "xpos": 524,
                "ypos": 652,
            },
            "ward": {
                "unitname": "npc_dota_observer_wards",
                "team": 2,
                "xpos": -5080,
                "ypos": 1947,
            },
            "tower": {
                "image": "minimap_tower",
                "team": 2,
                "unitname": "npc_dota_goodguys_tower1_mid",
            },
        },
    }


class AiAdvisorGoldenTests(unittest.TestCase):
    def test_prompt_text_hash_is_stable(self):
        with tempfile.TemporaryDirectory() as log_dir:
            advisor = AiAdvisor(
                {
                    "enabled": True,
                    "system_prompt": "SYS",
                    "prompt_log_dir": log_dir,
                }
            )
            with redirect_stdout(io.StringIO()):
                advisor.set_role("2")
                advisor._accumulate_lineups(sample_data())
                message = advisor._build_user_message(sample_data())

        self.assertIn('"analysis"', message)
        self.assertIn('"command"', message)
        self.assertIn('"item"', message)
        self.assertIn('"speech_level"', message)
        self.assertIn('"brief"', message)
        self.assertIn('"full"', message)
        self.assertIn("当前时间: 1分5秒", message)

    def test_timer_and_score_triggers_keep_current_sequence(self):
        with tempfile.TemporaryDirectory() as log_dir:
            advisor = AiAdvisor(
                {
                    "enabled": True,
                    "interval_minutes": 1,
                    "system_prompt": "SYS",
                    "prompt_log_dir": log_dir,
                }
            )
            queries = []
            advisor._log_prompt = lambda message: None
            advisor._log_advice = lambda advice, game_time, analysis="": None
            advisor._call_api = lambda message: queries.append(message) or (
                "analysis",
                "command",
                "item",
                "full",
            )

            with redirect_stdout(io.StringIO()):
                before_warmup = advisor.update(sample_data(clock_time=59))
                timer_event = advisor.update(sample_data(clock_time=65))
                no_repeat = advisor.update(sample_data(clock_time=70))
                score_change = advisor.update(
                    sample_data(clock_time=80, radiant_score=2)
                )
                score_event = advisor.update(
                    sample_data(clock_time=85, radiant_score=2)
                )

        self.assertEqual(before_warmup, [])
        self.assertEqual(no_repeat, [])
        self.assertEqual(score_change, [])
        self.assertEqual(len(queries), 2)
        self.assertIsInstance(timer_event[0], AdvisorEvent)
        self.assertEqual(timer_event[0].advice_text, "command")
        self.assertEqual(timer_event[0].analysis_text, "analysis")
        self.assertEqual(timer_event[0].item_text, "item")
        self.assertEqual(timer_event[0].speech_level, "full")
        self.assertEqual(score_event[0].game_time, 85)

    def test_logging_schema_is_stable(self):
        with tempfile.TemporaryDirectory() as log_dir:
            advisor = AiAdvisor(
                {
                    "enabled": True,
                    "interval_minutes": 1,
                    "system_prompt": "SYS",
                    "prompt_log_dir": log_dir,
                }
            )
            advisor._last_bucket = 1
            with redirect_stdout(io.StringIO()):
                advisor._log_prompt("USER")
                advisor._log_advice("COMMAND", 65, "ANALYSIS")

            prompt_path = next(Path(log_dir).glob("ai_prompts_*.jsonl"))
            advice_path = next(Path(log_dir).glob("ai_advices_*.jsonl"))
            prompt_entry = json.loads(prompt_path.read_text(encoding="utf-8"))
            advice_entry = json.loads(advice_path.read_text(encoding="utf-8"))

        self.assertEqual(
            set(prompt_entry),
            {
                "game_time_minutes",
                "system_prompt_length",
                "user_message",
                "timestamp",
            },
        )
        self.assertEqual(prompt_entry["game_time_minutes"], 1)
        self.assertEqual(prompt_entry["user_message"], "USER")
        self.assertEqual(
            set(advice_entry),
            {"game_time", "analysis", "command", "timestamp"},
        )
        self.assertEqual(advice_entry["game_time"], "1:05")
        self.assertEqual(advice_entry["analysis"], "ANALYSIS")
        self.assertEqual(advice_entry["command"], "COMMAND")


class AdvisorComponentTests(unittest.TestCase):
    def test_client_preserves_json_and_fallback_parsing(self):
        from advisor.client import AdvisorClient

        class Completions:
            def __init__(self, contents):
                self.contents = iter(contents)
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                message = types.SimpleNamespace(
                    content=next(self.contents),
                    reasoning_content="",
                )
                return types.SimpleNamespace(
                    choices=[types.SimpleNamespace(message=message)]
                )

        completions = Completions(
            [
                '{"analysis":"局势","command":"推进","item":"黑皇杖","speech_level":"full"}',
                '{"analysis":"稳住","command":"带线","item":"","speech_level":"loud"}',
                '{"analysis":"默认","command":"控盾","item":""}',
                '{"analysis":"只分析","command":"","speech_level":"full"}',
                "plain text",
            ]
        )
        fake_client = types.SimpleNamespace(
            chat=types.SimpleNamespace(completions=completions)
        )
        fake_openai = types.SimpleNamespace(OpenAI=lambda **kwargs: fake_client)
        client = AdvisorClient(
            api_key="key",
            base_url="https://example.test",
            model="model",
            max_tokens=500,
            temperature=0.2,
        )

        with (
            patch.dict(sys.modules, {"openai": fake_openai}),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(
                client.complete("SYS", "USER"),
                ("局势", "推进", "黑皇杖", "full"),
            )
            self.assertEqual(
                client.complete("SYS", "USER"),
                ("稳住", "带线", "", "brief"),
            )
            self.assertEqual(
                client.complete("SYS", "USER"),
                ("默认", "控盾", "", "brief"),
            )
            self.assertEqual(
                client.complete("SYS", "USER"),
                ("", "只分析", "", "brief"),
            )
            self.assertEqual(
                client.complete("SYS", "USER"),
                ("", "plain text", "", "brief"),
            )

        self.assertEqual(
            completions.calls[0],
            {
                "model": "model",
                "messages": [
                    {"role": "system", "content": "SYS"},
                    {"role": "user", "content": "USER"},
                ],
                "max_tokens": 500,
                "temperature": 0.2,
                "extra_body": {"thinking": {"type": "disabled"}},
            },
        )

    def test_logger_preserves_jsonl_schema(self):
        from advisor.logging import AdvisorLogger

        with tempfile.TemporaryDirectory() as log_dir:
            logger = AdvisorLogger(log_dir)
            with redirect_stdout(io.StringIO()):
                logger.log_prompt(
                    user_message="USER",
                    system_prompt="SYS",
                    game_time_minutes=1,
                    history_section="",
                )
                logger.log_advice("COMMAND", 65, "ANALYSIS")
            prompt_path = next(Path(log_dir).glob("ai_prompts_*.jsonl"))
            advice_path = next(Path(log_dir).glob("ai_advices_*.jsonl"))
            prompt_entry = json.loads(prompt_path.read_text(encoding="utf-8"))
            advice_entry = json.loads(advice_path.read_text(encoding="utf-8"))

        self.assertEqual(prompt_entry["user_message"], "USER")
        self.assertEqual(prompt_entry["system_prompt_length"], 3)
        self.assertEqual(advice_entry["game_time"], "1:05")
        self.assertEqual(advice_entry["command"], "COMMAND")

    def test_extractor_preserves_state_text_and_lineups(self):
        from advisor.extractor import StateExtractor

        extractor = StateExtractor()
        data = sample_data()
        with redirect_stdout(io.StringIO()):
            extractor.accumulate_lineups(data)

        self.assertEqual(extractor.team_lineups["radiant"], ["莉娜"])
        self.assertEqual(extractor.team_lineups["dire"], ["斧王"])
        self.assertEqual(
            extractor.nearest_landmark(-1544, -1408),
            "天辉中路一塔",
        )
        positions = extractor.extract_hero_positions(data)
        wards = extractor.extract_ward_info(data)
        player = extractor.build_player_state(data)

        self.assertIn("【我】莉娜(-1544,-1408)→天辉中路一塔", positions)
        self.assertIn("斧王(524,652)→夜魇中路一塔", positions)
        self.assertIn("天辉视野: 假眼(1)", wards)
        self.assertIn("装备: blink(cd:5s)", player)
        self.assertIn("技能: dragon_slave:lv4(cd:3s)", player)

    def test_prompt_builder_preserves_golden_message_and_history(self):
        from advisor.extractor import StateExtractor
        from advisor.prompt import PromptBuilder

        extractor = StateExtractor()
        data = sample_data()
        extractor.accumulate_lineups(data)
        prompt = PromptBuilder(
            {
                "system_prompt": "SYS",
                "system_prompt_file": "",
            },
            extractor,
        )
        with redirect_stdout(io.StringIO()):
            prompt.set_role("2")
        message = prompt.build_user_message(data, recently_killed={})

        self.assertEqual(prompt.system_prompt, "SYS")
        self.assertIn('"analysis"', message)
        self.assertIn('"command"', message)
        self.assertIn('"item"', message)
        self.assertIn('"speech_level"', message)
        self.assertIn('"brief"', message)
        self.assertIn('"full"', message)
        self.assertIn("当前时间: 1分5秒", message)

        prompt.record_advice(65, "推进", "局势")
        self.assertEqual(prompt.last_analysis, "局势")
        self.assertEqual(prompt.build_history_section(), "\n之前的建议:\n- (1分5秒) 推进\n")

    def test_trigger_controller_preserves_timer_score_and_cooldown(self):
        from advisor.extractor import StateExtractor
        from advisor.trigger import TriggerController

        trigger = TriggerController(interval_minutes=1, extractor=StateExtractor())
        with redirect_stdout(io.StringIO()):
            warmup = trigger.evaluate(sample_data(clock_time=59))
            timer = trigger.evaluate(sample_data(clock_time=65))
            trigger.complete(sample_data(clock_time=65), succeeded=True)
            repeated = trigger.evaluate(sample_data(clock_time=70))
            changed = trigger.evaluate(
                sample_data(clock_time=80, radiant_score=2)
            )
            delayed = trigger.evaluate(
                sample_data(clock_time=84, radiant_score=2)
            )
            score = trigger.evaluate(
                sample_data(clock_time=85, radiant_score=2)
            )
            trigger.complete(
                sample_data(clock_time=85, radiant_score=2),
                succeeded=True,
            )
            cooldown_change = trigger.evaluate(
                sample_data(clock_time=90, radiant_score=3)
            )
            cooldown_skip = trigger.evaluate(
                sample_data(clock_time=95, radiant_score=3)
            )

        self.assertFalse(warmup.should_query)
        self.assertTrue(timer.should_query)
        self.assertEqual(timer.clock_time, 65)
        self.assertFalse(repeated.should_query)
        self.assertFalse(changed.should_query)
        self.assertFalse(delayed.should_query)
        self.assertTrue(score.should_query)
        self.assertFalse(cooldown_change.should_query)
        self.assertFalse(cooldown_skip.should_query)
        self.assertEqual(trigger.last_query_time, 85)


if __name__ == "__main__":
    unittest.main()
