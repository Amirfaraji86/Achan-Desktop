"""Headless startup and teardown smoke test for Achan's Qt Quick interface."""
from __future__ import annotations

import sys
from pathlib import Path

# Running `python tools\validate_qml.py` puts tools/ rather than the project
# root at sys.path[0]. Add the project root before importing the app bridge.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QTimer,
    QUrl,
    qInstallMessageHandler,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from main_qt import AchanBridge, SingleInstance


def main() -> int:
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication([sys.argv[0]])
    app.setApplicationName("Achan-QML-SmokeTest")
    app.setQuitOnLastWindowClosed(False)

    errors: list[str] = []
    fatal_markers = (
        "TypeError:",
        "ReferenceError:",
        "is not a function",
        "Cannot assign to non-existent property",
        "Unable to assign",
    )

    # QQmlEngine.warnings handles QML-engine diagnostics; installing a Qt
    # message handler also captures runtime binding errors emitted by Qt.
    def qt_message_handler(_kind, _context, message: str) -> None:
        rendered = str(message)
        if any(marker in rendered for marker in fatal_markers):
            errors.append(rendered)

    qInstallMessageHandler(qt_message_handler)

    engine = QQmlApplicationEngine()
    bridge = AchanBridge(SingleInstance(enabled=False), demo=True)
    # Keep the bridge alive through root-object/context destruction. QObject
    # children are deleted after the engine's derived destructor cleans QML.
    bridge.setParent(engine)
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.warnings.connect(
        lambda warnings: errors.extend(w.toString() for w in warnings)
    )

    qml_path = PROJECT_ROOT / "qt_ui" / "main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    roots = engine.rootObjects()
    if not roots:
        print("QML smoke test failed: no root object was created.", file=sys.stderr)
        return 1

    if not callable(getattr(bridge, "closeAfterConfirmation", None)):
        print(
            "QML smoke test failed: closeAfterConfirmation() is not exposed.",
            file=sys.stderr,
        )
        return 1

    # Allow deferred bindings, animations, and QML Connections to initialize.
    QTimer.singleShot(700, app.quit)
    exit_code = app.exec()

    # Stop bridge timers and destroy the QML engine while the bridge is still
    # alive. This catches errors raised during QML teardown as well as startup.
    bridge._health_timer.stop()
    bridge._auto_update_timer.stop()
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()

    # The engine owns the bridge and has now destroyed it after QML teardown.
    app.processEvents()

    fatal_errors = [
        message
        for message in errors
        if any(marker in message for marker in fatal_markers)
    ]
    if fatal_errors:
        print(
            "QML smoke test failed: runtime QML error(s) detected.",
            file=sys.stderr,
        )
        for error in fatal_errors:
            print(error, file=sys.stderr)
        return 1

    if exit_code != 0:
        print(
            "QML smoke test failed: Qt event loop returned {}.".format(exit_code),
            file=sys.stderr,
        )
        return exit_code

    print(
        "QML smoke test passed: {} root object(s); no fatal QML runtime "
        "errors during startup or teardown.".format(len(roots))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
