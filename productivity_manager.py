"""
Mewly - Productivity Manager (activity sensing + Pomodoro)

Lightweight, Qt-thread activity sampling once per second:

- Time since last input:
    Windows  → GetLastInputInfo (system-wide keyboard + mouse, zero cost)
    others   → last keystroke (pynput) or cursor movement (QCursor polling)
- Keystrokes: a pynput keyboard hook that ONLY appends a timestamp under a
  lock.  No database writes or Qt calls happen on the hook thread; counts are
  drained on the Qt thread and flushed to SQLite in batches.
- Foreground app:
    Windows  → GetForegroundWindow → process name (cached per PID)
    others   → unknown; falls back to "an IDE is running" (scanned every 30 s)
  Keystrokes typed while an IDE is focused count as coding keystrokes.

Each sample goes through ActivityClassifier; state_changed is emitted only
when the base state actually changes.
"""
from __future__ import annotations

import logging
import sys
import threading
import time
from collections import deque
from typing import Deque, Dict, List, Optional

import psutil
from PyQt6.QtCore import QObject, QPoint, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor

from config import (
    ACTIVITY_POLL_MS, IDE_PROCESSES, IDE_SCAN_INTERVAL_SECS,
    POMODORO_WORK_MINS, POMODORO_BREAK_MINS, DEFAULT_SLEEP_AFTER_SECS,
)
from state_manager import ActivityClassifier, ActivitySample, CatState
from storage import log_session, increment_keystrokes

log = logging.getLogger("Mewly.activity")

try:
    from pynput import keyboard as _kb
    _PYNPUT_OK = True
except Exception:  # pragma: no cover - optional dependency / no display
    _PYNPUT_OK = False

_KEY_HISTORY_SECS = 60.0
_STATS_FLUSH_SECS = 30.0


def _normalise_exe(name: str) -> str:
    name = (name or "").strip().lower()
    return name[:-4] if name.endswith(".exe") else name


class _WinApi:
    """Tiny ctypes wrapper; every call fails soft and returns None."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        self._ctypes = ctypes
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32
        self._kernel32.GetTickCount.restype = wintypes.DWORD
        self._user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
        self._user32.GetLastInputInfo.restype = wintypes.BOOL
        # HWND is pointer-sized: without restype it would be truncated on 64-bit.
        self._user32.GetForegroundWindow.restype = wintypes.HWND
        self._user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self._lii = LASTINPUTINFO()
        self._lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        self._pid = wintypes.DWORD()

    def idle_seconds(self) -> Optional[float]:
        try:
            if not self._user32.GetLastInputInfo(self._ctypes.byref(self._lii)):
                return None
            # Both are 32-bit millisecond tick counts; mask handles wrap-around.
            elapsed = (self._kernel32.GetTickCount() - self._lii.dwTime) & 0xFFFFFFFF
            return elapsed / 1000.0
        except Exception:
            return None

    def foreground_window(self) -> int:
        try:
            return int(self._user32.GetForegroundWindow() or 0)
        except Exception:
            return 0

    def foreground_pid(self) -> Optional[int]:
        try:
            hwnd = self._user32.GetForegroundWindow()
            if not hwnd:
                return None
            self._user32.GetWindowThreadProcessId(hwnd, self._ctypes.byref(self._pid))
            return int(self._pid.value) or None
        except Exception:
            return None


class ProductivityManager(QObject):
    state_changed = pyqtSignal(object)             # CatState
    pomodoro_tick = pyqtSignal(int, int, str)       # remaining_secs, total_secs, phase
    pomodoro_event = pyqtSignal(str)                # "work_started" | "work_done" | "break_done" | "stopped"
    foreground_changed = pyqtSignal()               # the active window switched (Windows only)

    def __init__(self, sleep_after_secs: int = DEFAULT_SLEEP_AFTER_SECS, parent=None) -> None:
        super().__init__(parent)
        self._classifier = ActivityClassifier(sleep_after_secs)

        # keyboard hook → Qt thread hand-off
        self._lock = threading.Lock()
        self._pending_keys: List[float] = []
        self._listener = None

        # Qt-thread state
        self._last_input = time.monotonic()
        self._last_cursor: Optional[QPoint] = None
        self._coding_keys: Deque[float] = deque()
        self._unflushed_keys = 0
        self._last_flush = time.monotonic()
        self._exe_by_pid: Dict[int, str] = {}
        self._ide_running = False
        self._last_ide_scan = float("-inf")
        self._last_foreground = 0

        self._win: Optional[_WinApi] = None
        if sys.platform == "win32":
            try:
                self._win = _WinApi()
            except Exception as exc:
                log.warning("Win32 activity APIs unavailable: %s", exc)

        # Pomodoro
        self._pomo_running = False
        self._pomo_phase = "work"      # "work" | "break"
        self._pomo_end = 0.0
        self._pomo_work_secs = POMODORO_WORK_MINS * 60
        self._pomo_break_secs = POMODORO_BREAK_MINS * 60

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(ACTIVITY_POLL_MS)

        self._start_keyboard_listener()

    # ── public API ───────────────────────────────────────────────

    @property
    def state(self) -> CatState:
        return self._classifier.state

    @property
    def pomodoro_running(self) -> bool:
        return self._pomo_running

    def set_sleep_after(self, secs: int) -> None:
        self._classifier.sleep_after_secs = secs

    def note_user_input(self) -> None:
        """The user interacted with the cat itself: count as activity now."""
        self._last_input = time.monotonic()
        self._poll()

    def start_pomodoro(self) -> None:
        self._pomo_phase = "work"
        self._pomo_end = time.monotonic() + self._pomo_work_secs
        self._pomo_running = True
        self.pomodoro_event.emit("work_started")
        self._poll()

    def stop_pomodoro(self) -> None:
        if not self._pomo_running:
            return
        self._pomo_running = False
        self.pomodoro_event.emit("stopped")
        self._poll()

    def set_pomodoro_times(self, work_mins: int, break_mins: int) -> None:
        self._pomo_work_secs = work_mins * 60
        self._pomo_break_secs = break_mins * 60

    def shutdown(self) -> None:
        """Stop the timer and the keyboard hook thread; flush statistics."""
        self._poll_timer.stop()
        if self._listener is not None:
            try:
                self._listener.stop()
                self._listener.join(1.0)
            except Exception:
                pass
            self._listener = None
        self._drain_keys(time.monotonic(), None)
        self._flush_stats(force=True)

    # ── keyboard hook (runs on the pynput thread) ────────────────

    def _start_keyboard_listener(self) -> None:
        if not _PYNPUT_OK:
            log.info("pynput unavailable — keyboard activity not tracked")
            return

        def on_press(_key) -> None:
            t = time.monotonic()
            with self._lock:
                self._pending_keys.append(t)

        try:
            self._listener = _kb.Listener(on_press=on_press)
            self._listener.daemon = True
            self._listener.start()
        except Exception as exc:
            log.warning("Keyboard listener failed to start: %s", exc)
            self._listener = None

    # ── sampling (Qt thread) ─────────────────────────────────────

    def _poll(self) -> None:
        now = time.monotonic()
        in_ide = self._ide_in_focus(now)
        self._drain_keys(now, in_ide)
        self._sample_cursor(now)

        idle = now - self._last_input
        if self._win is not None:
            sys_idle = self._win.idle_seconds()
            if sys_idle is not None:
                idle = min(idle, sys_idle)

        on_break = self._update_pomodoro(now)

        cutoff = now - _KEY_HISTORY_SECS
        while self._coding_keys and self._coding_keys[0] < cutoff:
            self._coding_keys.popleft()

        old = self._classifier.state
        new = self._classifier.update(ActivitySample(
            now=now, idle_secs=idle, coding_key_times=self._coding_keys, on_break=on_break,
        ))
        if new != old:
            self.state_changed.emit(new)
        if self._win is not None:
            hwnd = self._win.foreground_window()
            if hwnd != self._last_foreground:
                self._last_foreground = hwnd
                self.foreground_changed.emit()
        self._flush_stats()

    def _drain_keys(self, now: float, in_ide: Optional[bool]) -> None:
        with self._lock:
            keys, self._pending_keys = self._pending_keys, []
        if not keys:
            return
        self._last_input = max(self._last_input, keys[-1])
        self._unflushed_keys += len(keys)
        if in_ide:
            self._coding_keys.extend(keys)

    def _sample_cursor(self, now: float) -> None:
        pos = QCursor.pos()
        if self._last_cursor is not None and pos != self._last_cursor:
            self._last_input = now
        self._last_cursor = pos

    def _ide_in_focus(self, now: float) -> bool:
        if self._win is not None:
            pid = self._win.foreground_pid()
            if pid is None:
                return False
            name = self._exe_by_pid.get(pid)
            if name is None:
                try:
                    name = _normalise_exe(psutil.Process(pid).name())
                except Exception:
                    name = ""
                if len(self._exe_by_pid) > 256:
                    self._exe_by_pid.clear()
                self._exe_by_pid[pid] = name
            return name in IDE_PROCESSES
        # Foreground app unknown on this platform: fall back to "IDE running".
        if now - self._last_ide_scan >= IDE_SCAN_INTERVAL_SECS:
            self._last_ide_scan = now
            self._ide_running = self._scan_ide_running()
        return self._ide_running

    @staticmethod
    def _scan_ide_running() -> bool:
        try:
            for proc in psutil.process_iter(["name"]):
                if _normalise_exe(proc.info["name"]) in IDE_PROCESSES:
                    return True
        except Exception:
            pass
        return False

    def _update_pomodoro(self, now: float) -> bool:
        """Advance the Pomodoro timer.  Returns True while on a break."""
        if not self._pomo_running:
            return False
        remaining = max(0, int(round(self._pomo_end - now)))
        total = self._pomo_work_secs if self._pomo_phase == "work" else self._pomo_break_secs
        self.pomodoro_tick.emit(remaining, total, self._pomo_phase)
        if now >= self._pomo_end:
            if self._pomo_phase == "work":
                log_session("pomodoro_work", self._pomo_work_secs)
                self._pomo_phase = "break"
                self._pomo_end = now + self._pomo_break_secs
                self.pomodoro_event.emit("work_done")
            else:
                log_session("pomodoro_break", self._pomo_break_secs)
                self._pomo_phase = "work"
                self._pomo_end = now + self._pomo_work_secs
                self.pomodoro_event.emit("break_done")
        return self._pomo_phase == "break"

    def _flush_stats(self, force: bool = False) -> None:
        now = time.monotonic()
        if self._unflushed_keys and (force or now - self._last_flush >= _STATS_FLUSH_SECS):
            increment_keystrokes(self._unflushed_keys)
            self._unflushed_keys = 0
            self._last_flush = now
