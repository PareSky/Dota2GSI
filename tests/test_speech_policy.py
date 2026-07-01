import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from speech_policy import (SpeechSettings, compose_advisor_speech,
                           _trim_at_boundary)


class SpeechSettingsTests(unittest.TestCase):
    def test_invalid_values_fall_back_and_rate_is_clamped(self):
        settings = SpeechSettings.from_config(
            {
                "rate": 99,
                "full_max_seconds": 0,
                "estimated_chars_per_second": -1,
                "timeout_buffer_seconds": -3,
            }
        )
        self.assertEqual(settings.rate, 10)
        self.assertEqual(settings.full_max_seconds, 25)
        self.assertEqual(settings.estimated_chars_per_second, 7)
        self.assertEqual(settings.timeout_buffer_seconds, 8)


class SpeechCompositionTests(unittest.TestCase):
    def test_brief_omits_analysis(self):
        text = compose_advisor_speech(
            "战略分析",
            "立刻推塔",
            "后排边缘输出",
            "黑皇杖",
            "brief",
            SpeechSettings(),
        )
        self.assertEqual(
            text,
            "立刻推塔。团战思路：后排边缘输出。出装建议：黑皇杖",
        )

    def test_full_includes_all_sections(self):
        text = compose_advisor_speech(
            "我方团战更强。",
            "控盾逼团",
            "等先手后再进场",
            "黑皇杖",
            "full",
            SpeechSettings(),
        )
        self.assertEqual(
            text,
            "战略分析：我方团战更强。战术指令：控盾逼团。团战思路：等先手后再进场。出装建议：黑皇杖",
        )

    def test_invalid_level_downgrades_to_brief(self):
        text = compose_advisor_speech(
            "分析", "撤退", "", "", "unexpected", SpeechSettings()
        )
        self.assertEqual(text, "撤退")


class SpeechTrimTests(unittest.TestCase):
    def test_trim_preserves_command_and_item_under_budget(self):
        settings = SpeechSettings(
            estimated_chars_per_second=10,
            full_max_seconds=6,
        )
        text = compose_advisor_speech(
            "我方优势明显，应该继续推进。敌方核心尚未成型，此时是最佳进攻窗口。",
            "推上路二塔",
            "后排边缘输出",
            "黑皇杖",
            "full",
            settings,
        )
        self.assertIn("战略分析：", text)
        self.assertIn("战术指令：推上路二塔", text)
        self.assertIn("团战思路：后排边缘输出", text)
        self.assertIn("出装建议：黑皇杖", text)
        self.assertTrue(text.endswith("出装建议：黑皇杖"))

    def test_tiny_budget_still_preserves_command_and_item(self):
        settings = SpeechSettings(
            estimated_chars_per_second=1,
            full_max_seconds=1,
        )
        text = compose_advisor_speech(
            "十个字的分析文本占掉大量预算。",
            "推塔",
            "靠后打",
            "出装",
            "full",
            settings,
        )
        self.assertIn("推塔", text)
        self.assertIn("靠后打", text)
        self.assertIn("出装", text)


if __name__ == "__main__":
    unittest.main()
