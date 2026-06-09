"""CodingCat – Screen / monitor utilities."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRect


def all_screen_geometry() -> list[QRect]:
    """Return available geometry for every connected monitor."""
    return [s.availableGeometry() for s in QApplication.screens()]


def primary_geometry() -> QRect:
    s = QApplication.primaryScreen()
    return s.availableGeometry() if s else QRect(0, 0, 1920, 1080)


def clamp_to_screens(x: int, y: int, w: int, h: int) -> tuple[int, int]:
    """Clamp (x,y) so a window of size (w,h) stays on some screen."""
    for geo in all_screen_geometry():
        if geo.contains(x, y):
            nx = max(geo.left(), min(x, geo.right() - w))
            ny = max(geo.top(), min(y, geo.bottom() - h))
            return nx, ny
    # Fallback: primary screen
    geo = primary_geometry()
    return (
        max(geo.left(), min(x, geo.right() - w)),
        max(geo.top(), min(y, geo.bottom() - h)),
    )
