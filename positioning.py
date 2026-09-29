"""
Mewly - Automatic positioning (deterministic, activity-driven)

Decides WHERE the cat should sit on its current monitor.  The monitor's work
area is split into thirds: "left", "center", "right".  The cat walks only
when it is not already in the target third, so it never moves without need.

    SLEEP          → stay where it is
    IDLE, BREAK    → center (keeping you company)
    CODE, FOCUS    → beside the active window, on the side with more free
                     screen space; if the window fills the screen → right

(Those are the defaults; Settings → Movement can map each activity to a
different keyword, see DEFAULT_MOVEMENT.)

It is re-evaluated only on a clear trigger: a base-state change, or a switch
of the foreground window (see main.py).  No randomness, no timers of its own.
"""
from __future__ import annotations

import sys
from typing import Dict, Optional, Tuple

from state_manager import CatState

Rect = Tuple[int, int, int, int]      # left, top, right, bottom

LEFT, CENTER, RIGHT = "left", "center", "right"

# The free strip beside the active window must be at least this fraction of
# the monitor width to count as room for the cat.
MIN_FREE_FRACTION = 0.12


def zone_of(x: float, lo: float, hi: float) -> str:
    """Which third of [lo, hi] the position *x* is in."""
    if hi <= lo:
        return CENTER
    f = (x - lo) / (hi - lo)
    if f < 1 / 3:
        return LEFT
    if f > 2 / 3:
        return RIGHT
    return CENTER


def zone_target(zone: str, lo: float, hi: float) -> float:
    return {LEFT: lo, RIGHT: hi}.get(zone, (lo + hi) / 2)


BESIDE, STAY = "beside", "stay"

# Movement keywords per activity (user-customisable in Settings).
#   "left" / "center" / "right" → that third of the screen
#   "beside"                    → next to the active window (coding only)
#   "stay"                      → don't move
DEFAULT_MOVEMENT = {"code": BESIDE, "idle": CENTER, "break": CENTER}
MOVEMENT_CHOICES = {
    "code":  (BESIDE, LEFT, CENTER, RIGHT, STAY),
    "idle":  (CENTER, LEFT, RIGHT, STAY),
    "break": (CENTER, LEFT, RIGHT, STAY),
}


def target_zone(state: CatState, fg_rect: Optional[Rect], work_rect: Optional[Rect],
                movement: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Where the cat belongs for *state*; None = stay put."""
    if state == CatState.SLEEP:
        return None
    prefs = {**DEFAULT_MOVEMENT, **(movement or {})}
    key = {CatState.IDLE: "idle", CatState.BREAK: "break"}.get(state, "code")
    choice = prefs[key] if prefs[key] in MOVEMENT_CHOICES[key] else DEFAULT_MOVEMENT[key]
    if choice == STAY:
        return None
    if choice in (LEFT, CENTER, RIGHT):
        return choice
    # "beside" (CODE / FOCUS): don't sit on top of the work — go beside the active window.
    if fg_rect and work_rect:
        wl, _, wr, _ = work_rect
        fl, _, fr, _ = fg_rect
        width = wr - wl
        if width > 0 and fr > wl and fl < wr:          # window is on the cat's monitor
            free_left = max(0, fl - wl)
            free_right = max(0, wr - fr)
            if max(free_left, free_right) >= width * MIN_FREE_FRACTION:
                return LEFT if free_left > free_right else RIGHT
    return RIGHT


class WindowGeometry:
    """Foreground-window and monitor rectangles (Windows only, physical pixels).

    Both rectangles come from Win32 in the same coordinate space, so they can
    be compared directly regardless of display scaling.  On other platforms
    every method returns None and CODE/FOCUS fall back to "right".
    """

    _SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}

    def __init__(self) -> None:
        self._ok = False
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes

            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                            ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

            u = ctypes.windll.user32
            u.GetForegroundWindow.restype = wintypes.HWND
            u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            u.GetWindowRect.restype = wintypes.BOOL
            u.IsIconic.argtypes = [wintypes.HWND]
            u.IsIconic.restype = wintypes.BOOL
            u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
            u.GetClassNameW.restype = ctypes.c_int
            u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            u.GetWindowThreadProcessId.restype = wintypes.DWORD
            u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
            u.MonitorFromWindow.restype = ctypes.c_void_p
            u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
            u.GetMonitorInfoW.restype = wintypes.BOOL
            try:
                dwm = ctypes.windll.dwmapi
                dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD,
                                                      ctypes.c_void_p, wintypes.DWORD]
                dwm.DwmGetWindowAttribute.restype = ctypes.c_long
            except Exception:
                dwm = None
            self._ctypes, self._wt, self._u, self._dwm = ctypes, wintypes, u, dwm
            self._MONITORINFO = MONITORINFO
            self._ok = True
        except Exception:
            self._ok = False

    def foreground_rect(self, own_pid: int) -> Optional[Rect]:
        """Visible bounds of the foreground app window (None for desktop/taskbar/us)."""
        if not self._ok:
            return None
        try:
            c, wt, u = self._ctypes, self._wt, self._u
            hwnd = u.GetForegroundWindow()
            if not hwnd or u.IsIconic(hwnd):
                return None
            buf = c.create_unicode_buffer(64)
            u.GetClassNameW(hwnd, buf, 64)
            if buf.value in self._SHELL_CLASSES:
                return None
            pid = wt.DWORD()
            u.GetWindowThreadProcessId(hwnd, c.byref(pid))
            if pid.value == own_pid:
                return None
            rect = wt.RECT()
            # DWMWA_EXTENDED_FRAME_BOUNDS (9) excludes the invisible resize border.
            if not (self._dwm and self._dwm.DwmGetWindowAttribute(
                    hwnd, 9, c.byref(rect), c.sizeof(rect)) == 0):
                if not u.GetWindowRect(hwnd, c.byref(rect)):
                    return None
            return rect.left, rect.top, rect.right, rect.bottom
        except Exception:
            return None

    def work_rect(self, hwnd: int) -> Optional[Rect]:
        """Work area (without taskbar) of the monitor showing window *hwnd*."""
        if not self._ok or not hwnd:
            return None
        try:
            c = self._ctypes
            mon = self._u.MonitorFromWindow(hwnd, 2)       # MONITOR_DEFAULTTONEAREST
            info = self._MONITORINFO()
            info.cbSize = c.sizeof(info)
            if not mon or not self._u.GetMonitorInfoW(mon, c.byref(info)):
                return None
            r = info.rcWork
            return r.left, r.top, r.right, r.bottom
        except Exception:
            return None
