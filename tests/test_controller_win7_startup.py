import io
import unittest

from core.controller_win7 import Win7NetworkController


class FakeProcess:
    def __init__(self, output):
        self.stdout = io.StringIO(output)


class Win7StartupHandshakeTests(unittest.TestCase):
    def make_controller(self):
        stages = []
        messages = []
        controller = Win7NetworkController(None, messages.append, lambda *args: stages.append(args))
        return controller, stages, messages

    def test_startup_banner_marks_engine_ready(self):
        controller, _stages, _messages = self.make_controller()
        controller._read_process_output(FakeProcess("tun2proxy 0.8.7 starting...\n"))
        self.assertTrue(controller._engine_ready.is_set())

    def test_ready_stage_is_held_until_startup_banner(self):
        controller, stages, _messages = self.make_controller()
        controller._set_stage("tunnel", "ready", "active")
        self.assertEqual(stages[-1][1], "checking")
        controller._engine_ready.set()
        controller._set_stage("tunnel", "ready", "active")
        self.assertEqual(stages[-1][1], "ready")

    def test_engine_error_is_recorded(self):
        controller, _stages, _messages = self.make_controller()
        controller._read_process_output(FakeProcess("main loop error: Element not found\n"))
        self.assertEqual(controller._engine_error, "main loop error: Element not found")


if __name__ == "__main__":
    unittest.main()
