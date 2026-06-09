"""
CodingCat - Movement Manager  (v2)

Fixes:
- set_position() immediately syncs internal float state so drag release
  doesn't cause the cat to teleport back on the next tick.
- _start_walk() picks direction toward center of screen to avoid
  the cat getting stuck at one edge.
- All position arithmetic is in float; only exposed as int.
"""
from __future__ import annotations
import random
import logging
from enum import Enum

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRect

from config import (
    WALK_SPEED_MIN, WALK_SPEED_MAX,
    IDLE_PAUSE_MIN, IDLE_PAUSE_MAX,
    WALK_DURATION_MIN, WALK_DURATION_MAX,
    EDGE_MARGIN, PROB_START_WALKING,
    PROB_SLEEP_FROM_IDLE, PROB_JUMP,
    CAT_DISPLAY_SIZE,
)
from state_manager import CatState

log = logging.getLogger("CodingCat.movement")


class Direction(Enum):
    LEFT  = -1
    RIGHT =  1


class MovementManager:
    def __init__(self) -> None:
        self._x:    float = 200.0
        self._y:    float = 200.0
        self._dir:  Direction = Direction.RIGHT
        self._speed: float = random.uniform(WALK_SPEED_MIN, WALK_SPEED_MAX)

        self._is_walking:   bool = False
        self._walk_ticks:   int  = 0
        self._walk_target:  int  = 0
        self._idle_ticks:   int  = 0
        self._idle_target:  int  = random.randint(IDLE_PAUSE_MIN, IDLE_PAUSE_MAX)

    # ── Public ────────────────────────────────────────────────────

    @property
    def x(self) -> int:
        return int(self._x)

    @property
    def y(self) -> int:
        return int(self._y)

    @property
    def facing_left(self) -> bool:
        return self._dir == Direction.LEFT

    def set_position(self, x: int, y: int) -> None:
        """Called by drag handler — keeps internal state in sync."""
        self._x = float(x)
        self._y = float(y)

    def tick(self, locked: bool = False) -> CatState:
        """
        Advance one master-clock tick.
        *locked* = True when a productivity/forced state prevents walking.
        Returns the desired movement state for the state machine.
        """
        if locked:
            self._is_walking = False
            return CatState.IDLE

        screen = self._screen_rect()
        return self._do_walk(screen) if self._is_walking else self._do_idle()

    # ── Private ───────────────────────────────────────────────────

    def _do_walk(self, screen: QRect) -> CatState:
        new_x = self._x + self._dir.value * self._speed

        left_limit  = float(screen.left()  + EDGE_MARGIN)
        right_limit = float(screen.right() - CAT_DISPLAY_SIZE - EDGE_MARGIN)

        if new_x <= left_limit:
            new_x = left_limit
            self._dir = Direction.RIGHT
            log.debug("Edge bounce → RIGHT at x=%.0f", new_x)
        elif new_x >= right_limit:
            new_x = right_limit
            self._dir = Direction.LEFT
            log.debug("Edge bounce → LEFT  at x=%.0f", new_x)

        self._x = new_x
        self._walk_ticks += 1

        if self._walk_ticks >= self._walk_target:
            self._is_walking = False
            self._idle_ticks = 0
            self._idle_target = random.randint(IDLE_PAUSE_MIN, IDLE_PAUSE_MAX)
            log.debug("Walk done → IDLE  pos=(%.0f,%.0f)", self._x, self._y)
            return CatState.IDLE

        return CatState.WALK

    def _do_idle(self) -> CatState:
        self._idle_ticks += 1
        r = random.random()

        if r < PROB_JUMP:
            return CatState.JUMP

        if r < PROB_SLEEP_FROM_IDLE:
            return CatState.SLEEP

        if self._idle_ticks >= self._idle_target:
            self._idle_ticks = 0
            self._idle_target = random.randint(IDLE_PAUSE_MIN, IDLE_PAUSE_MAX)
            if random.random() < PROB_START_WALKING:
                self._start_walk()

        return CatState.IDLE

    def _start_walk(self) -> None:
        screen = self._screen_rect()
        center_x = screen.center().x()

        # Bias direction toward screen center so cat doesn't hug edges
        if self._x < center_x - 100:
            self._dir = Direction.RIGHT
        elif self._x > center_x + 100:
            self._dir = Direction.LEFT
        else:
            self._dir = random.choice([Direction.LEFT, Direction.RIGHT])

        self._is_walking  = True
        self._walk_ticks  = 0
        self._walk_target = random.randint(WALK_DURATION_MIN, WALK_DURATION_MAX)
        self._speed       = random.uniform(WALK_SPEED_MIN, WALK_SPEED_MAX)
        log.debug("Walk start  dir=%s  speed=%.1f  tgt=%d", self._dir.name, self._speed, self._walk_target)

    @staticmethod
    def _screen_rect() -> QRect:
        screen = QApplication.primaryScreen()
        return screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
