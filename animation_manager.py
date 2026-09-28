"""
Mewly - Animation Manager (sprite cache)

Loads the pre-processed sprite strips from assets/sprites/ (built offline by
tools/build_sprites.py) and serves scaled QPixmaps for (strip, index, flip).

Rendering rules:
- Every frame lives on the SAME canvas (manifest cell_w x cell_h) with the
  cat's feet on a common ground line and centred on a common vertical axis.
  Drawing every frame at the same position is therefore enough for perfect
  bottom-centre anchoring — no per-frame offsets at paint time.
- One uniform scale factor for all frames; aspect ratio is always preserved.
- Magnification uses nearest-neighbour (crisp pixels).  Minification uses
  Qt's area-averaging smooth scale: nearest-neighbour *downscaling* drops
  whole rows/columns of the outline and makes it shimmer between frames.
- Scaled/flipped pixmaps are built once per display size and cached.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap

from config import CAT_DISPLAY_SIZE, SPRITES_DIR

log = logging.getLogger("Mewly.sprites")


class AnimationManager:
    def __init__(self, display_size: int = CAT_DISPLAY_SIZE, sprites_dir: str = SPRITES_DIR) -> None:
        with open(os.path.join(sprites_dir, "manifest.json"), encoding="utf-8") as f:
            self._manifest = json.load(f)
        self.cell_w: int = self._manifest["cell_w"]
        self.cell_h: int = self._manifest["cell_h"]

        # Native-resolution frames, sliced once.
        self._native: Dict[str, List[QImage]] = {}
        for name, info in self._manifest["animations"].items():
            path = os.path.join(sprites_dir, info["file"])
            strip = QImage(path)
            if strip.isNull():
                log.error("Sprite strip missing or unreadable: %s", path)
                continue
            strip = strip.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            self._native[name] = [
                strip.copy(i * self.cell_w, 0, self.cell_w, self.cell_h)
                for i in range(info["frames"])
            ]
        log.info("Sprites loaded: %s", {k: len(v) for k, v in self._native.items()})

        self._cache: Dict[Tuple[str, int, bool], QPixmap] = {}
        self._dpr: float = 1.0
        self.display_size = 0
        self.set_display_size(display_size)

    # ── public ────────────────────────────────────────────────────

    @property
    def sprite_width(self) -> int:
        return max(1, round(self.cell_w * self.display_size / self.cell_h))

    @property
    def sprite_height(self) -> int:
        return self.display_size

    def set_display_size(self, size: int) -> None:
        if size == self.display_size:
            return
        self.display_size = max(1, int(size))
        self._cache.clear()

    def set_device_pixel_ratio(self, dpr: float) -> None:
        """Build pixmaps at physical resolution so HiDPI scaling adds no blur."""
        dpr = max(1.0, float(dpr))
        if abs(dpr - self._dpr) > 1e-3:
            self._dpr = dpr
            self._cache.clear()

    def pixmap(self, strip: str, index: int, flip: bool = False) -> QPixmap:
        key = (strip, index, flip)
        pm = self._cache.get(key)
        if pm is None:
            pm = self._build(strip, index, flip)
            self._cache[key] = pm
        return pm

    def has_strip(self, strip: str) -> bool:
        return strip in self._native

    # ── private ───────────────────────────────────────────────────

    def _build(self, strip: str, index: int, flip: bool) -> QPixmap:
        frames = self._native.get(strip) or self._native.get("idle")
        if not frames:
            pm = QPixmap(self.sprite_width, self.sprite_height)
            pm.fill(Qt.GlobalColor.transparent)
            return pm
        img = frames[index % len(frames)]
        if flip:
            # The canvas is symmetric around the anchor axis, so a mirrored
            # frame keeps the cat's feet exactly where they were.
            img = img.mirrored(True, False)
        # Physical pixel size; the logical size stays sprite_width x sprite_height.
        w = max(1, round(self.sprite_width * self._dpr))
        h = max(1, round(self.sprite_height * self._dpr))
        if (w, h) != (img.width(), img.height()):
            mode = (Qt.TransformationMode.FastTransformation if h >= img.height()
                    else Qt.TransformationMode.SmoothTransformation)
            img = img.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, mode)
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(self._dpr)
        return pm
