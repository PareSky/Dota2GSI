import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from speech_policy import SpeechSettings
from tts import SpeechQueue, SpeechRequest, speak, configure_speech, clear_pending_speech


class SpeechQueueUnitTests(unittest.TestCase):
    def test_queue_preserves_request_objects(self):
        speech = SpeechQueue(SpeechSettings())
        speech.say("资源提醒", category="alert")
        speech.say("旧局分析", category="advisor")
        speech.say("夜晚降临", category="alert")
        speech.clear_pending("advisor")
        self.assertEqual(
            [(r.text, r.category) for r in speech.pending_requests()],
            [("资源提醒", "alert"), ("夜晚降临", "alert")],
        )

    def test_clear_without_category_removes_all(self):
        speech = SpeechQueue(SpeechSettings())
        speech.say("A", category="alert")
        speech.say("B", category="advisor")
        speech.clear_pending()
        self.assertEqual(speech.pending_requests(), [])

    def test_pending_returns_shallow_copy(self):
        speech = SpeechQueue(SpeechSettings())
        speech.say("测试", category="alert")
        requests = speech.pending_requests()
        self.assertEqual(len(requests), 1)
        self.assertEqual(speech.pending_requests()[0].text, "测试")


class SpeechQueueProcessTests(unittest.TestCase):
    def test_rate_and_timeout_reflect_settings(self):
        settings = SpeechSettings(
            rate=4,
            estimated_chars_per_second=5,
            timeout_buffer_seconds=8,
        )
        speech = SpeechQueue(settings)
        with (
            patch("tts.resource_path", return_value="speak.ps1"),
            patch("tts.subprocess.run") as run,
        ):
            speech._run_request("一" * 100)
        args, kwargs = run.call_args
        self.assertEqual(args[0][-2:], ["-rate", "4"])
        self.assertEqual(kwargs["timeout"], 28)

    def test_dynamic_timeout_floor_is_five(self):
        settings = SpeechSettings(
            rate=4,
            estimated_chars_per_second=1000,
            timeout_buffer_seconds=8,
        )
        speech = SpeechQueue(settings)
        with (
            patch("tts.resource_path", return_value="speak.ps1"),
            patch("tts.subprocess.run") as run,
        ):
            speech._run_request("短")
        self.assertGreaterEqual(run.call_args[1]["timeout"], 5.0)


class SpeechRequestContractTests(unittest.TestCase):
    def test_request_is_immutable_and_has_default_category(self):
        req = SpeechRequest("text")
        self.assertEqual(req.text, "text")
        self.assertEqual(req.category, "alert")


class SpeakPs1RateTests(unittest.TestCase):
    def test_ps1_accepts_rate_parameter(self):
        ps1_path = SRC_DIR / "speak.ps1"
        content = ps1_path.read_text(encoding="utf-8")
        self.assertIn("[int]$rate", content)
        self.assertIn("$voice.Rate = $rate", content)


if __name__ == "__main__":
    unittest.main()
