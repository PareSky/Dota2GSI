import sys
import threading
import time
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))


class AsyncAiAdvisorTests(unittest.TestCase):
    def test_submit_does_not_wait_for_advisor(self):
        from ai_worker import AiAdvisorWorker

        started = threading.Event()
        release = threading.Event()
        received = []

        class BlockingAdvisor:
            def update(self, data):
                started.set()
                release.wait(timeout=2)
                return [data["event"]]

            def set_role(self, role):
                pass

            def reset(self):
                pass

        worker = AiAdvisorWorker(advisor=BlockingAdvisor(), on_event=received.append)
        self.addCleanup(worker.stop)
        before = time.perf_counter()
        worker.submit({"event": "advice"})
        elapsed = time.perf_counter() - before
        self.assertLess(elapsed, 0.1)
        self.assertTrue(started.wait(timeout=1))
        release.set()
        deadline = time.time() + 1
        while not received and time.time() < deadline:
            time.sleep(0.01)
        self.assertEqual(received, ["advice"])

    def test_role_and_reset_run_on_worker_thread(self):
        from ai_worker import AiAdvisorWorker

        calls = []
        called = threading.Event()

        class RecordingAdvisor:
            def update(self, data):
                return []

            def set_role(self, role):
                calls.append(("role", role, threading.current_thread().name))
                called.set()

            def reset(self):
                calls.append(("reset", None, threading.current_thread().name))
                called.set()

        worker = AiAdvisorWorker(advisor=RecordingAdvisor(), on_event=lambda event: None)
        self.addCleanup(worker.stop)
        worker.set_role("3")
        self.assertTrue(called.wait(timeout=1))
        self.assertEqual(calls[0][:2], ("role", "3"))
        self.assertNotEqual(calls[0][2], threading.current_thread().name)

    def test_reset_discards_in_flight_advice_from_previous_session(self):
        from ai_worker import AiAdvisorWorker

        started = threading.Event()
        release = threading.Event()
        received = []

        class BlockingAdvisor:
            def update(self, data):
                started.set()
                release.wait(timeout=2)
                return ["stale advice"]

            def set_role(self, role):
                pass

            def reset(self):
                pass

        worker = AiAdvisorWorker(advisor=BlockingAdvisor(), on_event=received.append)
        self.addCleanup(worker.stop)
        worker.submit({"frame": "old session"})
        self.assertTrue(started.wait(timeout=1))
        worker.reset()
        release.set()
        time.sleep(0.05)
        self.assertEqual(received, [])


class RoleSelectorTests(unittest.TestCase):
    def test_request_selection_returns_without_waiting_for_dialog(self):
        from role_selector import RoleSelector

        started = threading.Event()
        release = threading.Event()

        class FakeProcess:
            daemon = False

            def start(self):
                started.set()

            def is_alive(self):
                return not release.is_set()

        selector = RoleSelector(process_factory=lambda target, args: FakeProcess())
        before = time.perf_counter()
        selector.request_selection()
        elapsed = time.perf_counter() - before
        self.assertLess(elapsed, 0.1)
        self.assertTrue(started.is_set())


if __name__ == "__main__":
    unittest.main()
