"""
Generate assets/icon.ico from the first idle frame if no icon exists.
Run once as a build step (build.bat does this).
"""
from __future__ import annotations

import json
import os

from PIL import Image


def generate_icon(assets_dir: str) -> None:
    ico_path = os.path.join(assets_dir, "icon.ico")
    if os.path.exists(ico_path):
        return
    sprites = os.path.join(assets_dir, "sprites")
    try:
        with open(os.path.join(sprites, "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        cw, ch = manifest["cell_w"], manifest["cell_h"]
        strip = Image.open(os.path.join(sprites, "idle.png")).convert("RGBA")
        # Frames are already transparent; crop the first one to its content, squared.
        frame = strip.crop((0, 0, cw, ch))
        frame = frame.crop(frame.getbbox())
        side = max(frame.size)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        square.paste(frame, ((side - frame.width) // 2, side - frame.height))
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        square.save(ico_path, format="ICO", sizes=sizes)
        print(f"[icon_gen] Created {ico_path}")
    except Exception as e:
        print(f"[icon_gen] Could not create icon: {e}")


if __name__ == "__main__":
    assets = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    generate_icon(assets)
