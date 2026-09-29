"""
Mewly - Settings Manager
Loads/saves all user-configurable settings via SQLite.
Values are validated on load so a corrupt or out-of-range entry can never
break startup.
"""
from __future__ import annotations

from dataclasses import dataclass

from config import (
    CAT_DISPLAY_SIZE, DEFAULT_FPS, MIN_FPS, MAX_FPS,
    MIN_DISPLAY_SIZE, MAX_DISPLAY_SIZE,
    POMODORO_WORK_MINS, POMODORO_BREAK_MINS,
    DEFAULT_SLEEP_AFTER_SECS, MIN_SLEEP_AFTER_SECS, MAX_SLEEP_AFTER_SECS,
)
from positioning import DEFAULT_MOVEMENT, MOVEMENT_CHOICES
from storage import get_setting, set_setting


@dataclass
class Settings:
    pos_x: int = 200
    pos_y: int = 200
    fps: int = DEFAULT_FPS
    volume: int = 50
    pomodoro_work_mins: int = POMODORO_WORK_MINS
    pomodoro_break_mins: int = POMODORO_BREAK_MINS
    display_size: int = CAT_DISPLAY_SIZE
    always_on_top: bool = True
    sleep_after_secs: int = DEFAULT_SLEEP_AFTER_SECS
    show_intro: bool = True                 # first-launch introduction window
    move_code: str = DEFAULT_MOVEMENT["code"]    # movement keyword while coding
    move_idle: str = DEFAULT_MOVEMENT["idle"]    # ...while idle
    move_break: str = DEFAULT_MOVEMENT["break"]  # ...on a Pomodoro break

    @property
    def movement(self) -> dict:
        return {"code": self.move_code, "idle": self.move_idle, "break": self.move_break}


def _choice(key: str, activity: str) -> str:
    value = str(get_setting(key, DEFAULT_MOVEMENT[activity]))
    return value if value in MOVEMENT_CHOICES[activity] else DEFAULT_MOVEMENT[activity]


def _int(key: str, default: int, lo: int, hi: int) -> int:
    try:
        value = int(float(get_setting(key, default)))
    except (TypeError, ValueError):
        return default
    return min(max(value, lo), hi)


class SettingsManager:
    def __init__(self) -> None:
        self.settings = Settings()
        self.load()

    def load(self) -> None:
        s = self.settings
        big = 1 << 30
        s.pos_x               = _int("pos_x", s.pos_x, -big, big)
        s.pos_y               = _int("pos_y", s.pos_y, -big, big)
        s.fps                 = _int("fps", s.fps, MIN_FPS, MAX_FPS)
        s.volume              = _int("volume", s.volume, 0, 100)
        s.pomodoro_work_mins  = _int("pomo_work", s.pomodoro_work_mins, 1, 90)
        s.pomodoro_break_mins = _int("pomo_break", s.pomodoro_break_mins, 1, 30)
        s.display_size        = _int("display_size", s.display_size, MIN_DISPLAY_SIZE, MAX_DISPLAY_SIZE)
        s.always_on_top       = str(get_setting("always_on_top", "1")) == "1"
        s.sleep_after_secs    = _int("sleep_after", s.sleep_after_secs,
                                     MIN_SLEEP_AFTER_SECS, MAX_SLEEP_AFTER_SECS)
        s.show_intro          = str(get_setting("show_intro", "1")) == "1"
        s.move_code           = _choice("move_code", "code")
        s.move_idle           = _choice("move_idle", "idle")
        s.move_break          = _choice("move_break", "break")

    def save(self) -> None:
        s = self.settings
        set_setting("pos_x",    s.pos_x)
        set_setting("pos_y",    s.pos_y)
        set_setting("fps",      s.fps)
        set_setting("volume",   s.volume)
        set_setting("pomo_work",  s.pomodoro_work_mins)
        set_setting("pomo_break", s.pomodoro_break_mins)
        set_setting("display_size", s.display_size)
        set_setting("always_on_top", "1" if s.always_on_top else "0")
        set_setting("sleep_after", s.sleep_after_secs)
        set_setting("show_intro", "1" if s.show_intro else "0")
        set_setting("move_code",  s.move_code)
        set_setting("move_idle",  s.move_idle)
        set_setting("move_break", s.move_break)
