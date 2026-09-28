"""
Mewly - State Manager

Two small, deterministic, Qt-free pieces:

ActivityClassifier
    Turns activity samples (time since last input, coding keystrokes,
    Pomodoro phase) into ONE base state: IDLE, CODE, FOCUS, SLEEP or BREAK.
    Uses thresholds, a grace period and hysteresis so the cat never
    thrashes between states.

CatBehavior
    Decides which animation should be on screen, with a strict priority:

        one-shot reaction  >  walking  >  base state

    One-shots (click, heart, wake, task, debug) always finish unless a
    higher-priority one-shot replaces them; base-state changes that happen
    meanwhile are remembered and shown when the one-shot ends.
    Waking up (SLEEP → anything) automatically plays the "wake" one-shot.

There is no randomness anywhere: every change has an explicit cause.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Sequence

from config import (
    CODE_ENTER_KEYS, CODE_ENTER_WINDOW, CODE_GRACE_SECS,
    FOCUS_ENTER_KPM, FOCUS_EXIT_KPM, FOCUS_MIN_CODE_SECS,
    MIN_STATE_DWELL_SECS, DEFAULT_SLEEP_AFTER_SECS, ONESHOT_PRIORITY,
)

log = logging.getLogger("Mewly.state")


class CatState(str, Enum):
    IDLE  = "idle"
    CODE  = "code"
    FOCUS = "focus"
    SLEEP = "sleep"
    BREAK = "break"


# Transitions between these three are debounced by MIN_STATE_DWELL_SECS.
_DEBOUNCED = {CatState.IDLE, CatState.CODE, CatState.FOCUS}


@dataclass
class ActivitySample:
    now: float                         # seconds (monotonic)
    idle_secs: float                   # since the last keyboard/mouse input
    coding_key_times: Sequence[float]  # timestamps of keystrokes made in an IDE (last ~60 s)
    on_break: bool = False             # Pomodoro break phase running


class ActivityClassifier:
    def __init__(self, sleep_after_secs: float = DEFAULT_SLEEP_AFTER_SECS) -> None:
        self.sleep_after_secs = sleep_after_secs
        self._state = CatState.IDLE
        self._since = float("-inf")         # when the current state was entered
        self._coding_since = 0.0            # start of the current CODE/FOCUS session

    @property
    def state(self) -> CatState:
        return self._state

    def update(self, s: ActivitySample) -> CatState:
        target = self._target(s)
        if target == self._state:
            return self._state
        debounced = self._state in _DEBOUNCED and target in _DEBOUNCED
        if debounced and s.now - self._since < MIN_STATE_DWELL_SECS:
            return self._state
        if target in (CatState.CODE, CatState.FOCUS) and self._state not in (CatState.CODE, CatState.FOCUS):
            self._coding_since = s.now
        log.info("Activity  %s → %s", self._state.value, target.value)
        self._state = target
        self._since = s.now
        return self._state

    def _target(self, s: ActivitySample) -> CatState:
        if s.on_break:
            return CatState.BREAK
        if s.idle_secs >= self.sleep_after_secs:
            return CatState.SLEEP

        keys = s.coding_key_times
        coding_now = self._state in (CatState.CODE, CatState.FOCUS)
        if coding_now:
            last = max(keys) if keys else float("-inf")
            coding = s.now - last <= CODE_GRACE_SECS
        else:
            coding = sum(1 for t in keys if t >= s.now - CODE_ENTER_WINDOW) >= CODE_ENTER_KEYS
        if not coding:
            return CatState.IDLE

        kpm = sum(1 for t in keys if t >= s.now - 60.0)
        if self._state == CatState.FOCUS:
            return CatState.FOCUS if kpm >= FOCUS_EXIT_KPM else CatState.CODE
        if (self._state == CatState.CODE
                and s.now - self._coding_since >= FOCUS_MIN_CODE_SECS
                and kpm >= FOCUS_ENTER_KPM):
            return CatState.FOCUS
        return CatState.CODE


class CatBehavior:
    """Resolves the animation to show.  Owns no timers."""

    def __init__(self, on_change: Optional[Callable[[str], None]] = None) -> None:
        self._base = CatState.IDLE
        self._oneshot: Optional[str] = None
        self._walking = False
        self._on_change = on_change
        self._shown = self.animation()

    # ── queries ──────────────────────────────────────────────────

    @property
    def base(self) -> CatState:
        return self._base

    @property
    def oneshot(self) -> Optional[str]:
        return self._oneshot

    @property
    def movement_paused(self) -> bool:
        """Walking pauses while a one-shot plays and resumes afterwards."""
        return self._oneshot is not None

    def animation(self) -> str:
        if self._oneshot is not None:
            return self._oneshot
        if self._walking:
            return "walk"
        return self._base.value

    # ── events ───────────────────────────────────────────────────

    def set_listener(self, on_change: Callable[[str], None]) -> None:
        self._on_change = on_change

    def set_base(self, state: CatState) -> None:
        if state == self._base:
            return
        old, self._base = self._base, state
        log.info("Base  %s → %s", old.value, state.value)
        if old == CatState.SLEEP:
            self.trigger("wake")
        self._notify()

    def trigger(self, name: str) -> bool:
        """Start a one-shot.  Returns False if a higher/equal one is playing."""
        if self._oneshot is not None:
            if ONESHOT_PRIORITY.get(name, 0) <= ONESHOT_PRIORITY.get(self._oneshot, 0):
                log.debug("One-shot %s ignored (playing %s)", name, self._oneshot)
                return False
        self._oneshot = name
        log.info("One-shot  %s", name)
        self._notify()
        return True

    def oneshot_finished(self, name: str) -> None:
        if self._oneshot == name:
            self._oneshot = None
            self._notify()

    def set_walking(self, walking: bool) -> None:
        if walking != self._walking:
            self._walking = walking
            self._notify()

    def _notify(self) -> None:
        anim = self.animation()
        if anim != self._shown:
            self._shown = anim
            if self._on_change:
                self._on_change(anim)
