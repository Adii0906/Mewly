"""
CodingCat - Productivity Manager

Simple activity tracking:
- Keyboard activity → CODE state
- IDE active → CODE state  
- 10+ seconds inactivity → SLEEP state
"""
from __future__ import annotations
import time
from collections import deque
from typing import Optional, Deque
import psutil
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from config import (
    IDE_PROCESSES, ACTIVE_THRESHOLD_WPM,
    INACTIVITY_SLEEP_SECS, TYPING_WINDOW_SECS,
    POMODORO_WORK_MINS, POMODORO_BREAK_MINS,
)
from state_manager import CatState
from storage import log_session, increment_keystrokes

try:
    from pynput import keyboard as _kb
    _PYNPUT_OK = True
except Exception:
    _PYNPUT_OK = False


class ProductivityManager(QObject):
    """
    Simple activity monitoring for cat behavior.
    Emits state changes based on:
    - IDE active or typing → CODE
    - 10+ seconds inactivity → SLEEP
    - Otherwise → None (allows IDLE/WALK)
    """
    state_changed   = pyqtSignal(object)        # Optional[CatState]
    pomodoro_tick   = pyqtSignal(int, int, str)  # remaining_secs, total_secs, phase

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._keystroke_times: Deque[float] = deque()
        self._last_keypress: float = time.time()
        self._ide_active: bool = False
        self._current_state: Optional[CatState] = None
        self._listener = None

        # Pomodoro
        self._pomo_running: bool = False
        self._pomo_phase: str = "work"      # "work" | "break"
        self._pomo_end: float = 0.0
        self._pomo_work_secs: int = POMODORO_WORK_MINS * 60
        self._pomo_break_secs: int = POMODORO_BREAK_MINS * 60

        # Polling timer (1s)
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(1000)

        self._start_keyboard_listener()

    # ── Public API ────────────────────────────────────────────────────────────

    def start_pomodoro(self) -> None:
        self._pomo_phase = "work"
        self._pomo_end = time.time() + self._pomo_work_secs
        self._pomo_running = True

    def stop_pomodoro(self) -> None:
        self._pomo_running = False

    def set_pomodoro_times(self, work_mins: int, break_mins: int) -> None:
        self._pomo_work_secs = work_mins * 60
        self._pomo_break_secs = break_mins * 60

    def register_keystroke(self) -> None:
        now = time.time()
        self._last_keypress = now
        self._keystroke_times.append(now)
        increment_keystrokes()

    # ── Private ───────────────────────────────────────────────────────────────

    def _start_keyboard_listener(self) -> None:
        if not _PYNPUT_OK:
            return
        def on_press(key):
            self.register_keystroke()
        try:
            self._listener = _kb.Listener(on_press=on_press, daemon=True)
            self._listener.start()
        except Exception:
            pass

    def _wpm_estimate(self) -> float:
        now = time.time()
        cutoff = now - TYPING_WINDOW_SECS
        while self._keystroke_times and self._keystroke_times[0] < cutoff:
            self._keystroke_times.popleft()
        # Rough: 5 keystrokes ≈ 1 word
        return (len(self._keystroke_times) / 5) * (60 / TYPING_WINDOW_SECS)

    def _check_ide(self) -> bool:
        try:
            for proc in psutil.process_iter(["name"]):
                name = (proc.info["name"] or "").lower()
                if any(ide in name for ide in IDE_PROCESSES):
                    return True
        except Exception:
            pass
        return False

    def _poll(self) -> None:
        now = time.time()
        idle_secs = now - self._last_keypress
        wpm = self._wpm_estimate()
        self._ide_active = self._check_ide()

        # Pomodoro logic (highest priority)
        if self._pomo_running:
            remaining = max(0, int(self._pomo_end - now))
            total = self._pomo_work_secs if self._pomo_phase == "work" else self._pomo_break_secs
            self.pomodoro_tick.emit(remaining, total, self._pomo_phase)

            if remaining == 0:
                if self._pomo_phase == "work":
                    log_session("pomodoro_work", self._pomo_work_secs)
                    self._pomo_phase = "break"
                    self._pomo_end = now + self._pomo_break_secs
                    new_state = CatState.IDLE
                else:
                    log_session("pomodoro_break", self._pomo_break_secs)
                    self._pomo_phase = "work"
                    self._pomo_end = now + self._pomo_work_secs
                    new_state = CatState.CODE
                self._emit_state(new_state)
                return
            else:
                pomo_state = CatState.CODE if self._pomo_phase == "work" else CatState.IDLE
                self._emit_state(pomo_state)
                return

        # Simple state logic
        # Priority: CODE > SLEEP > IDLE/WALK
        
        # 10+ seconds inactivity → SLEEP
        if idle_secs >= INACTIVITY_SLEEP_SECS:
            self._emit_state(CatState.SLEEP)
        # IDE active or typing → CODE
        elif self._ide_active or wpm >= ACTIVE_THRESHOLD_WPM:
            self._emit_state(CatState.CODE)
        # Otherwise → None (allows IDLE/WALK/JUMP)
        else:
            self._emit_state(None)

    def _emit_state(self, state: Optional[CatState]) -> None:
        if state != self._current_state:
            self._current_state = state
            self.state_changed.emit(state)
