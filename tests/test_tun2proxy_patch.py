import tempfile
import unittest
from pathlib import Path

from tools.patch_tun2proxy_win7 import NEW_SNIPPET, OLD_SNIPPET, patch_windows_source


class Tun2ProxyPatchTests(unittest.TestCase):
    def test_removes_literal_quotes_from_netsh_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "windows.rs"
            source.write_text("before\n" + OLD_SNIPPET + "\nafter\n", encoding="utf-8")
            self.assertTrue(patch_windows_source(source))
            text = source.read_text(encoding="utf-8")
            self.assertIn(NEW_SNIPPET, text)
            self.assertNotIn(OLD_SNIPPET, text)

    def test_patch_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "windows.rs"
            source.write_text(NEW_SNIPPET + "\n", encoding="utf-8")
            self.assertFalse(patch_windows_source(source))


if __name__ == "__main__":
    unittest.main()
