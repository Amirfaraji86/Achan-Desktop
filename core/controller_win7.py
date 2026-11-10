"""Windows 7-specific startup validation and Wintun DNS cleanup."""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from typing import Optional

from .controller import NetworkController


_PREMATURE_READY_LOG = (
    "Achan tunnel is running; IPv4 TCP traffic is routed through the local proxy"
)


class Win7NetworkController(NetworkController):
    """Keep Win7-only readiness and WMI cleanup out of the Win10/11 controller."""

    STARTUP_TIMEOUT_SECONDS = 75.0
    STARTUP_POLL_SECONDS = 0.15

    def __init__(self, app_dir, logger, stage=None):
        self._engine_ready = threading.Event()
        self._engine_error: Optional[str] = None

        # The shared controller emits this message after only a 4-second
        # process-alive check. Do not let the UI interpret it as a ready tunnel.
        def guarded_logger(message):
            if message == _PREMATURE_READY_LOG:
                return
            logger(message)

        super().__init__(app_dir, guarded_logger, stage)

    def _read_process_output(self, process):
        stream = process.stdout
        if stream is None:
            return
        try:
            for raw_line in stream:
                line = raw_line.rstrip()
                if not line:
                    continue
                lowered = line.lower()
                # tun2proxy v0.8.7 emits this only after TUN creation and
                # tproxy_setup (including the Win7 netsh DNS command) succeed.
                if "tun2proxy" in lowered and "starting..." in lowered:
                    self._engine_ready.set()
                if (
                    "wintuncreateadapter failed" in lowered
                    or "failed to install adapter device" in lowered
                    or "main loop error:" in lowered
                ):
                    self._engine_error = line
                self.logger("tun2proxy: {}".format(line))
        except Exception as exc:
            self.logger("Could not read tun2proxy output: {}".format(exc))

    def _set_stage(self, key, state, detail=None):
        # The base class reaches ready after 4 seconds if its child survives.
        # Keep the Win7 stage pending until tun2proxy's post-setup banner arrives.
        if key == "tunnel" and state == "ready" and not self._engine_ready.is_set():
            self.logger(
                "Wintun readiness not confirmed yet; keeping tunnel stage pending"
            )
            super()._set_stage(
                key, "checking", "در انتظار آماده‌شدن رابط Wintun"
            )
            return
        super()._set_stage(key, state, detail)

    def _cleanup_failed_start(self):
        try:
            clean = self.stop()
            if not clean:
                self.logger(
                    "Warning: tunnel cleanup was not fully confirmed after startup failure"
                )
        except Exception as exc:
            self.logger("Startup cleanup warning: {}".format(exc))
        self._set_stage("tunnel", "error", "خطا")

    def start(self):
        self._engine_ready.clear()
        self._engine_error = None

        # Preserve the base engine/proxy/DoH setup and its failure cleanup.
        super().start()

        process = self.process
        if process is None:
            self._cleanup_failed_start()
            raise RuntimeError(
                "tun2proxy process was not available after the startup check"
            )

        deadline = time.monotonic() + self.STARTUP_TIMEOUT_SECONDS
        while not self._engine_ready.is_set():
            if self._engine_error:
                detail = self._engine_error
                self._cleanup_failed_start()
                raise RuntimeError(detail)

            exit_code = process.poll()
            if exit_code is not None:
                detail = self._engine_error or (
                    "tun2proxy exited before Wintun startup confirmation "
                    "(code {})".format(exit_code)
                )
                self._cleanup_failed_start()
                raise RuntimeError(detail)

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                detail = self._engine_error or (
                    "Wintun adapter startup was not confirmed within {} seconds".format(
                        int(self.STARTUP_TIMEOUT_SECONDS)
                    )
                )
                self._cleanup_failed_start()
                raise RuntimeError(detail)

            self._engine_ready.wait(
                min(self.STARTUP_POLL_SECONDS, remaining)
            )

        # The process must still be alive after emitting the setup-complete banner.
        exit_code = process.poll()
        if exit_code is not None:
            detail = self._engine_error or (
                "tun2proxy exited immediately after startup confirmation "
                "(code {})".format(exit_code)
            )
            self._cleanup_failed_start()
            raise RuntimeError(detail)

        self._set_stage("tunnel", "ready", "فعال")
        self.logger(
            "Wintun adapter and tun2proxy startup confirmed; IPv4 TCP tunnel is ready"
        )

    def _reset_wintun_dns(self) -> bool:
        """Restore DNS on the Wintun adapter, including numbered aliases."""
        if sys.platform != "win32":
            self._tunnel_attempted = False
            return True

        command = (
            "$adapters = Get-WmiObject -Class Win32_NetworkAdapter | "
            "Where-Object { $_.NetConnectionID -match '^wintun(?:\\s+\\d+)?$' }; "
            "foreach ($adapter in $adapters) { "
            "$config = Get-WmiObject -Class Win32_NetworkAdapterConfiguration "
            "-Filter \"Index=$($adapter.Index)\"; "
            "if ($config) { $result = $config.SetDNSServerSearchOrder($null); "
            "if ($result.ReturnValue -ne 0) { throw ('DNS reset return code: ' + $result.ReturnValue) } } }"
        )
        try:
            result = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "Bypass", "-Command", command,
                ],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                self.logger("Temporary Wintun DNS setting cleared")
                self._tunnel_attempted = False
                return True
            self.logger(
                "Wintun DNS reset warning: %s"
                % (result.stderr or result.stdout).strip()
            )
            return False
        except Exception as exc:
            self.logger("Wintun DNS reset warning: %s" % exc)
            return False
