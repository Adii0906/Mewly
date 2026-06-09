"""
CodingCat - Settings Manager
Loads/saves all user-configurable settings via SQLite.
"""
from __future__ import annotations
from dataclasses import dataclass
from storage import get_setting, set_setting
from config import DEFAULT_FPS, POMODORO_WORK_MINS, POMODORO_BREAK_MINS


@dataclass
class Settings:
    pos_x: int = 200
    pos_y: int = 200
    fps: int = DEFAULT_FPS
    volume: int = 50
    pomodoro_work_mins: int = POMODORO_WORK_MINS
    pomodoro_break_mins: int = POMODORO_BREAK_MINS
    display_size: int = 120
    always_on_top: bool = True


class SettingsManager:
    def __init__(self) -> None:
        self.settings = Settings()
        self.load()

    def load(self) -> None:
        s = self.settings
        s.pos_x            = int(get_setting("pos_x", s.pos_x))
        s.pos_y            = int(get_setting("pos_y", s.pos_y))
        s.fps              = int(get_setting("fps", s.fps))
        s.volume           = int(get_setting("volume", s.volume))
        s.pomodoro_work_mins  = int(get_setting("pomo_work", s.pomodoro_work_mins))
        s.pomodoro_break_mins = int(get_setting("pomo_break", s.pomodoro_break_mins))
        s.display_size     = int(get_setting("display_size", s.display_size))
        s.always_on_top    = get_setting("always_on_top", "1") == "1"

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
