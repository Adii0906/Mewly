"""
Mewly - Animation Controller

The ONE authority over which animation is playing and which frame is shown.
Nothing else in the app advances frames or swaps frame lists.

- Time based: frames advance on elapsed milliseconds, not on timer ticks, so
  playback speed is exact regardless of how often the UI timer fires.
- play() of the animation that is already playing is a no-op, so callers can
  request the desired animation every tick without restarting it.
- One-shots play (repeat x frames), hold their last frame for hold_ms, then
  report completion exactly once from update().

Pure Python (no Qt) so it can be unit tested.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

from config import ANIMATIONS, AnimSpec, Frame

log = logging.getLogger("Mewly.anim")

# If the app stalls longer than this (system sleep, debugger), resync instead
# of fast-forwarding through dozens of frames.
_MAX_CATCH_UP_MS = 1000.0


class AnimationPlayer:
    def __init__(self, animations: Optional[Dict[str, AnimSpec]] = None, speed: float = 1.0) -> None:
        self._anims = animations if animations is not None else ANIMATIONS
        self._speed = max(0.05, speed)
        self._name: str = ""
        self._spec: Optional[AnimSpec] = None
        self._step: int = 0            # position in the (repeated) frame sequence
        self._next_due: float = 0.0    # ms timestamp of the next frame change
        self._finished: bool = False

    # ── queries ──────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def is_oneshot(self) -> bool:
        return self._spec is not None and not self._spec.loop

    @property
    def flippable(self) -> bool:
        return self._spec is not None and self._spec.flippable

    @property
    def frame(self) -> Frame:
        if self._spec is None:
            return ("idle", 0)
        frames = self._spec.frames
        return frames[self._step % len(frames)]

    def ms_until_next(self, now_ms: float) -> float:
        """Time until the next frame change (inf when nothing will change)."""
        if self._spec is None or self._finished:
            return float("inf")
        if self._spec.loop and len(self._spec.frames) < 2:
            return float("inf")
        return max(0.0, self._next_due - now_ms)

    # ── control ──────────────────────────────────────────────────

    def set_speed(self, speed: float) -> None:
        self._speed = max(0.05, speed)

    def play(self, name: str, now_ms: float, restart: bool = False) -> bool:
        """Switch to *name*.  Returns True if playback actually changed."""
        if name == self._name and not restart and not self._finished:
            return False
        spec = self._anims.get(name)
        if spec is None:
            log.warning("Unknown animation '%s' — ignored", name)
            return False
        self._name = name
        self._spec = spec
        self._step = 0
        self._finished = False
        self._next_due = now_ms + self._frame_ms(0)
        log.debug("play %s", name)
        return True

    def update(self, now_ms: float) -> Tuple[bool, Optional[str]]:
        """Advance to *now_ms*.  Returns (frame_changed, finished_oneshot_name)."""
        spec = self._spec
        if spec is None or self._finished:
            return False, None
        if now_ms - self._next_due > _MAX_CATCH_UP_MS:
            self._next_due = now_ms
        changed = False
        n = len(spec.frames)
        total = n * max(1, spec.repeat)
        while now_ms >= self._next_due:
            if spec.loop:
                if n < 2:
                    self._next_due = float("inf")
                    break
                self._step = (self._step + 1) % n
                changed = True
                self._next_due += self._frame_ms(self._step)
            else:
                if self._step + 1 < total:
                    self._step += 1
                    changed = True
                    self._next_due += self._frame_ms(self._step)
                else:
                    self._finished = True
                    return changed, self._name
        return changed, None

    # ── helpers ──────────────────────────────────────────────────

    def _frame_ms(self, step: int) -> float:
        spec = self._spec
        assert spec is not None
        ms = 1000.0 / (spec.fps * self._speed)
        if not spec.loop and step == len(spec.frames) * max(1, spec.repeat) - 1:
            ms += spec.hold_ms
        return ms
