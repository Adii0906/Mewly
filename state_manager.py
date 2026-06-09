"""
CodingCat - State Manager  (v2)

Fixes:
- force_state() now IMMEDIATELY transitions without waiting for can_transition().
- Productivity state overrides are respected strictly; movement state can only
  win when no productivity override is active.
- Added full debug logging on every transition.
"""
from __future__ import annotations
import logging
from enum import Enum
from typing import Optional, Callable

log = logging.getLogger("CodingCat.state")


class CatState(str, Enum):
    IDLE    = "idle"
    WALK    = "walk"
    SLEEP   = "sleep"
    JUMP    = "jump"
    CODE    = "code"
    FOCUS   = "focus"
    TASK    = "task"
    DEBUG   = "debug"
    BREAK   = "break"
    LOAF    = "loaf"
    STRETCH = "stretch"
    GROOM   = "groom"
    BLINK   = "blink"


# States where the cat must not walk
STATIONARY_STATES = {
    CatState.SLEEP, CatState.CODE,  CatState.FOCUS,
    CatState.TASK,  CatState.DEBUG, CatState.BREAK,
    CatState.LOAF,  CatState.STRETCH, CatState.GROOM,
}

# Minimum ticks before we allow leaving a state
STATE_MIN_TICKS: dict[CatState, int] = {
    CatState.SLEEP:  80,
    CatState.JUMP:   12,
    CatState.TASK:   30,
    CatState.DEBUG:  30,
    CatState.BREAK:  50,
    CatState.CODE:   20,
    CatState.FOCUS:  20,
    CatState.WALK:    8,
}


class StateManager:
    def __init__(
        self,
        on_state_change: Optional[Callable[[CatState, CatState], None]] = None,
    ) -> None:
        self._state: CatState = CatState.IDLE
        self._ticks_in_state: int = 0
        self._forced: Optional[CatState] = None
        self._forced_remaining: int = 0
        self._productivity: Optional[CatState] = None
        self._on_change = on_state_change

    # ── Public ────────────────────────────────────────────────────

    @property
    def state(self) -> CatState:
        return self._state

    def force_state(self, state: CatState, duration_ticks: int = 60) -> None:
        """Immediately enter *state* for *duration_ticks* ticks, ignoring all else."""
        self._forced = state
        self._forced_remaining = duration_ticks
        self._do_transition(state)

    def set_productivity_state(self, state: Optional[CatState]) -> None:
        self._productivity = state

    def tick(self, movement_state: CatState) -> CatState:
        """Resolve state for this tick.  Returns the current state."""
        self._ticks_in_state += 1

        # Priority 1 — forced
        if self._forced is not None:
            self._forced_remaining -= 1
            if self._forced_remaining <= 0:
                self._forced = None
                self._ticks_in_state = 9999   # satisfy min-tick guard immediately
                log.debug("Force expired — resuming normal logic")
                # fall through to priority 2/3 immediately
            else:
                if self._state != self._forced:
                    self._do_transition(self._forced)
                return self._state

        # Priority 2 — productivity (IDE / keyboard / pomodoro)
        if self._productivity is not None:
            self._try_transition(self._productivity)
            return self._state

        # Priority 3 — movement / natural behaviour
        self._try_transition(movement_state)
        return self._state

    # ── Private ───────────────────────────────────────────────────

    def _try_transition(self, desired: CatState) -> None:
        if desired == self._state:
            return
        min_t = STATE_MIN_TICKS.get(self._state, 0)
        if self._ticks_in_state >= min_t:
            self._do_transition(desired)

    def _do_transition(self, new_state: CatState) -> None:
        if new_state == self._state:
            return
        old = self._state
        self._state = new_state
        self._ticks_in_state = 0
        log.info("Transition  %-8s → %-8s", old.value, new_state.value)
        if self._on_change:
            try:
                self._on_change(old, new_state)
            except Exception as exc:
                log.exception("on_state_change callback raised: %s", exc)
