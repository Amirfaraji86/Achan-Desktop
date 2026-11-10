from __future__ import annotations

import argparse
import ctypes
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Property, QSettings, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle

from core.controller import NetworkController
from core.update_client import UpdateClient, UpdateInfo, installed_by_setup

APP_NAME = "Achan"
APP_VERSION = "1.2.4"
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
LOCAL_APP_DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
DATA_DIR = LOCAL_APP_DATA / APP_NAME
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "achan.log"
UPDATE_DIR = DATA_DIR / "updates"
UPDATE_INTERVAL_SECONDS = 24 * 60 * 60


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def setup_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("achan")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1_500_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    return logger


LOGGER = setup_logger()


def is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def friendly_error(exc: BaseException) -> str:
    raw = str(exc).lower()
    if "wintunstartsession" in raw or "register rings" in raw or "0x000004df" in raw:
        return "رابط تونل قبلی هنوز آزاد نشده است؛ ویندوز را راه‌اندازی مجدد کن."
    if "address already in use" in raw or "only one usage" in raw:
        return "پورت محلی 4525 در حال استفاده است. برنامه دیگری از این پورت استفاده می‌کند."
    if "tun2proxy binary" in raw or "wintun.dll" in raw or "not found" in raw:
        return "فایل‌های موتور شبکه کامل نیستند. نصب آچان را Repair یا دوباره نصب کن."
    if "doh" in raw or "resolve" in raw or "timed out" in raw or "ssl" in raw:
        return "ارتباط با DNS امن برقرار نشد. اینترنت عادی را بررسی و دوباره تلاش کن."
    if "another tun2proxy" in raw or "already running" in raw:
        return "یک تونل دیگر در حال اجراست؛ ابتدا آن را به‌درستی قطع کن."
    if "administrator" in raw or "access is denied" in raw or "winerror 5" in raw:
        return "برای فعال‌کردن تونل، دسترسی مدیر ویندوز لازم است."
    return "اتصال کامل نشد. جزئیات در بخش گزارش فنی ذخیره شده است."


class SingleInstance:
    """Share the legacy Achan mutex so two builds cannot own Wintun together."""

    MUTEX_NAME = "Local\\Achan.NetworkTunnel.Singleton.v1"
    ERROR_ALREADY_EXISTS = 183

    def __init__(self, enabled: bool = True) -> None:
        self.handle = None
        self._kernel32 = None
        self.already_running = False
        if enabled and sys.platform == "win32":
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            handle = kernel32.CreateMutexW(None, True, self.MUTEX_NAME)
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            self.handle = handle
            self._kernel32 = kernel32
            self.already_running = ctypes.get_last_error() == self.ERROR_ALREADY_EXISTS

    def release(self) -> None:
        if self.handle and self._kernel32 is not None:
            try:
                self._kernel32.ReleaseMutex(self.handle)
            except Exception:
                pass
            try:
                self._kernel32.CloseHandle(self.handle)
            except Exception:
                pass
            self.handle = None
            self._kernel32 = None

    def reacquire(self) -> bool:
        self.release()
        self.__init__(enabled=True)
        return not self.already_running


class AchanBridge(QObject):
    """Qt/QML bridge for Achan's existing network core and secure updater."""

    stateChanged = Signal()
    stagesChanged = Signal()
    noticeChanged = Signal()
    diagnosticsChanged = Signal()
    languageChanged = Signal()
    updateChanged = Signal()
    closeReady = Signal()
    _stateEvent = Signal(str, str, str)
    _stageEvent = Signal(str, str, str)
    _updateResult = Signal(object, str)
    _downloadProgress = Signal(int, int)
    _downloadResult = Signal(str, str)
    _installReady = Signal()

    def __init__(self, mutex: SingleInstance, demo: bool = False) -> None:
        super().__init__()
        self.mutex = mutex
        self.demo = demo
        self.settings = QSettings("Faraj", APP_NAME)
        self._language = str(self.settings.value("language", "fa"))
        if self._language not in {"fa", "en"}:
            self._language = "fa"
        self._auto_update_checks = self.settings.value("autoUpdateChecks", True, type=bool)
        self._state = "stopped"
        self._notice = "برای شروع، دکمه اتصال را بزن."
        self._notice_en = "Press the power button to connect."
        self._notice_level = "normal"
        self._stages = {key: "idle" for key in ("engine", "proxy", "doh", "tunnel")}
        self._diagnostics = "برای مشاهده گزارش فنی، گزارش را تازه‌سازی کن."
        self._close_after_stop = False
        self._install_after_stop = False
        self._handoff_to_elevated = False
        self._downloaded_installer: Optional[Path] = None
        self._pending_update: Optional[UpdateInfo] = None
        self._update_status = "idle"
        self._update_message = ""
        self._update_notes = ""
        self._update_version = ""
        self._update_percent = 0
        self._update_check_running = False
        self._download_running = False
        self._update_client = UpdateClient()
        self.controller = None if demo else NetworkController(APP_DIR, self._log, self._on_stage)

        self._stateEvent.connect(self._apply_state)
        self._stageEvent.connect(self._apply_stage)
        self._updateResult.connect(self._apply_update_result)
        self._downloadProgress.connect(self._apply_download_progress)
        self._downloadResult.connect(self._apply_download_result)
        self._installReady.connect(self._launch_update_installer)

        # A lightweight health watcher only checks the tunnel process.
        # No ping, traffic-rate or network-monitor sampling runs in the UI.
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(1200)
        self._health_timer.timeout.connect(self._watch_tunnel)
        self._health_timer.start()

        self._auto_update_timer = QTimer(self)
        self._auto_update_timer.setInterval(UPDATE_INTERVAL_SECONDS * 1000)
        self._auto_update_timer.timeout.connect(self._scheduled_update_check)
        if self._auto_update_checks:
            self._auto_update_timer.start()
        QTimer.singleShot(5000, self._scheduled_update_check)
        self._log("Modern Qt Quick interface initialized (demo=%s, language=%s)", demo, self._language)

    def _log(self, message: str, *args) -> None:
        if args:
            LOGGER.info(message, *args)
        else:
            LOGGER.info("%s", message)

    def _on_stage(self, key: str, state: str, detail: Optional[str] = None) -> None:
        self._stageEvent.emit(key, state, detail or "")

    @Slot(str, str, str)
    def _apply_stage(self, key: str, state: str, _detail: str) -> None:
        if key in self._stages:
            self._stages[key] = state
            self.stagesChanged.emit()

    def _set_state(self, state: str, notice: Optional[str] = None, level: str = "normal") -> None:
        self._stateEvent.emit(state, notice if notice is not None else self._notice, level)

    @Slot(str, str, str)
    def _english_notice(self, notice: str, level: str) -> str:
        known = {
            "برای شروع، دکمه اتصال را بزن.": "Press the power button to connect.",
            "اتصال سراسری آچان فعال است.": "Achan system tunnel is active.",
            "در حال بررسی موتور شبکه، DNS امن و ساخت تونل…": "Checking the network engine, secure DNS and preparing the tunnel…",
            "در حال بستن تونل و بازیابی مسیر قبلی ویندوز…": "Stopping the tunnel and restoring the previous Windows routes…",
            "اتصال قطع شد؛ مسیر شبکه بازیابی شد.": "Disconnected; Windows network routes were restored.",
            "بازیابی مسیر شبکه کامل تأیید نشد؛ برای ایمنی ویندوز را Restart کن.": "Network route restoration could not be confirmed. Restart Windows before retrying.",
            "حالت نمایشی متوقف شد؛ هیچ تغییری در شبکه ایجاد نشد.": "Demo stopped; no network settings were changed.",
            "حالت نمایشی: مراحل اتصال در حال اجرا هستند…": "Demo mode: connection stages are being simulated…",
            "حالت نمایشی: اتصال شبیه‌سازی شد؛ شبکه تغییر نکرد.": "Demo mode: connection simulated; the network was not changed.",
            "حالت نمایشی بسته شد.": "Demo closed.",
            "برای ساخت تونل شبکه، تأیید دسترسی مدیر لازم است.": "Administrator permission is required to create the network tunnel.",
            "حالت واقعی اتصال فقط روی ویندوز پشتیبانی می‌شود.": "Real connection mode is supported only on Windows.",
            "گزارش فنی در کلیپ‌بورد کپی شد.": "Diagnostic log copied to the clipboard.",
        }
        if notice in known:
            return known[notice]
        if level == "error":
            return "The operation failed. See Logs & Diagnostics for technical details."
        if level == "warning":
            return "Please review the warning and retry when it is safe."
        return notice

    def _apply_state(self, state: str, notice: str, level: str) -> None:
        self._state = state
        self._notice = notice
        self._notice_en = self._english_notice(notice, level)
        self._notice_level = level
        if state == "stopped":
            for key in self._stages:
                if self._stages[key] != "error":
                    self._stages[key] = "idle"
            self.stagesChanged.emit()
        self.stateChanged.emit()
        self.noticeChanged.emit()

    @Property(str, notify=stateChanged)
    def state(self) -> str:
        return self._state

    @Property(bool, notify=stateChanged)
    def isBusy(self) -> bool:
        return self._state in {"starting", "stopping"}

    @Property(bool, notify=stateChanged)
    def isConnected(self) -> bool:
        return self._state == "running"

    @Property(str, notify=noticeChanged)
    def notice(self) -> str:
        return self._notice

    @Property(str, notify=noticeChanged)
    def noticeLevel(self) -> str:
        return self._notice_level

    @Property(str, notify=noticeChanged)
    def noticeEnglish(self) -> str:
        return self._notice_en

    @Property(str, notify=stagesChanged)
    def engineState(self) -> str:
        return self._stages["engine"]

    @Property(str, notify=stagesChanged)
    def proxyState(self) -> str:
        return self._stages["proxy"]

    @Property(str, notify=stagesChanged)
    def dohState(self) -> str:
        return self._stages["doh"]

    @Property(str, notify=stagesChanged)
    def tunnelState(self) -> str:
        return self._stages["tunnel"]

    @Property(str, constant=True)
    def version(self) -> str:
        return APP_VERSION

    @Property(bool, constant=True)
    def demoMode(self) -> bool:
        return self.demo

    @Property(str, notify=diagnosticsChanged)
    def diagnosticsText(self) -> str:
        return self._diagnostics

    @Property(str, notify=languageChanged)
    def language(self) -> str:
        return self._language

    @Property(bool, notify=languageChanged)
    def autoUpdateChecks(self) -> bool:
        return self._auto_update_checks

    @Property(str, notify=updateChanged)
    def updateStatus(self) -> str:
        return self._update_status

    @Property(str, notify=updateChanged)
    def updateMessage(self) -> str:
        return self._update_message

    @Property(str, notify=updateChanged)
    def updateVersion(self) -> str:
        return self._update_version

    @Property(str, notify=updateChanged)
    def updateNotes(self) -> str:
        return self._update_notes

    @Property(int, notify=updateChanged)
    def updatePercent(self) -> int:
        return self._update_percent

    @Property(bool, notify=updateChanged)
    def updateCanDownload(self) -> bool:
        return self._pending_update is not None and not self._download_running and self._downloaded_installer is None

    @Property(bool, notify=updateChanged)
    def updateDownloaded(self) -> bool:
        return self._downloaded_installer is not None and self._downloaded_installer.is_file()

    @Property(bool, notify=updateChanged)
    def updateCanInstall(self) -> bool:
        return self.updateDownloaded and not self.demo

    @Property(str, constant=True)
    def updateChannel(self) -> str:
        return "Windows 10/11 x64"

    @Slot()
    def toggleLanguage(self) -> None:
        self._language = "en" if self._language == "fa" else "fa"
        self.settings.setValue("language", self._language)
        self.languageChanged.emit()

    @Slot(bool)
    def setAutoUpdateChecks(self, enabled: bool) -> None:
        self._auto_update_checks = bool(enabled)
        self.settings.setValue("autoUpdateChecks", self._auto_update_checks)
        if self._auto_update_checks:
            self._auto_update_timer.start()
        else:
            self._auto_update_timer.stop()
        self.languageChanged.emit()

    @Slot()
    def closeAfterConfirmation(self) -> None:
        """Close Achan only after any active tunnel has been stopped safely."""
        # A close request must never interrupt startup or shutdown. The QML UI
        # normally blocks these states, but keep the bridge defensive as well.
        if self._state in {"starting", "stopping"}:
            return

        if self._state == "running":
            if self.demo:
                # Demo mode has no real tunnel to tear down. Simulate a clean
                # stop before letting the window run its close animation.
                for key in self._stages:
                    self._stages[key] = "idle"
                self.stagesChanged.emit()
                self._set_state("stopped", "حالت نمایشی بسته شد.", "normal")
                self.closeReady.emit()
            else:
                self._close_after_stop = True
                self._stop_async()
            return

        # Already disconnected: the QML window can fade out and close now.
        self.closeReady.emit()

    @Slot()
    def toggleConnection(self) -> None:
        if self._state in {"starting", "stopping"}:
            return
        if self._state == "running":
            if self.demo:
                for key in self._stages:
                    self._stages[key] = "idle"
                self.stagesChanged.emit()
                self._set_state("stopped", "حالت نمایشی متوقف شد؛ هیچ تغییری در شبکه ایجاد نشد.", "normal")
            else:
                self._stop_async()
            return
        if self.demo:
            self._demo_start()
            return
        if sys.platform != "win32":
            self._set_state("stopped", "حالت واقعی اتصال فقط روی ویندوز پشتیبانی می‌شود.", "error")
            return
        if not is_admin():
            self._request_admin_restart()
            return
        self._start_async()

    def _request_admin_restart(self) -> None:
        self._set_state("stopped", "برای ساخت تونل شبکه، تأیید دسترسی مدیر لازم است.", "warning")
        self.mutex.release()
        if getattr(sys, "frozen", False):
            executable, params = sys.executable, "--autostart"
        else:
            executable = sys.executable
            params = subprocess.list2cmdline([str(Path(__file__).resolve()), "--autostart"])
        try:
            shell32 = ctypes.windll.shell32
            shell32.ShellExecuteW.restype = ctypes.c_void_p
            result = int(shell32.ShellExecuteW(None, "runas", executable, params, str(APP_DIR), 1) or 0)
        except Exception:
            result = 0
            LOGGER.exception("Could not request administrator elevation")
        if result <= 32:
            self.mutex.reacquire()
            self._set_state("stopped", "درخواست دسترسی مدیر ویندوز لغو شد یا انجام نشد.", "warning")
            return
        self._handoff_to_elevated = True
        self.closeReady.emit()

    def _start_async(self) -> None:
        self._set_state("starting", "در حال بررسی موتور شبکه، DNS امن و ساخت تونل…", "warning")
        threading.Thread(target=self._start_worker, name="AchanQtStart", daemon=True).start()

    def _start_worker(self) -> None:
        try:
            assert self.controller is not None
            self.controller.start()
            self._set_state("running", "اتصال سراسری آچان فعال است.", "success")
        except Exception as exc:
            LOGGER.exception("Achan Qt startup failed")
            self._set_state("stopped", friendly_error(exc), "error")

    def _stop_async(self) -> None:
        self._set_state("stopping", "در حال بستن تونل و بازیابی مسیر قبلی ویندوز…", "warning")
        threading.Thread(target=self._stop_worker, name="AchanQtStop", daemon=True).start()

    def _stop_worker(self) -> None:
        clean = False
        try:
            assert self.controller is not None
            clean = self.controller.stop()
        except Exception:
            LOGGER.exception("Achan Qt shutdown failed")
        if clean:
            self._set_state("stopped", "اتصال قطع شد؛ مسیر شبکه بازیابی شد.", "normal")
            if self._close_after_stop:
                self._close_after_stop = False
                self.closeReady.emit()
            elif self._install_after_stop:
                self._install_after_stop = False
                self._installReady.emit()
        else:
            self._close_after_stop = False
            self._install_after_stop = False
            self._set_state("stopped", "بازیابی مسیر شبکه کامل تأیید نشد؛ برای ایمنی ویندوز را Restart کن.", "error")

    def _demo_start(self) -> None:
        self._set_state("starting", "حالت نمایشی: مراحل اتصال در حال اجرا هستند…", "warning")
        order = (("engine", 250), ("proxy", 650), ("doh", 1050), ("tunnel", 1450))
        for key, delay in order:
            QTimer.singleShot(delay, lambda name=key: self._apply_stage(name, "checking", ""))
            QTimer.singleShot(delay + 350, lambda name=key: self._apply_stage(name, "ready", ""))
        QTimer.singleShot(2100, lambda: self._set_state("running", "حالت نمایشی: اتصال شبیه‌سازی شد؛ شبکه تغییر نکرد.", "success"))

    def _watch_tunnel(self) -> None:
        """Detect an unexpected tunnel-process exit without sampling network stats."""
        if not self.demo and self._state == "running" and self.controller is not None:
            if not self.controller.is_running():
                LOGGER.error("Tunnel process exited unexpectedly; starting cleanup")
                self._stop_async()

    @Slot()
    def refreshDiagnostics(self) -> None:
        try:
            self._diagnostics = LOG_FILE.read_text(encoding="utf-8", errors="replace")[-60000:]
            if not self._diagnostics:
                self._diagnostics = "هنوز گزارشی ثبت نشده است."
        except OSError as exc:
            self._diagnostics = "خواندن گزارش ممکن نشد: {}".format(exc)
        self.diagnosticsChanged.emit()

    @Slot()
    def copyDiagnostics(self) -> None:
        QGuiApplication.clipboard().setText(self._diagnostics)
        self._set_state(self._state, "گزارش فنی در کلیپ‌بورد کپی شد.", "success")

    def _scheduled_update_check(self) -> None:
        if self.demo or not self._auto_update_checks or self._update_check_running:
            return
        # Daily background checks are useful only for the installed build.
        if not installed_by_setup(APP_DIR):
            return
        self.checkForUpdates()

    @Slot()
    def checkForUpdates(self) -> None:
        if self.demo:
            self._update_status = "demo"
            self._update_message = "Update checks are disabled in demo mode."
            self.updateChanged.emit()
            return
        if self._update_check_running or self._download_running:
            return
        self._update_check_running = True
        self._update_status = "checking"
        self._update_message = ""
        self._update_version = ""
        self._update_notes = ""
        self.updateChanged.emit()
        threading.Thread(target=self._check_update_worker, name="AchanUpdateCheck", daemon=True).start()

    def _check_update_worker(self) -> None:
        try:
            if sys.platform != "win32":
                raise RuntimeError("Achan updates are available for Windows builds only.")
            version = sys.getwindowsversion()
            info = self._update_client.check_for_update(APP_VERSION, (version.major, version.minor))
            self._updateResult.emit(info, "")
        except Exception as exc:
            LOGGER.warning("Update check failed: %s", exc)
            self._updateResult.emit(None, str(exc))

    @Slot(object, str)
    def _apply_update_result(self, info: object, error: str) -> None:
        self._update_check_running = False
        if error:
            self._update_status = "error"
            self._update_message = error
            self._pending_update = None
        elif info is None:
            self._update_status = "current"
            self._update_message = "You are using the latest compatible version."
            self._pending_update = None
        else:
            self._pending_update = info  # type: ignore[assignment]
            self._update_version = self._pending_update.version
            self._update_notes = self._pending_update.release_notes or ""
            self._update_status = "available"
            self._update_message = "A verified release is available."
        self.updateChanged.emit()

    @Slot()
    def downloadUpdate(self) -> None:
        if self.demo or self._pending_update is None or self._download_running:
            return
        self._download_running = True
        self._update_status = "downloading"
        self._update_percent = 0
        self.updateChanged.emit()
        threading.Thread(target=self._download_update_worker, args=(self._pending_update,),
                         name="AchanUpdateDownload", daemon=True).start()

    def _download_update_worker(self, info: UpdateInfo) -> None:
        try:
            def progress(received: int, total: int) -> None:
                percent = int(received * 100 / total) if total else 0
                self._downloadProgress.emit(percent, total)

            path = self._update_client.download_installer(info, UPDATE_DIR, progress=progress)
            self._downloadResult.emit(str(path), "")
        except Exception as exc:
            LOGGER.exception("Update download failed")
            self._downloadResult.emit("", str(exc))

    @Slot(int, int)
    def _apply_download_progress(self, percent: int, _total: int) -> None:
        self._update_percent = max(0, min(100, percent))
        self.updateChanged.emit()

    @Slot(str, str)
    def _apply_download_result(self, path: str, error: str) -> None:
        self._download_running = False
        if error:
            self._update_status = "error"
            self._update_message = error
        else:
            self._downloaded_installer = Path(path)
            self._update_status = "downloaded"
            self._update_message = "Installer downloaded and SHA-256 verified."
            self._update_percent = 100
        self.updateChanged.emit()

    @Slot()
    def installUpdate(self) -> None:
        if self.demo or not self.updateDownloaded:
            return
        if self._state in {"starting", "stopping"}:
            return
        if self._state == "running":
            self._install_after_stop = True
            self._stop_async()
            return
        self._launch_update_installer()

    @Slot()
    def _launch_update_installer(self) -> None:
        if self.demo or not self.updateDownloaded or self._downloaded_installer is None:
            return
        try:
            installer = self._downloaded_installer
            if installed_by_setup(APP_DIR):
                bundled_helper = APP_DIR / "AchanUpdater.exe"
                app_exe = APP_DIR / "Achan.exe"
                if not bundled_helper.is_file() or not app_exe.is_file():
                    self._update_status = "error"
                    self._update_message = "The installed updater helper is missing. Run the downloaded setup manually."
                    self.updateChanged.emit()
                    os.startfile(str(installer))
                    return
                helper_dir = DATA_DIR / "updater"
                helper_dir.mkdir(parents=True, exist_ok=True)
                helper = helper_dir / "AchanUpdater.exe"
                shutil.copy2(str(bundled_helper), str(helper))
                flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
                ) | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                subprocess.Popen(
                    [str(helper), "--wait-pid", str(os.getpid()),
                     "--installer", str(installer), "--restart", str(app_exe)],
                    cwd=str(APP_DIR), creationflags=flags,
                )
                self._update_status = "installing"
                self.updateChanged.emit()
                self.closeReady.emit()
                return
            # Source/portable runs cannot safely self-replace. Open the already
            # verified vendor setup and let Windows handle installation.
            os.startfile(str(installer))
            self._update_status = "installer_opened"
            self._update_message = "Verified installer opened. Close Achan before completing setup."
            self.updateChanged.emit()
        except Exception as exc:
            LOGGER.exception("Could not launch downloaded update")
            self._update_status = "error"
            self._update_message = str(exc)
            self.updateChanged.emit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Achan modern Qt Quick interface")
    parser.add_argument("--autostart", action="store_true", help="connect after elevation")
    parser.add_argument("--demo", action="store_true", help="run visual demo without changing network settings")
    args, _unknown = parser.parse_known_args()

    if not args.demo:
        if sys.platform != "win32":
            print("Achan network mode is available only on supported Windows x64 editions.")
            return 2
        if sys.maxsize <= 2 ** 32:
            print("Achan requires 64-bit Windows.")
            return 2
        win_version = sys.getwindowsversion()
        if win_version.major < 10:
            print("The modern Qt interface requires Windows 10 or Windows 11. Use the legacy Windows 7 build.")
            return 2
        if win_version.major == 10 and getattr(win_version, "build", 0) < 17763:
            print("The modern Qt interface requires Windows 10 version 1809 (build 17763) or later.")
            return 2

    mutex = SingleInstance(enabled=not args.demo)
    if mutex.already_running:
        print("Another Achan instance is already running. Close it before launching the modern interface.", file=sys.stderr)
        mutex.release()
        return 4

    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Faraj")
    app.setQuitOnLastWindowClosed(False)
    app.lastWindowClosed.connect(app.quit)

    engine = QQmlApplicationEngine()
    bridge = AchanBridge(mutex, demo=args.demo)
    # Keep the bridge alive throughout QML teardown. As an engine child, it is
    # destroyed only after QQmlApplicationEngine has released its root objects
    # and contexts, avoiding a transient null context property on shutdown.
    bridge.setParent(engine)
    # PyInstaller and windeployqt may place QML plugins in either the
    # application-level qml folder or the bundled PySide6 runtime folder.
    qml_import_candidates = (
        APP_DIR / "qml",
        resource_path("qml"),
        resource_path("PySide6/Qt/qml"),
        APP_DIR / "PySide6" / "Qt" / "qml",
    )
    for import_path in qml_import_candidates:
        if import_path.is_dir():
            engine.addImportPath(str(import_path))
    qml_root = resource_path("qt_ui/main.qml")
    engine.rootContext().setContextProperty("bridge", bridge)

    def report_qml_warnings(warnings) -> None:
        for warning in warnings:
            message = warning.toString()
            LOGGER.error("QML: %s", message)
            print("QML:", message, file=sys.stderr, flush=True)

    engine.warnings.connect(report_qml_warnings)
    engine.load(QUrl.fromLocalFile(str(qml_root)))
    roots = engine.rootObjects()
    if not roots:
        mutex.release()
        print("Could not load QML interface: {}".format(qml_root), file=sys.stderr, flush=True)
        return 3

    main_window = next((obj for obj in roots if isinstance(obj, QQuickWindow)), None)
    if main_window is None:
        mutex.release()
        print("QML root object is not a QQuickWindow.", file=sys.stderr, flush=True)
        return 3

    main_window.show()
    main_window.raise_()
    main_window.requestActivate()
    LOGGER.info("Qt Quick window visible: %sx%s", main_window.width(), main_window.height())
    print("[Achan Qt] Window shown: {}x{}".format(main_window.width(), main_window.height()), flush=True)

    if args.autostart:
        QTimer.singleShot(650, bridge.toggleConnection)

    try:
        return app.exec()
    finally:
        mutex.release()


if __name__ == "__main__":
    raise SystemExit(main())
