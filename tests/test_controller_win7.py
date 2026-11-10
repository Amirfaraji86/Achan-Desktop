import unittest
from unittest.mock import patch

from core import controller_win7 as module
from core.controller_win7 import Win7NetworkController


class FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class Win7CleanupTests(unittest.TestCase):
    def test_cleanup_matches_numbered_wintun_alias(self):
        messages = []
        controller = Win7NetworkController(None, messages.append)
        controller._tunnel_attempted = True
        with patch.object(module.sys, "platform", "win32"), patch.object(
            module.subprocess, "run", return_value=FakeResult()
        ) as run:
            self.assertTrue(controller._reset_wintun_dns())
        command = run.call_args.args[0][-1]
        self.assertIn("^wintun(?:\\s+\\d+)?$", command)
        self.assertFalse(controller._tunnel_attempted)

    def test_cleanup_failure_keeps_retry_flag(self):
        controller = Win7NetworkController(None, lambda _message: None)
        controller._tunnel_attempted = True
        with patch.object(module.sys, "platform", "win32"), patch.object(
            module.subprocess, "run", return_value=FakeResult(1, stderr="WMI failed")
        ):
            self.assertFalse(controller._reset_wintun_dns())
        self.assertTrue(controller._tunnel_attempted)


if __name__ == "__main__":
    unittest.main()
