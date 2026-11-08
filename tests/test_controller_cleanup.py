import unittest
from unittest.mock import patch

from core import controller as controller_module
from core.controller import NetworkController


class FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class NetworkCleanupTests(unittest.TestCase):
    def make_controller(self):
        messages = []
        controller = NetworkController(None, messages.append)
        controller._tunnel_attempted = True
        return controller, messages

    def test_wintun_dns_cleanup_failure_is_not_reported_as_clean(self):
        controller, messages = self.make_controller()
        with patch.object(controller_module.sys, "platform", "win32"), \
             patch.object(controller_module.subprocess, "run", return_value=FakeResult(1, stderr="WMI failed")):
            clean = controller.stop()
        self.assertFalse(clean)
        self.assertTrue(controller._tunnel_attempted)
        self.assertIn("Wintun DNS reset warning", "\n".join(messages))

    def test_wintun_dns_cleanup_success_clears_pending_flag(self):
        controller, messages = self.make_controller()
        with patch.object(controller_module.sys, "platform", "win32"), \
             patch.object(controller_module.subprocess, "run", return_value=FakeResult(0)):
            clean = controller.stop()
        self.assertTrue(clean)
        self.assertFalse(controller._tunnel_attempted)
        self.assertIn("Temporary Wintun DNS setting cleared", "\n".join(messages))


if __name__ == "__main__":
    unittest.main()
