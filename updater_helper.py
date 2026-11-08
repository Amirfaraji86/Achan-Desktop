"""Small detached helper that installs Achan after the GUI process exits.

It intentionally uses only the Python standard library so it can be built for
both the current Windows release and the Windows 7 compatibility build.
"""
from __future__ import annotations

import argparse
import ctypes
import logging
import os
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

LOG_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "Achan" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / "updater.log"),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

SYNCHRONIZE = 0x00100000
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0x00000000
SEE_MASK_NOCLOSEPROCESS = 0x00000040
SW_HIDE = 0


class SHELLEXECUTEINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


def wait_for_process(pid: int) -> None:
    if os.name != "nt" or pid <= 0:
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        logging.info("Parent process %s has already exited or cannot be opened.", pid)
        return
    try:
        result = kernel32.WaitForSingleObject(handle, INFINITE)
        if result != WAIT_OBJECT_0:
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel32.CloseHandle(handle)


def run_installer(installer: Path) -> int:
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFO)]
    shell32.ShellExecuteExW.restype = wintypes.BOOL
    info = SHELLEXECUTEINFO()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = str(installer)
    info.lpParameters = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /CLOSEAPPLICATIONS"
    info.lpDirectory = str(installer.parent)
    info.nShow = SW_HIDE
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        error = ctypes.get_last_error()
        raise ctypes.WinError(error)
    if not info.hProcess:
        return 0

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.WaitForSingleObject(info.hProcess, INFINITE)
    exit_code = wintypes.DWORD()
    if not kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(exit_code)):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(info.hProcess)
        raise ctypes.WinError(error)
    kernel32.CloseHandle(info.hProcess)
    return int(exit_code.value)


def restart_app(executable: Path) -> None:
    if not executable.is_file():
        logging.error("Restart executable does not exist: %s", executable)
        return
    flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
    )
    subprocess.Popen([str(executable)], cwd=str(executable.parent), creationflags=flags)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-pid", type=int, required=True)
    parser.add_argument("--installer", required=True)
    parser.add_argument("--restart", required=True)
    args = parser.parse_args()
    installer = Path(args.installer).resolve()
    app = Path(args.restart).resolve()
    try:
        if not installer.is_file():
            raise FileNotFoundError("Installer does not exist: {}".format(installer))
        wait_for_process(args.wait_pid)
        code = run_installer(installer)
        logging.info("Inno Setup exit code: %s", code)
        # Reopen the current installation even when UAC was declined or the
        # installer returned an error, so the user is not left without Achan.
        restart_app(app)
        return 0 if code == 0 else code
    except Exception:
        logging.exception("Automatic update installation failed")
        try:
            restart_app(app)
        except Exception:
            logging.exception("Could not restart Achan after update failure")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
