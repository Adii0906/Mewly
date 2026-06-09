"""
CodingCat - Configuration

A simple, natural companion cat behavior system.
States: CODE (typing), IDLE (present), WALK (occasional), SLEEP (inactive)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

APP_NAME    = "CodingCat"
APP_VERSION = "1.0.0"
DB_NAME     = "coding_cat.db"

# ── Display ───────────────────────────────────────────────────────────────────
CAT_DISPLAY_SIZE: int = 120
DEFAULT_FPS:      int = 8
MIN_FPS:          int = 4
MAX_FPS:          int = 24

# ── Movement ──────────────────────────────────────────────────────────────────
WALK_SPEED_MIN:    float = 1.5
WALK_SPEED_MAX:    float = 3.5
IDLE_PAUSE_MIN:    int   = 60
IDLE_PAUSE_MAX:    int   = 200
WALK_DURATION_MIN: int   = 40
WALK_DURATION_MAX: int   = 120
EDGE_MARGIN:       int   = 10
PROB_START_WALKING:   float = 0.008
PROB_SLEEP_FROM_IDLE: float = 0.003
PROB_JUMP:            float = 0.002

# ── Activity Detection ────────────────────────────────────────────────────
# Keyboard and IDE tracking for simple state determination
TYPING_WINDOW_SECS:    int = 5      # Window for WPM calculation
ACTIVE_THRESHOLD_WPM:  int = 1      # Any typing = active
INACTIVITY_SLEEP_SECS: int = 10     # Sleep after 10 seconds of inactivity

# IDEs that indicate "coding" activity
IDE_PROCESSES: List[str] = ["code", "cursor", "windsurf", "code - insiders"]

# Pomodoro configuration
POMODORO_WORK_MINS:    int = 25
POMODORO_BREAK_MINS:   int = 5

# ── Sprite layout ─────────────────────────────────────────────────────────────
# Measured pixel-accurately from the actual sprite sheets.
#
# sprite_basic.png  (1536 x 1024)
#   Label badge occupies x=0..329 on every row.
#   Frames begin at x_start; each slot is slot_w pixels wide.
#
# sprite_coding.png (1535 x 1024)
#   Label badge occupies x=0..339 on every row.
#   Same principle.
#
@dataclass
class SpriteConfig:
    sheet:      str   # "basic" | "coding"
    row_y:      int   # top pixel of this animation row
    row_h:      int   # height of the row in pixels
    x_start:    int   # x coordinate of the FIRST frame slot
    slot_w:     int   # width of every frame slot (uniform per state)
    num_frames: int   # how many frames to extract

SPRITE_CONFIGS: Dict[str, SpriteConfig] = {
    # ── sprite_basic.png ─────────────────────────────────────────
    # Row 0  IDLE  (4 frames, cats at ~382-1190)
    "idle":  SpriteConfig("basic",   0,   256, 330, 216, 4),
    # Row 1  WALK  (5 frames, cats at ~363-1258)
    "walk":  SpriteConfig("basic", 256,   256, 330, 187, 5),
    # Row 2  SLEEP (4 frames, cats at ~371-1140)
    "sleep": SpriteConfig("basic", 512,   256, 330, 203, 4),
    # Row 3  JUMP  (4 frames, cats at ~373-1112)
    "jump":  SpriteConfig("basic", 768,   256, 330, 196, 4),

    # ── sprite_coding.png ────────────────────────────────────────
    # Row 0  CODE  (4 frames, cats at ~357-1239)
    "code":  SpriteConfig("coding",  0,   208, 340, 226, 4),
    # Row 1  FOCUS (4 frames, cats at ~357-1264)
    "focus": SpriteConfig("coding", 208,  210, 340, 232, 4),
    # Row 2  TASK  (5 frames, cats at ~348-1359)
    "task":  SpriteConfig("coding", 418,  205, 340, 205, 5),
    # Row 3  DEBUG (5 frames, cats at ~358-1362)
    "debug": SpriteConfig("coding", 623,  201, 340, 205, 5),
    # Row 4  BREAK (5 frames, cats at ~363-1378)
    "break": SpriteConfig("coding", 824,  200, 340, 208, 5),
}

# Virtual states that fall back to a real animation
STATE_FALLBACK: Dict[str, str] = {
    "loaf":    "idle",
    "stretch": "idle",
    "groom":   "idle",
    "blink":   "idle",
    "focus":   "code",
    "task":    "jump",
    "break":   "idle",
    "debug":   "code",
}

# Animation speed (FPS) per state — calm and natural
STATE_FPS_OVERRIDE: Dict[str, int] = {
    "idle":   6,    # Calm, relaxed
    "sleep":  4,    # Slow and peaceful
    "walk":   8,    # Natural pace
    "code":   7,    # Attentive but calm
    "jump":   10,   # Quick burst
}
