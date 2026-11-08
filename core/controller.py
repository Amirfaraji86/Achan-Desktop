"""Lifecycle-safe coordinator for Achan's local DoH proxy and Windows TUN."""
from __future__ import annotations

import ctypes
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .proxy import LocalProxy
from .windows_network import get_default_interface_indices

StageCallback = Callable[[str, str, Optional[str]], None]


class NetworkController:
    def __init__(self, app_dir: Path, logger: Callable[[str], None], stage: StageCallback | None = None) -> None:
        self.app_dir = app_dir
        self.logger = logger
        self.stage = stage or (lambda _key, _state, _detail=None: None)
        self.proxy: LocalProxy | None = None
        self.process: subprocess.Popen | None = None
        self.interface_indices: dict[str, int | None] | None = None
        self._lock = threading.RLock()
        self._starting = False
        self._last_stop_clean = True
        self._tunnel_attempted = False

    def _set_stage(self, key: str, state: str, detail: str | None = None) -> None:
        try:
            self.stage(key, state, detail)
        except Exception:
            pass

    def _binary_path(self) -> Path:
        candidates = [self.app_dir / "bin" / "tun2proxy-bin.exe", self.app_dir / "bin" / "tun2proxy.exe"]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise FileNotFoundError("tun2proxy binary was not found")

    @staticmethod
    def _another_engine_is_running() -> bool:
        result = subprocess.run(
            ["tasklist.exe", "/FO", "CSV", "/NH"],
            # Elevated GUI launches may not have a valid console STDIN handle.
            # Explicit DEVNULL prevents subprocess from inheriting that invalid handle.
            stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        names = {line.split(",", 1)[0].strip().strip('"').lower() for line in (result.stdout or "").splitlines()}
        return bool(names.intersection({"tun2proxy-bin.exe", "tun2proxy.exe"}))

    def start(self) -> None:
        with self._lock:
            if self._starting:
                raise RuntimeError("Achan connection startup is already running")
            if self.process is not None and self.process.poll() is None:
                raise RuntimeError("Achan tunnel is already running")
            if sys.platform != "win32":
                raise OSError("Achan system TUN mode is available only on Windows 7 SP1 or later x64")
            self._starting = True

        failed_stage = "engine"
        try:
            self._set_stage("engine", "checking", "در حال بررسی")
            binary = self._binary_path()
            wintun = binary.parent / "wintun.dll"
            if not wintun.is_file():
                raise FileNotFoundError("wintun.dll is missing beside tun2proxy-bin.exe")
            if self._another_engine_is_running():
                raise RuntimeError("Another tun2proxy process is already running")
            self.logger("Engine binary and Wintun DLL verified")
            self._set_stage("engine", "ready", "آماده")

            self.interface_indices = get_default_interface_indices()
            self.logger(f"Captured physical interface indexes: {self.interface_indices}")

            failed_stage = "proxy"
            self._set_stage("proxy", "checking", "در حال اجرا")
            self.proxy = LocalProxy(self.interface_indices, self.logger)
            self.proxy.start()
            self._set_stage("proxy", "ready", "آماده")

            failed_stage = "doh"
            self._set_stage("doh", "checking", "در حال آزمایش")
            # This is a real end-to-end DoH smoke test, before the system route is changed.
            resolved = self.proxy.resolver.resolve("www.youtube.com")
            if not resolved:
                raise OSError("DoH preflight returned no address for www.youtube.com")
            self.logger(f"DoH preflight succeeded: www.youtube.com -> {', '.join(resolved)}")
            self._set_stage("doh", "ready", "پاسخ‌گو")

            failed_stage = "tunnel"
            self._set_stage("tunnel", "checking", "در حال ساخت")
            args = [
                str(binary), "--setup", "--proxy", "http://127.0.0.1:4525", "--dns", "virtual",
                "--verbosity", "info", "--max-sessions", "384",
            ]
            if self.interface_indices.get("ipv6"):
                args.append("--ipv6-enabled")
            # Give the console subsystem a private hidden console so Ctrl+Break can
            # reach tun2proxy's ctrlc handler and let it restore the original routes.
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            creationflags = (
                getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
            self.logger("Starting tun2proxy with a hidden console and graceful Ctrl+Break shutdown")
            self._tunnel_attempted = True
            self.process = subprocess.Popen(
                args,
                cwd=str(binary.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
                startupinfo=startupinfo,
            )
            process = self.process
            threading.Thread(target=self._read_process_output, args=(process,), name="AchanTunnelLog", daemon=True).start()
            deadline = time.monotonic() + 4.0
            while time.monotonic() < deadline:
                code = process.poll()
                if code is not None:
                    self.process = None
                    raise RuntimeError(f"tun2proxy exited during startup (code {code})")
                time.sleep(0.15)
            if process.poll() is not None:
                code = process.returncode
                self.process = None
                raise RuntimeError(f"tun2proxy exited during startup (code {code})")
            self._set_stage("tunnel", "ready", "فعال")
            self.logger("Achan tunnel is running; IPv4 TCP traffic is routed through the local proxy")
            self.logger("Reminder: HTTP proxy transport does not relay arbitrary UDP")
        except Exception:
            # Never leave the loopback proxy running after a failed preflight/start.
            active = self.process
            if active is not None and active.poll() is None:
                self.stop()
            else:
                self.process = None
                self._stop_proxy_only()
                self.interface_indices = None
                if self._tunnel_attempted:
                    self._reset_wintun_dns()
            self._set_stage(failed_stage, "error", "خطا")
            raise
        finally:
            with self._lock:
                self._starting = False

    def _read_process_output(self, process: subprocess.Popen) -> None:
        stream = process.stdout
        if stream is None:
            return
        try:
            for line in stream:
                line = line.rstrip()
                if line:
                    # Raw third-party diagnostics are written to the private local log, not shown in the UI.
                    self.logger(f"tun2proxy: {line}")
        except Exception as exc:
            self.logger(f"Could not read tun2proxy output: {exc}")

    def _reset_wintun_dns(self) -> bool:
        """Clear temporary Wintun DNS and report whether restoration succeeded."""
        if sys.platform != "win32":
            self._tunnel_attempted = False
            return True
        # Windows 7 does not include the newer NetAdapter/NetTCPIP PowerShell
        # modules. Win32_NetworkAdapterConfiguration is available on Win7 SP1
        # and later, so use WMI to restore the Wintun adapter DNS to automatic.
        command = (
            "$adapter = Get-WmiObject -Class Win32_NetworkAdapter "
            "-Filter \"NetConnectionID='wintun'\" | Select-Object -First 1; "
            "if ($adapter) { "
            "$config = Get-WmiObject -Class Win32_NetworkAdapterConfiguration "
            "-Filter \"Index=$($adapter.Index)\"; "
            "if ($config) { $result = $config.SetDNSServerSearchOrder($null); "
            "if ($result.ReturnValue -ne 0) { throw ('DNS reset return code: ' + $result.ReturnValue) } } }"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
                # Same invalid inherited STDIN issue can otherwise prevent cleanup.
                stdin=subprocess.DEVNULL,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                self.logger("Temporary Wintun DNS setting cleared")
                self._tunnel_attempted = False
                return True
            self.logger(f"Wintun DNS reset warning: {(result.stderr or result.stdout).strip()}")
            # Keep the cleanup flag set. A later stop/exit attempt may retry;
            # importantly, the updater must not install over an unclean state.
            return False
        except Exception as exc:
            self.logger(f"Wintun DNS reset warning: {exc}")
            return False

    def _stop_proxy_only(self) -> None:
        proxy, self.proxy = self.proxy, None
        if proxy is not None:
            try:
                proxy.stop()
            except Exception as exc:
                self.logger(f"Local proxy stop warning: {exc}")

    def stop(self) -> bool:
        clean = True
        with self._lock:
            process, self.process = self.process, None
        if process is not None and process.poll() is None:
            self.logger("Requesting graceful tun2proxy shutdown to restore Windows routes")
            try:
                if sys.platform == "win32" and hasattr(signal, "CTRL_BREAK_EVENT"):
                    # A windowed Tk app has no console attached. Attach to the
                    # hidden child console temporarily so Ctrl+Break reaches
                    # tun2proxy's handler and its route-restoration Drop guard.
                    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                    kernel32.AttachConsole.argtypes = [ctypes.c_uint]
                    kernel32.AttachConsole.restype = ctypes.c_bool
                    kernel32.GenerateConsoleCtrlEvent.argtypes = [ctypes.c_uint, ctypes.c_uint]
                    kernel32.GenerateConsoleCtrlEvent.restype = ctypes.c_bool
                    kernel32.FreeConsole.argtypes = []
                    kernel32.FreeConsole.restype = ctypes.c_bool
                    if not kernel32.AttachConsole(process.pid):
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if not kernel32.GenerateConsoleCtrlEvent(signal.CTRL_BREAK_EVENT, process.pid):
                            raise ctypes.WinError(ctypes.get_last_error())
                    finally:
                        kernel32.FreeConsole()
                else:
                    process.terminate()
                process.wait(timeout=18)
            except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
                self.logger(f"Graceful shutdown did not complete: {exc}")
                clean = False
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    try:
                        process.kill()
                        process.wait(timeout=4)
                    except Exception as kill_exc:
                        self.logger(f"Could not terminate tun2proxy: {kill_exc}")
        if self._tunnel_attempted and not self._reset_wintun_dns():
            clean = False
        self._stop_proxy_only()
        self.interface_indices = None
        self._last_stop_clean = clean
        self.logger("Achan stopped; local proxy closed")
        return clean

    def is_running(self) -> bool:
        with self._lock:
            return self.process is not None and self.process.poll() is None
