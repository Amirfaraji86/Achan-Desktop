from __future__ import annotations

import argparse
import ctypes
import logging
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import messagebox, scrolledtext

from core.controller import NetworkController

# Tk 8.6 does not shape Arabic-script glyphs itself. Shape Persian labels before
# handing them to Tk so the UI is legible on Windows and in diagnostics.
try:
    import arabic_reshaper
    from bidi.algorithm import get_display as _bidi_get_display

    def rtl_text(value: object) -> object:
        if not isinstance(value, str) or not any("\u0600" <= char <= "\u06ff" for char in value):
            return value
        return _bidi_get_display(arabic_reshaper.reshape(value), base_dir="R")

except ImportError:
    def rtl_text(value: object) -> object:
        return value


class _RTLLabel(tk.Label):
    def __init__(self, master=None, cnf=None, **kwargs):
        if "text" in kwargs:
            kwargs["text"] = rtl_text(kwargs["text"])
        if isinstance(cnf, dict) and "text" in cnf:
            cnf = dict(cnf)
            cnf["text"] = rtl_text(cnf["text"])
        super().__init__(master, cnf or {}, **kwargs)

    def configure(self, cnf=None, **kwargs):
        if "text" in kwargs:
            kwargs["text"] = rtl_text(kwargs["text"])
        if isinstance(cnf, dict) and "text" in cnf:
            cnf = dict(cnf)
            cnf["text"] = rtl_text(cnf["text"])
        return super().configure(cnf, **kwargs)

    config = configure


class _RTLButton(tk.Button):
    def __init__(self, master=None, cnf=None, **kwargs):
        if "text" in kwargs:
            kwargs["text"] = rtl_text(kwargs["text"])
        if isinstance(cnf, dict) and "text" in cnf:
            cnf = dict(cnf)
            cnf["text"] = rtl_text(cnf["text"])
        super().__init__(master, cnf or {}, **kwargs)

    def configure(self, cnf=None, **kwargs):
        if "text" in kwargs:
            kwargs["text"] = rtl_text(kwargs["text"])
        if isinstance(cnf, dict) and "text" in cnf:
            cnf = dict(cnf)
            cnf["text"] = rtl_text(cnf["text"])
        return super().configure(cnf, **kwargs)

    config = configure


# All text labels/buttons in the compact GUI get proper Persian shaping.
tk.Label = _RTLLabel
tk.Button = _RTLButton

APP_VERSION = "1.0.3"
APP_NAME = "Achan"
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
LOCAL_APP_DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
DATA_DIR = LOCAL_APP_DATA / APP_NAME
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "achan.log"

COLORS = {
    "bg": "#080D0A",
    "panel": "#101914",
    "panel2": "#142119",
    "border": "#263B2D",
    "green": "#45E58B",
    "green2": "#1C9E5B",
    "green_dim": "#173B28",
    "red": "#FF6B78",
    "red_dim": "#472329",
    "text": "#EAF5ED",
    "muted": "#8C9E91",
    "muted2": "#5D7063",
    "amber": "#E9C16E",
    "white": "#FFFFFF",
}

STAGES = {
    "engine": ("موتور و درایور", "فایل‌های اصلی و Wintun"),
    "doh": ("DNS امن", "بررسی پاسخ‌گویی DoH"),
    "proxy": ("پراکسی محلی", "اتصال محدود به همین دستگاه"),
    "tunnel": ("تونل شبکه", "مسیریابی سراسری TCP"),
}


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
    raw = str(exc)
    low = raw.lower()
    if "wintunstartsession" in low or "register rings" in low or "0x000004df" in low:
        return "رابط تونل قبلی هنوز آزاد نشده است. یک‌بار ویندوز را راه‌اندازی مجدد کن و دوباره امتحان کن."
    if "address already in use" in low or "only one usage" in low:
        return "پورت محلی آچان در حال استفاده است. برنامه یا پراکسی دیگری را که از پورت 4525 استفاده می‌کند ببند."
    if "tun2proxy binary" in low or "wintun.dll" in low or "not found" in low:
        return "فایل‌های موتور شبکه کامل نیستند. نصب آچان را Repair کن یا دوباره نصب کن."
    if "doh" in low or "resolve" in low or "timed out" in low or "ssl" in low:
        return "ارتباط با سرویس DNS امن برقرار نشد. اینترنت عادی را بررسی کن و چند لحظه بعد دوباره تلاش کن."
    if "another tun2proxy" in low or "already running" in low:
        return "یک نشست تونل دیگر در حال اجراست. ابتدا آن را به‌درستی قطع کن."
    if "administrator" in low or "access is denied" in low or "winerror 5" in low:
        return "برای فعال‌کردن تونل، مجوز مدیر ویندوز لازم است. درخواست UAC را تأیید کن."
    return "اتصال کامل نشد. جزئیات فنی در بخش «گزارش تشخیصی» ذخیره شده است."


class SingleInstance:
    """A named Windows mutex prevents two Achan instances from starting Wintun."""
    MUTEX_NAME = "Local\\Achan.NetworkTunnel.Singleton.v1"
    ERROR_ALREADY_EXISTS = 183

    def __init__(self) -> None:
        self.handle = None
        self.already_running = False
        self._kernel32 = None
        if sys.platform == "win32":
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
        self.__init__()
        return not self.already_running


class StageRow(tk.Frame):
    def __init__(self, parent: tk.Widget, key: str) -> None:
        super().__init__(parent, bg=COLORS["panel"])
        self.key = key
        title, subtitle = STAGES[key]
        self.dot = tk.Canvas(self, width=16, height=16, bg=COLORS["panel"], highlightthickness=0)
        self.dot.pack(side="right", padx=(0, 10))
        self.dot_id = None
        self.spinner_phase = 0

        copy = tk.Frame(self, bg=COLORS["panel"])
        copy.pack(side="right", fill="x", expand=True)
        self.title = tk.Label(copy, text=title, bg=COLORS["panel"], fg=COLORS["text"],
                              font=("Segoe UI", 10, "bold"), anchor="e")
        self.title.pack(anchor="e")
        self.subtitle = tk.Label(copy, text=subtitle, bg=COLORS["panel"], fg=COLORS["muted"],
                                 font=("Segoe UI", 8), anchor="e")
        self.subtitle.pack(anchor="e", pady=(1, 0))
        self.state = tk.Label(self, text="در انتظار", bg=COLORS["panel"], fg=COLORS["muted2"],
                              font=("Segoe UI", 8, "bold"), width=11, anchor="w")
        self.state.pack(side="left", padx=(8, 0))
        self.current_state = "idle"
        self.set_state("idle")

    def set_state(self, state: str, detail: str | None = None) -> None:
        if state == "checking" and self.current_state == "checking":
            if detail:
                self.state.configure(text=detail, fg=COLORS["amber"])
            return
        mapping = {
            "idle": (COLORS["muted2"], "در انتظار", COLORS["muted2"]),
            "checking": (COLORS["amber"], "در حال بررسی", COLORS["amber"]),
            "ready": (COLORS["green"], "آماده", COLORS["green"]),
            "error": (COLORS["red"], "نیاز به بررسی", COLORS["red"]),
        }
        dot, text, fg = mapping.get(state, mapping["idle"])
        self.current_state = state
        self.dot.delete("all")
        if state == "checking":
            self.spinner_phase = 0
            self._animate_spinner()
        else:
            self.dot.create_oval(3, 3, 13, 13, fill=dot, outline="")
        self.state.configure(text=detail or text, fg=fg)

    def _animate_spinner(self) -> None:
        if self.current_state != "checking":
            return
        self.dot.delete("all")
        self.dot.create_arc(2, 2, 14, 14, start=self.spinner_phase, extent=265,
                            style=tk.ARC, outline=COLORS["amber"], width=2)
        self.spinner_phase = (self.spinner_phase + 34) % 360
        self.after(75, self._animate_spinner)


class AchanApp:
    def __init__(self, root: tk.Tk, mutex: SingleInstance, auto_start: bool = False) -> None:
        self.root = root
        self.mutex = mutex
        self.events: queue.Queue[tuple] = queue.Queue()
        self.controller = NetworkController(APP_DIR, self._log, self._stage_event)
        self.state = "stopped"
        self.closing = False
        self.rows: dict[str, StageRow] = {}
        self._toggle_anim_after = None
        self._toggle_progress = 0.0
        self._toggle_target = 0.0
        self._toggle_anim_started = 0.0
        self._toggle_anim_from = 0.0
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(120, self._drain_events)
        self.root.after(900, self._monitor)
        self._log("Achan initialized")
        self._set_notice("برای شروع، کلید اتصال را روشن کن.", kind="normal")
        if auto_start:
            self.root.after(500, self.toggle_connection)

    def _build_ui(self) -> None:
        self.root.title("Achan")
        self.root.geometry("540x720")
        self.root.resizable(False, False)
        self.root.minsize(540, 720)
        self.root.configure(bg=COLORS["bg"])
        try:
            icon = APP_DIR / "assets" / "achan.ico"
            if not icon.exists() and getattr(sys, "frozen", False):
                icon = Path(sys._MEIPASS) / "assets" / "achan.ico"
            if icon.exists():
                self.root.iconbitmap(str(icon))
        except Exception:
            pass

        base = tk.Frame(self.root, bg=COLORS["bg"], padx=22, pady=14)
        base.pack(fill="both", expand=True)

        header = tk.Frame(base, bg=COLORS["bg"])
        header.pack(fill="x", pady=(0, 14))
        logo = tk.Canvas(header, width=48, height=48, bg=COLORS["bg"], highlightthickness=0)
        logo.pack(side="left")
        logo.create_oval(2, 2, 46, 46, fill=COLORS["green_dim"], outline=COLORS["border"], width=1)
        logo.create_line(14, 30, 23, 13, 33, 30, fill=COLORS["green"], width=3, capstyle="round", joinstyle="round")
        logo.create_line(18, 25, 28, 25, fill=COLORS["green"], width=2, capstyle="round")
        brand = tk.Frame(header, bg=COLORS["bg"])
        brand.pack(side="left", padx=(11, 0), fill="y")
        tk.Label(brand, text="Achan", bg=COLORS["bg"], fg=COLORS["text"],
                 font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(brand, text="مدیریت هوشمند اتصال ویندوز", bg=COLORS["bg"], fg=COLORS["muted"],
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 1))
        tk.Label(header, text=f"v{APP_VERSION}", bg=COLORS["bg"], fg=COLORS["muted2"],
                 font=("Segoe UI", 8)).pack(side="right", anchor="n", pady=(8, 0))

        # Main connection card.
        connection = tk.Frame(base, bg=COLORS["panel"], highlightbackground=COLORS["border"], highlightthickness=1)
        connection.pack(fill="x")
        top = tk.Frame(connection, bg=COLORS["panel"], padx=17, pady=15)
        top.pack(fill="x")
        tk.Label(top, text="وضعیت اتصال", bg=COLORS["panel"], fg=COLORS["muted"],
                 font=("Segoe UI", 9)).pack(anchor="e")
        statusline = tk.Frame(top, bg=COLORS["panel"])
        statusline.pack(fill="x", pady=(4, 0))
        self.big_dot = tk.Canvas(statusline, width=17, height=17, bg=COLORS["panel"], highlightthickness=0)
        self.big_dot.pack(side="right", padx=(0, 7), pady=(4, 0))
        self.big_dot_id = self.big_dot.create_oval(3, 3, 14, 14, fill=COLORS["muted2"], outline="")
        self.status_title = tk.Label(statusline, text="خاموش", bg=COLORS["panel"], fg=COLORS["text"],
                                     font=("Segoe UI", 18, "bold"))
        self.status_title.pack(side="right")
        self.status_detail = tk.Label(top, text="آچان هنوز تونل شبکه را فعال نکرده است.", bg=COLORS["panel"],
                                      fg=COLORS["muted"], font=("Segoe UI", 9), anchor="e")
        self.status_detail.pack(anchor="e", pady=(3, 0))

        divider = tk.Frame(connection, bg=COLORS["border"], height=1)
        divider.pack(fill="x", padx=17)
        controls = tk.Frame(connection, bg=COLORS["panel"], padx=17, pady=10)
        controls.pack(fill="x")
        self.toggle = tk.Canvas(controls, width=112, height=48, bg=COLORS["panel"], highlightthickness=0,
                                cursor="hand2")
        self.toggle.pack(side="right")
        self.toggle.bind("<Button-1>", lambda _event: self.toggle_connection())
        self.toggle.bind("<space>", lambda _event: self.toggle_connection())
        self.toggle.bind("<Return>", lambda _event: self.toggle_connection())
        self.toggle.bind("<Enter>", lambda _event: self.toggle.configure(cursor="hand2"))
        self._draw_toggle(False)
        labels = tk.Frame(controls, bg=COLORS["panel"])
        labels.pack(side="right", padx=(0, 12), fill="y")
        self.control_title = tk.Label(labels, text="اتصال سراسری", bg=COLORS["panel"], fg=COLORS["text"],
                                      font=("Segoe UI", 10, "bold"))
        self.control_title.pack(anchor="e", pady=(3, 0))
        self.control_subtitle = tk.Label(labels, text="برای فعال‌سازی لمس کن", bg=COLORS["panel"],
                                         fg=COLORS["muted"], font=("Segoe UI", 8))
        self.control_subtitle.pack(anchor="e", pady=(2, 0))

        # Readiness checklist.
        stages_panel = tk.Frame(base, bg=COLORS["panel"], highlightbackground=COLORS["border"], highlightthickness=1)
        stages_panel.pack(fill="x", pady=(12, 0))
        panel_head = tk.Frame(stages_panel, bg=COLORS["panel"], padx=16, pady=10)
        panel_head.pack(fill="x")
        tk.Label(panel_head, text="مراحل راه‌اندازی", bg=COLORS["panel"], fg=COLORS["text"],
                 font=("Segoe UI", 10, "bold")).pack(side="right")
        tk.Label(panel_head, text="LIVE CHECK", bg=COLORS["panel"], fg=COLORS["muted2"],
                 font=("Segoe UI", 7, "bold")).pack(side="left")
        for key in ("engine", "proxy", "doh", "tunnel"):
            row_wrap = tk.Frame(stages_panel, bg=COLORS["panel"], padx=16, pady=5)
            row_wrap.pack(fill="x")
            row = StageRow(row_wrap, key)
            row.pack(fill="x")
            self.rows[key] = row
            if key != "tunnel":
                tk.Frame(stages_panel, bg=COLORS["border"], height=1).pack(fill="x", padx=16)

        ready_panel = tk.Frame(base, bg=COLORS["panel2"], highlightbackground=COLORS["border"], highlightthickness=1)
        ready_panel.pack(fill="x", pady=(11, 0))
        ready_inner = tk.Frame(ready_panel, bg=COLORS["panel2"], padx=15, pady=10)
        ready_inner.pack(fill="x")
        self.ready_badge = tk.Canvas(ready_inner, width=24, height=24, bg=COLORS["panel2"], highlightthickness=0)
        self.ready_badge.pack(side="right", padx=(0, 8))
        self.ready_circle = self.ready_badge.create_oval(2, 2, 22, 22, fill=COLORS["muted2"], outline="")
        self.ready_badge.create_line(7, 12, 10, 15, 17, 8, fill=COLORS["bg"], width=2, capstyle="round", joinstyle="round")
        self.ready_text = tk.Label(ready_inner, text="آماده استفاده نیست", bg=COLORS["panel2"],
                                   fg=COLORS["muted"], font=("Segoe UI", 10, "bold"))
        self.ready_text.pack(side="right")
        self.ready_hint = tk.Label(ready_inner, text="پس از سبز شدن همه مراحل، آماده‌ای.", bg=COLORS["panel2"],
                                   fg=COLORS["muted2"], font=("Segoe UI", 8))
        self.ready_hint.pack(side="left")

        info = tk.Frame(base, bg=COLORS["bg"])
        info.pack(fill="x", pady=(9, 0))
        self._chip(info, "DNS  ·  DoH").pack(side="right", padx=(0, 6))
        self._chip(info, "TCP  ·  TUN").pack(side="right", padx=(0, 6))
        self._chip(info, "127.0.0.1").pack(side="right")

        self.notice = tk.Label(base, text="", bg=COLORS["bg"], fg=COLORS["muted"],
                               font=("Segoe UI", 8), anchor="e", justify="right", wraplength=470)
        self.notice.pack(fill="x", pady=(7, 0))

        # Persistent bottom bar: attribution remains visible at every window size.
        disclaimer = tk.Label(base, text="آچان VPN نیست و IP عمومی را مخفی نمی‌کند؛ UDP ممکن است پشتیبانی نشود.",
                              bg=COLORS["bg"], fg=COLORS["muted2"], font=("Segoe UI", 7), anchor="center")
        disclaimer.pack(side="bottom", fill="x", pady=(8, 3))
        footer = tk.Frame(base, bg=COLORS["bg"])
        footer.pack(fill="x", side="bottom", pady=(3, 0))
        tk.Button(footer, text="گزارش تشخیصی", command=self.show_diagnostics, bg=COLORS["bg"],
                  fg=COLORS["muted"], activebackground=COLORS["panel"], activeforeground=COLORS["green"],
                  relief="flat", bd=0, font=("Segoe UI", 8), cursor="hand2").pack(side="right")
        tk.Label(footer, text="Made by Faraj", bg=COLORS["bg"], fg=COLORS["green"],
                 font=("Segoe UI", 9, "bold")).pack(side="left")

    def _chip(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(parent, text=text, bg=COLORS["panel2"], fg=COLORS["muted"],
                        font=("Segoe UI", 8), padx=9, pady=5, highlightbackground=COLORS["border"], highlightthickness=1)

    def _draw_toggle(self, enabled: bool, busy: bool = False) -> None:
        """Animate the switch thumb and track without blocking connection workers."""
        target = 1.0 if enabled else 0.0
        if busy:
            # During connection transitions, move toward the requested state but
            # keep the control visually muted until the operation is confirmed.
            target = 1.0 if self.state in {"starting", "running"} else 0.0
        self._toggle_target = target
        if self._toggle_anim_after is not None:
            try:
                self.root.after_cancel(self._toggle_anim_after)
            except Exception:
                pass
            self._toggle_anim_after = None
        self._toggle_anim_from = self._toggle_progress
        self._toggle_anim_started = time.monotonic()
        self._toggle_busy = busy
        self._animate_toggle_frame()

    @staticmethod
    def _mix_color(a: str, b: str, t: float) -> str:
        av = tuple(int(a[i:i+2], 16) for i in (1, 3, 5))
        bv = tuple(int(b[i:i+2], 16) for i in (1, 3, 5))
        values = tuple(round(x + (y - x) * t) for x, y in zip(av, bv))
        return "#%02X%02X%02X" % values

    def _animate_toggle_frame(self) -> None:
        duration = 0.24
        elapsed = min(1.0, (time.monotonic() - self._toggle_anim_started) / duration)
        # Cubic ease-out: quick response, gentle settle.
        eased = 1.0 - (1.0 - elapsed) ** 3
        value = self._toggle_anim_from + (self._toggle_target - self._toggle_anim_from) * eased
        self._toggle_progress = value
        self.toggle.delete("all")
        off = "#26352B"
        on = COLORS["green2"]
        track = self._mix_color(off, on, value)
        if getattr(self, "_toggle_busy", False):
            track = self._mix_color(track, "#304033", 0.42)
        self.toggle.create_oval(5, 5, 107, 43, fill=track, outline="")
        self.toggle.create_rectangle(24, 5, 88, 43, fill=track, outline="")
        knob_x = 28 + (84 - 28) * value
        self.toggle.create_oval(knob_x - 15, 9, knob_x + 15, 39,
                                fill=COLORS["text"], outline="")
        if getattr(self, "_toggle_busy", False):
            label = "..."
            text_x = 28 if value > 0.5 else 82
        else:
            label = "ON" if value >= 0.5 else "OFF"
            text_x = 28 if value >= 0.5 else 82
        self.toggle.create_text(text_x, 24, text=label,
                                fill=COLORS["bg"] if value >= 0.5 else COLORS["muted"],
                                font=("Segoe UI", 7, "bold"))
        if elapsed < 1.0:
            self._toggle_anim_after = self.root.after(16, self._animate_toggle_frame)
        else:
            self._toggle_anim_after = None
            self._toggle_progress = self._toggle_target

    def _set_notice(self, text: str, kind: str = "normal") -> None:
        color = COLORS["red"] if kind == "error" else COLORS["amber"] if kind == "warning" else COLORS["muted"]
        self.notice.configure(text=text, fg=color)

    def _log(self, message: str) -> None:
        LOGGER.info(message)

    def _stage_event(self, key: str, state: str, detail: str | None = None) -> None:
        self.events.put(("stage", key, state, detail))

    def _drain_events(self) -> None:
        try:
            while True:
                item = self.events.get_nowait()
                kind = item[0]
                if kind == "stage":
                    _, key, stage_state, detail = item
                    row = self.rows.get(key)
                    if row:
                        row.set_state(stage_state, detail)
                elif kind == "started":
                    self.state = "running"
                    self._render_state()
                    self._set_notice("تونل فعال است. می‌توانی از اینترنت استفاده کنی.")
                elif kind == "stopped":
                    self.state = "stopped"
                    for row in self.rows.values():
                        row.set_state("idle")
                    self._render_state()
                    self._set_notice("اتصال قطع شد؛ مسیر عادی ویندوز بازیابی شد.")
                elif kind == "stop_warning":
                    self._set_notice("تونل به‌طور کامل متوقف نشد؛ برای اطمینان یک‌بار ویندوز را Restart کن.", "warning")
                elif kind == "starting":
                    self.state = "starting"
                    self._render_state()
                    self._set_notice("در حال بررسی اجزای اتصال...")
                elif kind == "error":
                    _, message = item
                    self.state = "stopped"
                    pending_rows = [row for row in self.rows.values() if row.current_state == "checking"]
                    if pending_rows:
                        pending_rows[-1].set_state("error")
                    self._render_state()
                    self._set_notice(message, "error")
                    LOGGER.error("Connection startup failed: %s", message)
        except queue.Empty:
            pass
        if not self.closing:
            self.root.after(120, self._drain_events)

    def _render_state(self) -> None:
        if self.state == "running":
            self.status_title.configure(text="متصل", fg=COLORS["green"])
            self.status_detail.configure(text="اتصال سراسری آچان فعال است.")
            self.big_dot.itemconfigure(self.big_dot_id, fill=COLORS["green"])
            self.ready_badge.itemconfigure(self.ready_circle, fill=COLORS["green"])
            self.ready_text.configure(text="آماده استفاده", fg=COLORS["green"])
            self.ready_hint.configure(text="همه مراحل با موفقیت انجام شدند.")
            self.control_title.configure(text="اتصال فعال")
            self.control_subtitle.configure(text="برای بازگشت به حالت عادی خاموش کن")
            self._draw_toggle(True)
        elif self.state in {"starting", "stopping"}:
            title = "در حال اتصال..." if self.state == "starting" else "در حال قطع..."
            self.status_title.configure(text=title, fg=COLORS["amber"])
            self.status_detail.configure(text="لطفاً تا پایان عملیات، برنامه را نبند.")
            self.big_dot.itemconfigure(self.big_dot_id, fill=COLORS["amber"])
            self.ready_badge.itemconfigure(self.ready_circle, fill=COLORS["amber"])
            self.ready_text.configure(text="در حال بررسی", fg=COLORS["amber"])
            self.ready_hint.configure(text="مراحل اتصال در حال اجرا هستند.")
            self.control_title.configure(text="در حال اجرا")
            self.control_subtitle.configure(text="در حال آماده‌سازی شبکه")
            self._draw_toggle(self.state == "stopping", busy=True)
        else:
            self.status_title.configure(text="خاموش", fg=COLORS["text"])
            self.status_detail.configure(text="آچان هنوز تونل شبکه را فعال نکرده است.")
            self.big_dot.itemconfigure(self.big_dot_id, fill=COLORS["muted2"])
            self.ready_badge.itemconfigure(self.ready_circle, fill=COLORS["muted2"])
            self.ready_text.configure(text="آماده استفاده نیست", fg=COLORS["muted"])
            self.ready_hint.configure(text="پس از سبز شدن همه مراحل، آماده‌ای.")
            self.control_title.configure(text="اتصال سراسری")
            self.control_subtitle.configure(text="برای فعال‌سازی لمس کن")
            self._draw_toggle(False)

    def toggle_connection(self) -> None:
        if self.state in {"starting", "stopping"}:
            return
        if self.state == "running":
            self.stop_connection()
            return
        if not is_admin():
            self._request_admin_restart()
            return
        self.state = "starting"
        self._render_state()
        self.events.put(("starting", ""))
        threading.Thread(target=self._start_worker, name="AchanStart", daemon=True).start()

    def _request_admin_restart(self) -> None:
        """Ask for elevation only when the user turns the system tunnel on."""
        self._set_notice("برای ساخت تونل شبکه، تأیید دسترسی مدیر لازم است.", "warning")
        self.mutex.release()
        if getattr(sys, "frozen", False):
            executable = sys.executable
            params = "--autostart"
        else:
            executable = sys.executable
            params = subprocess.list2cmdline([str(Path(__file__).resolve()), "--autostart"])
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, str(APP_DIR), 1)
        if result <= 32:
            self.mutex.reacquire()
            if result == 5:
                self._set_notice("درخواست دسترسی مدیر لغو شد.", "warning")
            else:
                self._set_notice(f"درخواست دسترسی ویندوز انجام نشد (کد {result}).", "error")
            return
        self.closing = True
        self.root.after(200, self.root.destroy)

    def _start_worker(self) -> None:
        try:
            self.controller.start()
            self.events.put(("started", ""))
        except Exception as exc:
            LOGGER.exception("Start failed")
            self.events.put(("error", friendly_error(exc)))

    def stop_connection(self) -> None:
        if self.state != "running":
            return
        self.state = "stopping"
        self._render_state()
        self._set_notice("در حال بستن تونل و بازیابی مسیر قبلی شبکه...")
        threading.Thread(target=self._stop_worker, name="AchanStop", daemon=True).start()

    def _stop_worker(self) -> None:
        clean = False
        try:
            clean = self.controller.stop()
        except Exception:
            LOGGER.exception("Stop failed")
        self.events.put(("stopped", ""))
        if not clean:
            self.events.put(("stop_warning", ""))

    def _monitor(self) -> None:
        if self.state == "running" and not self.controller.is_running():
            LOGGER.error("Tunnel process exited unexpectedly")
            self.state = "stopping"
            self._render_state()
            self._set_notice("ارتباط تونل قطع شد؛ در حال پاک‌سازی تنظیمات شبکه...", "warning")
            threading.Thread(target=self._stop_worker, name="AchanRecovery", daemon=True).start()
        if not self.closing:
            self.root.after(900, self._monitor)

    def show_diagnostics(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Achan | Diagnostics")
        window.geometry("700x430")
        window.configure(bg=COLORS["bg"])
        window.transient(self.root)
        tk.Label(window, text="گزارش فنی برای عیب‌یابی", bg=COLORS["bg"], fg=COLORS["text"],
                 font=("Segoe UI", 12, "bold")).pack(anchor="e", padx=14, pady=(12, 6))
        box = scrolledtext.ScrolledText(window, bg="#050806", fg="#B8D8C2", insertbackground=COLORS["green"],
                                        relief="flat", bd=0, font=("Consolas", 9), wrap="word")
        box.pack(fill="both", expand=True, padx=14, pady=8)
        try:
            content = LOG_FILE.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = "هنوز گزارشی ثبت نشده است."
        box.insert("1.0", content[-70000:])
        box.configure(state="disabled")
        actions = tk.Frame(window, bg=COLORS["bg"])
        actions.pack(fill="x", padx=14, pady=(0, 12))
        def copy_log() -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(content[-70000:])
            messagebox.showinfo("Achan", rtl_text("گزارش در کلیپ‌بورد کپی شد."), parent=window)
        tk.Button(actions, text="کپی گزارش", command=copy_log, bg=COLORS["green_dim"], fg=COLORS["green"],
                  activebackground=COLORS["green2"], relief="flat", padx=14, pady=7,
                  font=("Segoe UI", 9, "bold")).pack(side="right")
        tk.Button(actions, text="باز کردن پوشه گزارش", command=lambda: os.startfile(str(LOG_DIR)), bg=COLORS["panel"],
                  fg=COLORS["text"], activebackground=COLORS["panel2"], relief="flat", padx=14, pady=7,
                  font=("Segoe UI", 9)).pack(side="right", padx=8)

    def close(self) -> None:
        if self.closing:
            return
        if self.state == "running":
            if not messagebox.askyesno(rtl_text("خروج از آچان"), rtl_text("اتصال فعال است. قطع اتصال و خروج انجام شود؟"), parent=self.root):
                return
            self.closing = True
            threading.Thread(target=self._close_worker, name="AchanClose", daemon=True).start()
            self._set_notice("در حال قطع اتصال پیش از خروج...")
            return
        if self.state in {"starting", "stopping"}:
            messagebox.showinfo("Achan", rtl_text("عملیات جاری را تا پایان متوقف نکن."), parent=self.root)
            return
        self.closing = True
        self.mutex.release()
        self.root.destroy()

    def _close_worker(self) -> None:
        try:
            clean = self.controller.stop()
            if not clean:
                LOGGER.warning("App closing after forced tunnel termination")
        finally:
            self.root.after(0, self._finish_close)

    def _finish_close(self) -> None:
        self.mutex.release()
        self.root.destroy()


def main() -> int:
    if sys.platform != "win32":
        print("Achan is designed for Windows 7 SP1 or later (x64).")
        return 2
    try:
        win_version = sys.getwindowsversion()
        if (win_version.major, win_version.minor) == (6, 1) and getattr(win_version, "service_pack_major", 0) < 1:
            print("Achan requires Windows 7 Service Pack 1 or later.")
            return 2
    except Exception:
        # Do not block supported Windows versions if version reporting is unavailable.
        pass
    mutex = SingleInstance()
    if mutex.already_running:
        messagebox.showwarning("Achan", rtl_text("آچان از قبل باز است."))
        mutex.release()
        return 0
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--autostart", action="store_true")
    args, _unknown = parser.parse_known_args()
    root = tk.Tk()
    AchanApp(root, mutex, auto_start=args.autostart)
    root.mainloop()
    mutex.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
