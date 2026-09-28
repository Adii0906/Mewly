"""
Mewly - offline sprite builder.

Turns the two hand-authored sprite sheets in ``assets/source/`` into clean,
game-ready animation strips in ``assets/sprites/`` plus a ``manifest.json``.

Why this exists
---------------
The source sheets are JPEG images (no alpha channel) on a black background,
with a text badge on the left of every row and frames that are *not* evenly
spaced (some walk frames even touch each other).  Slicing them at runtime with
fixed slot widths cut feet and tails off, bled neighbouring frames into each
other, and keyed out the dark outlines together with the background.

This tool does the work once, offline, and deterministically:

1. Background key: flood-fill from the sheet border through near-black
   pixels.  Only black that is *connected to the outside* becomes
   transparent, so dark pixels inside the cat (eyes, laptop, outline)
   are kept.
2. Frame detection: connected components per animation row.  Large
   components are cat bodies; small ones (sparkles, "zZ", "?!") are attached
   to the nearest body.  Bodies that touch are split along a minimum-cost
   vertical seam.
3. Anchoring: every frame is placed on ONE shared canvas so that its
   feet (bottom of the body) sit on the same ground line and its feet
   centre sits on the canvas centre line.  Switching between any two
   frames or animations therefore never moves the cat.
4. Output: one horizontal PNG strip per animation (uniform cell size),
   fully transparent background, no resampling (no quality loss).

Usage::

    python tools/build_sprites.py

Pillow is used to decode the source JPEGs.  If Pillow is not installed you
can pass raw RGBA dumps with ``--raw`` (``<name>.rgba``: a text header
``"<w> <h>\\n"`` followed by w*h*4 bytes).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from png_io import Image, write_png  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "assets", "source")
OUT_DIR = os.path.join(ROOT, "assets", "sprites")

# Pixels whose R, G and B are all <= this and that are connected to the sheet
# border are background.  40 removes JPEG noise and the barely-visible ground
# haze of the basic sheet while keeping the maroon outline (~75,17,16).
BG_THRESHOLD = 40
# Label badges occupy the left part of every row.
BADGE_RIGHT = 340
# Components smaller than this are JPEG specks.
MIN_SPECK_AREA = 25
# Components at least this big are cat bodies.
MIN_BODY_AREA = 5000
# Transparent padding around the shared canvas.
PAD = 2
# Half the thickness of the coding sheet's drawn ground shadow.
SHADOW_INSET = 4
# Height (fraction of the frame) used to find the feet centre.
FEET_BAND = 0.12


@dataclass
class Row:
    name: str
    sheet: str
    y0: int
    y1: int
    frames: int
    # "frame": each frame's own feet sit on the ground (kills art jitter).
    # "row":   frames keep their vertical offset within the row (jump arc).
    ground: str = "frame"
    # The coding sheet draws a ground shadow under the cat; its feet rest on
    # the middle of that shadow, not its bottom edge.
    ground_inset: int = 0


ROWS: List[Row] = [
    Row("idle", "basic", 90, 300, 4),
    Row("walk", "basic", 340, 520, 5),
    Row("sleep", "basic", 560, 740, 4),
    Row("jump", "basic", 770, 940, 4, ground="row"),
    Row("code", "coding", 20, 215, 4, ground_inset=SHADOW_INSET),
    Row("focus", "coding", 225, 430, 4, ground_inset=SHADOW_INSET),
    Row("task", "coding", 440, 640, 5, ground_inset=SHADOW_INSET),
    Row("debug", "coding", 650, 835, 5, ground_inset=SHADOW_INSET),
    Row("break", "coding", 845, 1020, 5, ground_inset=SHADOW_INSET),
]


@dataclass
class Frame:
    pixels: List[Tuple[int, int]] = field(default_factory=list)  # (x, y) on sheet
    x0: int = 0
    y0: int = 0
    x1: int = 0
    y1: int = 0
    ground: int = 0
    anchor_x: int = 0

    def bbox(self) -> None:
        xs = [p[0] for p in self.pixels]
        ys = [p[1] for p in self.pixels]
        self.x0, self.x1 = min(xs), max(xs) + 1
        self.y0, self.y1 = min(ys), max(ys) + 1


# ── loading ──────────────────────────────────────────────────────────────────

def load_sheet(path: str, raw: Optional[str]) -> Image:
    if raw:
        with open(raw, "rb") as f:
            data = f.read()
        header, body = data.split(b"\n", 1)
        w, h = map(int, header.split())
        return Image(w, h, bytearray(body))
    from PIL import Image as PILImage  # type: ignore

    with PILImage.open(path) as im:
        im = im.convert("RGBA")
        return Image(im.width, im.height, bytearray(im.tobytes()))


# ── background key ───────────────────────────────────────────────────────────

def background_mask(img: Image) -> bytearray:
    w, h, d = img.width, img.height, img.data
    t = BG_THRESHOLD
    dark = bytearray(w * h)
    for i in range(w * h):
        j = i * 4
        if d[j] <= t and d[j + 1] <= t and d[j + 2] <= t:
            dark[i] = 1
    bg = bytearray(w * h)
    stack = list(range(w)) + [i + (h - 1) * w for i in range(w)]
    stack += [y * w for y in range(h)] + [y * w + w - 1 for y in range(h)]
    while stack:
        i = stack.pop()
        if bg[i] or not dark[i]:
            continue
        bg[i] = 1
        x = i % w
        if x > 0:
            stack.append(i - 1)
        if x < w - 1:
            stack.append(i + 1)
        if i >= w:
            stack.append(i - w)
        if i < w * (h - 1):
            stack.append(i + w)
    # The label badges are not part of any animation.
    for y in range(h):
        for x in range(min(BADGE_RIGHT, w)):
            bg[y * w + x] = 1
    return bg


def components(img: Image, bg: bytearray, y0: int, y1: int) -> List[List[Tuple[int, int]]]:
    """8-connected foreground components whose pixels lie within rows y0..y1."""
    w = img.width
    seen = bytearray(w * img.height)
    out: List[List[Tuple[int, int]]] = []
    for y in range(y0, y1):
        for x in range(w):
            s = y * w + x
            if bg[s] or seen[s]:
                continue
            seen[s] = 1
            stack = [s]
            pix: List[Tuple[int, int]] = []
            while stack:
                i = stack.pop()
                cx, cy = i % w, i // w
                pix.append((cx, cy))
                for dy in (-1, 0, 1):
                    yy = cy + dy
                    if yy < y0 or yy >= y1:
                        continue
                    for dx in (-1, 0, 1):
                        xx = cx + dx
                        if 0 <= xx < w:
                            k = yy * w + xx
                            if not bg[k] and not seen[k]:
                                seen[k] = 1
                                stack.append(k)
            out.append(pix)
    return out


# ── frame detection ──────────────────────────────────────────────────────────

def split_frame(img: Image, fr: Frame, parts: int) -> List[Frame]:
    """Split a frame containing *parts* touching cats along min-cost seams.

    Cutting through background is free, cutting through the dark outline is
    cheap and cutting through bright fill is expensive, so the seam follows
    the outline that separates one cat's tail from the next cat's cheek.
    """
    fr.bbox()
    occ: Dict[Tuple[int, int], float] = {}
    for (x, y) in fr.pixels:
        r, g, b, _ = img.get(x, y)
        occ[(x, y)] = 0.15 + (r + g + b) / 765.0
    width = fr.x1 - fr.x0
    seams: List[Dict[int, int]] = []
    search = max(8, width // (parts * 4))
    for k in range(1, parts):
        guess = fr.x0 + round(k * width / parts)
        lo, hi = guess - search, guess + search
        xs = range(lo, hi + 1)
        # DP over rows: seam may move one column per row.
        cost = {x: occ.get((x, fr.y0), 0.0) + abs(x - guess) * 1e-3 for x in xs}
        back: List[Dict[int, int]] = []
        for y in range(fr.y0 + 1, fr.y1):
            ncost, nback = {}, {}
            for x in xs:
                best, bx = None, x
                for px in (x - 1, x, x + 1):
                    if px in cost and (best is None or cost[px] < best):
                        best, bx = cost[px], px
                ncost[x] = best + occ.get((x, y), 0.0) + abs(x - guess) * 1e-3
                nback[x] = bx
            cost = ncost
            back.append(nback)
        x = min(cost, key=cost.get)
        seam = {fr.y1 - 1: x}
        for y in range(fr.y1 - 1, fr.y0, -1):
            x = back[y - fr.y0 - 1][x]
            seam[y - 1] = x
        seams.append(seam)
    out = [Frame() for _ in range(parts)]
    for (x, y) in fr.pixels:
        idx = sum(1 for s in seams if x >= s[y])
        out[idx].pixels.append((x, y))
    return out


def detect_frames(img: Image, bg: bytearray, row: Row) -> List[Frame]:
    comps = [c for c in components(img, bg, row.y0, row.y1) if len(c) >= MIN_SPECK_AREA]
    bodies = [Frame(pixels=c) for c in comps if len(c) >= MIN_BODY_AREA]
    extras = [Frame(pixels=c) for c in comps if len(c) < MIN_BODY_AREA]
    for f in bodies + extras:
        f.bbox()
    bodies.sort(key=lambda f: f.x0)

    while len(bodies) < row.frames:
        widths = sorted(f.x1 - f.x0 for f in bodies)
        typical = widths[0] if len(widths) > 1 else widths[0] / row.frames
        widest = max(bodies, key=lambda f: f.x1 - f.x0)
        parts = max(2, min(row.frames - len(bodies) + 1,
                           round((widest.x1 - widest.x0) / typical)))
        bodies.remove(widest)
        bodies.extend(split_frame(img, widest, parts))
        for f in bodies:
            f.bbox()
        bodies.sort(key=lambda f: f.x0)
    if len(bodies) != row.frames:
        raise SystemExit(f"{row.name}: expected {row.frames} frames, found {len(bodies)}")

    # Ground/feet are measured on the body alone, before sparkles are attached.
    for f in bodies:
        f.ground = f.y1 - row.ground_inset
        band = max(2, int((f.y1 - f.y0) * FEET_BAND))
        feet = [x for (x, y) in f.pixels if y >= f.y1 - band]
        f.anchor_x = round(sum(feet) / len(feet))

    for e in extras:
        cx = (e.x0 + e.x1) / 2

        def gap(f: Frame) -> float:
            if f.x0 <= cx < f.x1:
                return 0.0
            return min(abs(cx - f.x0), abs(cx - f.x1))
        min(bodies, key=gap).pixels.extend(e.pixels)
    for f in bodies:
        f.bbox()

    if row.ground == "row":
        g = max(f.ground for f in bodies)
        for f in bodies:
            f.ground = g
    return bodies


# ── output ───────────────────────────────────────────────────────────────────

def build(raw_dir: Optional[str]) -> None:
    sheets: Dict[str, Image] = {}
    masks: Dict[str, bytearray] = {}
    for key in ("basic", "coding"):
        path = os.path.join(SRC_DIR, f"sprite_{key}.jpg")
        raw = os.path.join(raw_dir, f"sprite_{key}.rgba") if raw_dir else None
        sheets[key] = load_sheet(path, raw)
        masks[key] = background_mask(sheets[key])
        print(f"loaded {key}: {sheets[key].width}x{sheets[key].height}")

    frames: Dict[str, List[Frame]] = {}
    for row in ROWS:
        frames[row.name] = detect_frames(sheets[row.sheet], masks[row.sheet], row)
        print(f"{row.name:6s} " + " ".join(
            f"[{f.x0}-{f.x1} gnd={f.ground} ax={f.anchor_x}]" for f in frames[row.name]))

    all_frames = [f for fs in frames.values() for f in fs]
    half_w = max(max(f.anchor_x - f.x0, f.x1 - f.anchor_x) for f in all_frames)
    above = max(f.ground - f.y0 for f in all_frames)
    below = max(max(0, f.y1 - f.ground) for f in all_frames)
    cell_w = 2 * (half_w + PAD)
    cell_h = above + below + 2 * PAD
    ground_y = PAD + above
    center_x = cell_w // 2
    print(f"cell {cell_w}x{cell_h} ground_y={ground_y}")

    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = {
        "cell_w": cell_w,
        "cell_h": cell_h,
        "anchor_x": center_x,
        "ground_y": ground_y,
        "animations": {},
    }
    for row in ROWS:
        fs = frames[row.name]
        strip = Image(cell_w * len(fs), cell_h)
        src = sheets[row.sheet]
        for i, f in enumerate(fs):
            ox = i * cell_w + center_x - f.anchor_x
            oy = ground_y - f.ground
            for (x, y) in f.pixels:
                r, g, b, _ = src.get(x, y)
                strip.put(x + ox, y + oy, (r, g, b, 255))
        fname = f"{row.name}.png"
        write_png(os.path.join(OUT_DIR, fname), strip)
        manifest["animations"][row.name] = {"file": fname, "frames": len(fs)}
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print(f"wrote {len(ROWS)} strips to {OUT_DIR}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--raw", metavar="DIR", help="read sprite_<key>.rgba dumps from DIR instead of decoding JPEGs")
    build(ap.parse_args().raw)
