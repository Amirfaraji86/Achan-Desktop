import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.update_client import UpdateClient, UpdateError, UpdateInfo, parse_version


class FakeResponse:
    def __init__(self, payload=None, content=b"", url=""):
        self.payload = payload
        self.content = content
        self.url = url

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload

    def iter_content(self, chunk_size=1024):
        for start in range(0, len(self.content), chunk_size):
            yield self.content[start:start + chunk_size]


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("No fake response left for URL: {}".format(url))
        return self.responses.pop(0)


class UpdateClientTests(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version("1.2.30"), (1, 2, 30))
        with self.assertRaises(UpdateError):
            parse_version("v1.2.3")
        with self.assertRaises(UpdateError):
            parse_version("1.2")

    def test_platform_selection(self):
        self.assertEqual(
            UpdateClient.platform_for_windows(6, 1),
            ("windows-7-sp1-x64", "-win7", "Achan-Update-Windows-7-SP1.json"),
        )
        self.assertEqual(
            UpdateClient.platform_for_windows(10, 0),
            ("windows-10-11-x64", "-win10-11", "Achan-Update-Windows-10-11.json"),
        )
        with self.assertRaises(UpdateError):
            UpdateClient.platform_for_windows(6, 2)

    def test_find_matching_release_and_verify_manifest(self):
        installer = b"fake installer bytes"
        digest = hashlib.sha256(installer).hexdigest()
        base = "https://github.com/Amirfaraji86/Achan-Desktop/releases/download/v1.1.0-win10-11/"
        releases = [{
            "tag_name": "v1.1.0-win10-11",
            "draft": False,
            "prerelease": False,
            "body": "Notes",
            "assets": [
                {"name": "Achan-Update-Windows-10-11.json", "browser_download_url": base + "Achan-Update-Windows-10-11.json", "size": 100},
                {"name": "Achan-Setup-Windows-10-11-x64.exe", "browser_download_url": base + "Achan-Setup-Windows-10-11-x64.exe", "size": len(installer)},
            ],
        }]
        manifest = {
            "schema_version": 1,
            "app_id": "achan-desktop",
            "version": "1.1.0",
            "tag": "v1.1.0-win10-11",
            "platform": "windows-10-11-x64",
            "installer": "Achan-Setup-Windows-10-11-x64.exe",
            "sha256": digest,
            "size_bytes": len(installer),
            "release_notes": "Notes",
        }
        session = FakeSession([FakeResponse(releases), FakeResponse(manifest)])
        client = UpdateClient(session=session)
        info = client.check_for_update("1.0.3", (10, 0))
        self.assertIsNotNone(info)
        self.assertEqual(info.version, "1.1.0")
        self.assertEqual(info.sha256, digest)

    def test_rejects_wrong_manifest_identity(self):
        base = "https://github.com/Amirfaraji86/Achan-Desktop/releases/download/v1.1.0-win7/"
        releases = [{
            "tag_name": "v1.1.0-win7",
            "draft": False,
            "prerelease": False,
            "assets": [
                {"name": "Achan-Update-Windows-7-SP1.json", "browser_download_url": base + "Achan-Update-Windows-7-SP1.json", "size": 100},
            ],
        }]
        session = FakeSession([FakeResponse(releases), FakeResponse({"schema_version": 1, "app_id": "other"})])
        client = UpdateClient(session=session)
        with self.assertRaises(UpdateError):
            client.check_for_update("1.0.3", (6, 1))


    def test_rejects_unexpected_installer_filename(self):
        installer = b"fake installer bytes"
        digest = hashlib.sha256(installer).hexdigest()
        base = "https://github.com/Amirfaraji86/Achan-Desktop/releases/download/v1.1.0-win10-11/"
        releases = [{
            "tag_name": "v1.1.0-win10-11",
            "draft": False,
            "prerelease": False,
            "assets": [
                {"name": "Achan-Update-Windows-10-11.json", "browser_download_url": base + "Achan-Update-Windows-10-11.json", "size": 100},
                {"name": "Achan-Setup-Windows-10-11-x64.exe", "browser_download_url": base + "Achan-Setup-Windows-10-11-x64.exe", "size": len(installer)},
            ],
        }]
        manifest = {
            "schema_version": 1,
            "app_id": "achan-desktop",
            "version": "1.1.0",
            "tag": "v1.1.0-win10-11",
            "platform": "windows-10-11-x64",
            "installer": "../payload.exe",
            "sha256": digest,
            "size_bytes": len(installer),
        }
        session = FakeSession([FakeResponse(releases), FakeResponse(manifest)])
        client = UpdateClient(session=session)
        with self.assertRaises(UpdateError):
            client.check_for_update("1.0.3", (10, 0))

    def test_download_checks_size_and_sha256(self):
        payload = b"Achan test installer"
        digest = hashlib.sha256(payload).hexdigest()
        info = UpdateInfo(
            version="1.1.0",
            tag="v1.1.0-win10-11",
            platform="windows-10-11-x64",
            installer_name="Achan-Setup-Windows-10-11-x64.exe",
            installer_url="https://github.com/Amirfaraji86/Achan-Desktop/releases/download/v1.1.0-win10-11/Achan-Setup-Windows-10-11-x64.exe",
            sha256=digest,
            size_bytes=len(payload),
            release_notes="",
        )
        with TemporaryDirectory() as tmp:
            client = UpdateClient(session=FakeSession([FakeResponse(content=payload, url=info.installer_url)]))
            saved = client.download_installer(info, Path(tmp))
            self.assertEqual(saved.read_bytes(), payload)

    def test_download_rejects_untrusted_url_before_network_request(self):
        info = UpdateInfo(
            version="1.1.0",
            tag="v1.1.0-win10-11",
            platform="windows-10-11-x64",
            installer_name="Achan-Setup-Windows-10-11-x64.exe",
            installer_url="https://attacker.example/payload.exe",
            sha256="0" * 64,
            size_bytes=10,
            release_notes="",
        )
        session = FakeSession([])
        with TemporaryDirectory() as tmp:
            client = UpdateClient(session=session)
            with self.assertRaises(UpdateError):
                client.download_installer(info, Path(tmp))
        self.assertEqual(session.calls, [])

    def test_download_rejects_inconsistent_tag_before_network_request(self):
        info = UpdateInfo(
            version="1.1.0",
            tag="v1.1.0-win7",
            platform="windows-10-11-x64",
            installer_name="Achan-Setup-Windows-10-11-x64.exe",
            installer_url=("https://github.com/Amirfaraji86/Achan-Desktop/releases/download/"
                           "v1.1.0-win10-11/Achan-Setup-Windows-10-11-x64.exe"),
            sha256="0" * 64,
            size_bytes=10,
            release_notes="",
        )
        session = FakeSession([])
        with TemporaryDirectory() as tmp:
            client = UpdateClient(session=session)
            with self.assertRaises(UpdateError):
                client.download_installer(info, Path(tmp))
        self.assertEqual(session.calls, [])

    def test_download_rejects_hash_mismatch_and_removes_partial_file(self):
        payload = b"tampered"
        info = UpdateInfo(
            version="1.1.0",
            tag="v1.1.0-win10-11",
            platform="windows-10-11-x64",
            installer_name="Achan-Setup-Windows-10-11-x64.exe",
            installer_url="https://github.com/Amirfaraji86/Achan-Desktop/releases/download/v1.1.0-win10-11/Achan-Setup-Windows-10-11-x64.exe",
            sha256="0" * 64,
            size_bytes=len(payload),
            release_notes="",
        )
        with TemporaryDirectory() as tmp:
            client = UpdateClient(session=FakeSession([FakeResponse(content=payload, url=info.installer_url)]))
            with self.assertRaises(UpdateError):
                client.download_installer(info, Path(tmp))
            self.assertFalse((Path(tmp) / info.installer_name).exists())
            self.assertFalse((Path(tmp) / (info.installer_name + ".part")).exists())


if __name__ == "__main__":
    unittest.main()
