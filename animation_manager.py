"""
CodingCat - Animation Manager (v3)

Slices each animation state from its sprite sheet using pixel-accurate
coordinates from config.SPRITE_CONFIGS.

Each state produces a list of QPixmap frames — one pixmap per frame.
The renderer (cat_widget) cycles through this list, displaying exactly
ONE frame at a time.  No all-at-once rendering.  No stacking.
"""
from __future__ import annotations
import os
import logging
from typing import Dict, List

from PIL import Image
from PyQt6.QtGui import QPixmap, QImage, QTransform

from config import SPRITE_CONFIGS, STATE_FALLBACK, CAT_DISPLAY_SIZE, SpriteConfig

log = logging.getLogger("CodingCat.anim")

_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_FLIP   = QTransform().scale(-1, 1)


def _remove_black_bg(img: Image.Image) -> Image.Image:
    """Make all near-black pixels (r<25, g<25, b<25) fully transparent."""
    img = img.convert("RGBA")
    data = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = data[x, y]
            if r < 25 and g < 25 and b < 25:
                data[x, y] = (0, 0, 0, 0)
    return img


def _to_pixmap(img: Image.Image, size: int) -> QPixmap:
    img = img.resize((size, size), Image.LANCZOS)
    raw = img.tobytes("raw", "RGBA")
    qi  = QImage(raw, img.width, img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qi)


class AnimationManager:
    """
    Loads sprite sheets once, slices every state into a list of QPixmaps.
    get_frames(state) returns that list — the renderer picks one at a time.
    """

    def __init__(self, display_size: int = CAT_DISPLAY_SIZE) -> None:
        self.display_size = display_size
        self._normal:  Dict[str, List[QPixmap]] = {}
        self._flipped: Dict[str, List[QPixmap]] = {}
        self._sheets:  Dict[str, Image.Image]   = {}
        self._load_sheets()
        self._slice_all()
        log.info("AnimationManager ready — states: %s", list(self._normal.keys()))

    # ── public ────────────────────────────────────────────────────

    def get_frames(self, state: str, flip: bool = False) -> List[QPixmap]:
        key = STATE_FALLBACK.get(state, state)
        src = self._flipped if flip else self._normal
        frames = src.get(key) or src.get("idle", [])
        if not frames:
            log.warning("No frames for state='%s' flip=%s", state, flip)
        return frames

    def available_states(self) -> List[str]:
        return list(self._normal.keys())

    # ── private ───────────────────────────────────────────────────

    def _load_sheets(self) -> None:
        for key, fname in [("basic", "sprite_basic.png"),
                            ("coding", "sprite_coding.png")]:
            path = os.path.join(_ASSETS, fname)
            if os.path.exists(path):
                self._sheets[key] = Image.open(path).convert("RGBA")
                log.debug("Sheet '%s' loaded (%s)", key, path)
            else:
                log.error("Sheet NOT found: %s", path)

    def _slice_all(self) -> None:
        for state, cfg in SPRITE_CONFIGS.items():
            sheet = self._sheets.get(cfg.sheet)
            if sheet is None:
                continue
            frames = self._slice_state(sheet, cfg)
            if frames:
                self._normal[state]  = frames
                self._flipped[state] = [f.transformed(_FLIP) for f in frames]
                log.debug("  %-7s  %d frames  slot_w=%d  x_start=%d",
                          state, len(frames), cfg.slot_w, cfg.x_start)
            else:
                log.warning("  %-7s  0 frames — skipped", state)

    def _slice_state(self, sheet: Image.Image, cfg: SpriteConfig) -> List[QPixmap]:
        frames: List[QPixmap] = []
        for i in range(cfg.num_frames):
            x0 = cfg.x_start + i * cfg.slot_w
            y0 = cfg.row_y
            x1 = x0 + cfg.slot_w
            y1 = y0 + cfg.row_h

            if x1 > sheet.width or y1 > sheet.height:
                log.warning("  %s frame %d out of bounds (x1=%d, sheet_w=%d)",
                            cfg.sheet, i, x1, sheet.width)
                break

            crop   = sheet.crop((x0, y0, x1, y1))
            crop   = _remove_black_bg(crop)
            pixmap = _to_pixmap(crop, self.display_size)
            frames.append(pixmap)

        return frames
