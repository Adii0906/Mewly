"""
Mewly - Configuration

Everything that tunes the cat lives here.  Behaviour is fully deterministic:
there are no probabilities or random timers anywhere in the app.  Every
state change is caused by user activity, a user interaction, or a Pomodoro
event (see BEHAVIOR_SYSTEM.md).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Tuple

APP_NAME    = "Mewly"
APP_VERSION = "1.1.0"
DB_NAME     = "coding_cat.db"      # kept for backwards compatibility with saved settings


def resource_dir() -> str:
    """Directory holding bundled resources (works from source and PyInstaller)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


ASSETS_DIR  = os.path.join(resource_dir(), "assets")
SPRITES_DIR = os.path.join(ASSETS_DIR, "sprites")

# ── Display ───────────────────────────────────────────────────────────────────
# display_size = on-screen height of the sprite canvas in pixels.
CAT_DISPLAY_SIZE: int = 120
MIN_DISPLAY_SIZE: int = 60
MAX_DISPLAY_SIZE: int = 386        # 2x the native canvas height
# Space above the sprite reserved for the speech bubble / hearts.
BUBBLE_HEIGHT_RATIO: float = 0.22

# "Animation FPS" setting.  Each animation has its own authored speed (below);
# the user setting scales all of them: effective = anim_fps * fps / DEFAULT_FPS.
DEFAULT_FPS: int = 8
MIN_FPS:     int = 4
MAX_FPS:     int = 24

# ── Animations ────────────────────────────────────────────────────────────────
# A frame is (strip name, frame index) so an animation can reuse frames from
# several strips (e.g. the wake-up sequence).  All strips share one canvas
# with a common ground line, so mixing strips never moves the cat.
Frame = Tuple[str, int]


@dataclass(frozen=True)
class AnimSpec:
    frames: Tuple[Frame, ...]
    fps: float
    loop: bool = True
    repeat: int = 1          # one-shots: how many times to play the frame list
    hold_ms: int = 0         # one-shots: how long to hold the last frame
    flippable: bool = True   # False for art containing text/laptops


def _strip(name: str, count: int) -> Tuple[Frame, ...]:
    return tuple((name, i) for i in range(count))


ANIMATIONS: Dict[str, AnimSpec] = {
    # ── looping base states ──
    "idle":  AnimSpec(_strip("idle", 4),  fps=4),
    "code":  AnimSpec(_strip("code", 4),  fps=5, flippable=False),
    "focus": AnimSpec(_strip("focus", 4), fps=6, flippable=False),
    "sleep": AnimSpec(_strip("sleep", 4), fps=2),
    # Pomodoro break: coffee → yawn → yarn → lie down → doze, shown slowly.
    "break": AnimSpec(_strip("break", 5), fps=0.8, flippable=False),
    "walk":  AnimSpec(_strip("walk", 5),  fps=8),

    # ── one-shots ──
    "jump":  AnimSpec(_strip("jump", 4), fps=8, loop=False, hold_ms=150),
    "heart": AnimSpec((("idle", 3), ("idle", 2), ("idle", 3)), fps=3, loop=False, hold_ms=400),
    "task":  AnimSpec(_strip("task", 5), fps=3, loop=False, hold_ms=1200, flippable=False),
    "debug": AnimSpec(_strip("debug", 5), fps=4, loop=False, repeat=2, hold_ms=300, flippable=False),
    # sleep → yawn/stretch → sit up
    "wake":  AnimSpec((("sleep", 3), ("break", 1), ("break", 1), ("idle", 0)),
                      fps=4, loop=False, hold_ms=150, flippable=False),
}

# One-shot priority: a one-shot only interrupts another of LOWER priority.
ONESHOT_PRIORITY: Dict[str, int] = {
    "jump":  1,
    "heart": 2,
    "wake":  3,
    "debug": 4,
    "task":  5,
}

# ── Movement (walking is only ever started by an explicit event) ─────────────
WALK_SPEED_PX_PER_SEC: float = 110.0   # at the default display size
WALK_STEP_PX:          int   = 160     # arrow-key walk distance (default size)
EDGE_MARGIN:           int   = 4
# Automatic positioning: a new foreground window must stay active this long
# before the cat repositions for it.
WINDOW_SETTLE_MS:      int   = 2500

# ── Timing ────────────────────────────────────────────────────────────────────
MOVE_TICK_MS:      int = 16     # master timer while walking / fading text
MAX_IDLE_TICK_MS:  int = 500    # master timer upper bound when nothing moves
ACTIVITY_POLL_MS:  int = 1000   # activity sampling interval
AUTOSAVE_MS:       int = 30_000

# ── Activity classification ──────────────────────────────────────────────────
# Default inactivity before the cat falls asleep (user-configurable).
DEFAULT_SLEEP_AFTER_SECS: int = 120
MIN_SLEEP_AFTER_SECS:     int = 15
MAX_SLEEP_AFTER_SECS:     int = 3600

CODE_ENTER_KEYS:     int   = 4      # coding keystrokes within CODE_ENTER_WINDOW
CODE_ENTER_WINDOW:   float = 6.0    # seconds
CODE_GRACE_SECS:     float = 20.0   # keep CODE this long after the last coding keystroke
FOCUS_ENTER_KPM:     int   = 150    # coding keystrokes / minute to enter FOCUS
FOCUS_EXIT_KPM:      int   = 70     # ...and to stay in it (hysteresis)
FOCUS_MIN_CODE_SECS: float = 45.0   # CODE must have lasted this long before FOCUS
MIN_STATE_DWELL_SECS: float = 4.0   # anti-thrash: minimum time in a base state

# IDE executables (compared exactly, case-insensitive, without ".exe").
IDE_PROCESSES: FrozenSet[str] = frozenset({
    "code", "code - insiders", "code-insiders", "codium", "vscodium",
    "cursor", "windsurf",
})
IDE_SCAN_INTERVAL_SECS: float = 30.0   # fallback scan when the foreground app is unknown

# ── Pomodoro ──────────────────────────────────────────────────────────────────
POMODORO_WORK_MINS:  int = 25
POMODORO_BREAK_MINS: int = 5

# Reaction texts cycle in order (no randomness).
CLICK_REACTIONS: List[str] = ["meow!", "nyaa~", "purr ✨", "mrrp?"]
