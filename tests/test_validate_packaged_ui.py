import tempfile
import unittest
from pathlib import Path

from tools.validate_packaged_ui import validate_packaged_ui


VALID_QML = b'''component BottomNavItem: Rectangle {
    LayoutMirroring.enabled: bridge.language === "fa"
    Canvas {
        id: powerGlow
        visible: bridge.isConnected
    }
}
'''


class ValidatePackagedUiTests(unittest.TestCase):
    def create_bundle(self, root, internal=True, qml=VALID_QML):
        app = root / "app"
        app.mkdir()
        (app / "Achan.exe").write_bytes(b"frozen app")
        resource_root = app / "_internal" if internal else app
        qml_path = resource_root / "qt_ui" / "main.qml"
        qml_path.parent.mkdir(parents=True)
        qml_path.write_bytes(qml)
        source = root / "main.qml"
        source.write_bytes(VALID_QML)
        return source, app

    def test_matching_pyinstaller_internal_qml_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, app = self.create_bundle(Path(temporary))
            packaged, digest = validate_packaged_ui(source, app, "qt_ui/main.qml")
            self.assertTrue(packaged.samefile(app / "_internal" / "qt_ui" / "main.qml"))
            self.assertEqual(len(digest), 64)

    def test_older_application_root_layout_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, app = self.create_bundle(Path(temporary), internal=False)
            packaged, _ = validate_packaged_ui(source, app, "qt_ui/main.qml")
            self.assertTrue(packaged.samefile(app / "qt_ui" / "main.qml"))

    def test_stale_packaged_qml_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, app = self.create_bundle(Path(temporary), qml=b"old QML")
            with self.assertRaisesRegex(ValueError, "does not match"):
                validate_packaged_ui(source, app, "qt_ui/main.qml")

    def test_disconnected_halo_configuration_fails(self):
        old_halo = VALID_QML.replace(b"visible: bridge.isConnected", b"visible: true")
        with tempfile.TemporaryDirectory() as temporary:
            source, app = self.create_bundle(Path(temporary), qml=old_halo)
            source.write_bytes(old_halo)
            with self.assertRaisesRegex(ValueError, "only be visible"):
                validate_packaged_ui(source, app, "qt_ui/main.qml")


if __name__ == "__main__":
    unittest.main()
