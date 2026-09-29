"""
Mewly - Movement Manager

Walking is never spontaneous.  The cat only walks when something asks it to:
  - the user picks a "Walk" command (context menu / arrow keys), or
  - the user drops the cat partly outside the screen and it walks back in.

Movement is time based (pixels per second), so speed does not depend on the
timer rate, and positions are kept as floats to avoid jitter.  Bounds come
from the monitor the cat is currently on, so multi-monitor setups work.

The position is the window's top-left corner.  All sprite frames share one
bottom-centre anchor, so moving the window never makes the feet jump.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional, Tuple

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QGuiApplication

from config import EDGE_MARGIN

log = logging.getLogger("Mewly.movement")


def screen_rect_at(point: QPoint) -> QRect:
    """Available geometry of the monitor containing *point* (or the primary one)."""
    screen = QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()
    return screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)


class MovementManager:
    def __init__(self) -> None:
        self._x: float = 200.0
        self._y: float = 200.0
        self._w: int = 1
        self._h: int = 1
        self._target_x: Optional[float] = None
        self._speed: float = 0.0
        # The source art faces left; facing right mirrors flippable animations.
        self._facing_left: bool = True
        self._on_arrive: Optional[Callable[[], None]] = None

    # ── queries ──────────────────────────────────────────────────

    @property
    def x(self) -> int:
        return round(self._x)

    @property
    def y(self) -> int:
        return round(self._y)

    @property
    def is_walking(self) -> bool:
        return self._target_x is not None

    @property
    def target_x(self) -> Optional[float]:
        return self._target_x

    @property
    def facing_left(self) -> bool:
        return self._facing_left

    def bounds(self) -> Tuple[int, int]:
        """Valid [min_x, max_x] for the window's left edge on the current monitor."""
        scr = self._screen()
        lo = scr.left() + EDGE_MARGIN
        hi = scr.right() + 1 - self._w - EDGE_MARGIN
        return lo, max(lo, hi)

    # ── control ──────────────────────────────────────────────────

    def set_size(self, w: int, h: int) -> None:
        self._w, self._h = max(1, w), max(1, h)

    def set_position(self, x: float, y: float) -> None:
        """Hard position update (drag, restore, resize).  Does not stop a walk."""
        self._x, self._y = float(x), float(y)

    def walk_to(self, target_x: float, speed_px_s: float,
                on_arrive: Optional[Callable[[], None]] = None) -> None:
        lo, hi = self.bounds()
        target = min(max(float(target_x), lo), hi)
        if abs(target - self._x) < 1.0:
            self.stop()
            return
        self._target_x = target
        self._speed = speed_px_s
        self._facing_left = target < self._x
        self._on_arrive = on_arrive
        log.info("Walk  %.0f → %.0f  (%s)", self._x, target, "left" if self._facing_left else "right")

    def walk_by(self, dx: float, speed_px_s: float) -> None:
        base = self._target_x if self._target_x is not None else self._x
        self.walk_to(base + dx, speed_px_s)

    def stop(self) -> None:
        self._target_x = None
        self._on_arrive = None

    def update(self, dt_s: float) -> bool:
        """Advance a walk by *dt_s* seconds.  Returns True if the position changed."""
        if self._target_x is None or dt_s <= 0:
            return False
        step = self._speed * min(dt_s, 0.05)      # cap: no teleport after a stall
        dist = self._target_x - self._x
        if abs(dist) <= step:
            self._x = self._target_x
            cb = self._on_arrive
            self.stop()
            log.info("Walk arrived at x=%.0f", self._x)
            if cb:
                cb()
        else:
            self._x += step if dist > 0 else -step
        return True

    def clamp_vertical(self) -> None:
        """Keep the whole window vertically on its monitor (after a drop)."""
        scr = self._screen()
        top = scr.top()
        bottom = scr.bottom() + 1 - self._h
        self._y = float(min(max(self._y, top), max(top, bottom)))

    def out_of_bounds_x(self) -> Optional[float]:
        """If the window sticks out horizontally, the x it should walk back to."""
        lo, hi = self.bounds()
        if self._x < lo:
            return float(lo)
        if self._x > hi:
            return float(hi)
        return None

    def _screen(self) -> QRect:
        center = QPoint(round(self._x + self._w / 2), round(self._y + self._h / 2))
        return screen_rect_at(center)
