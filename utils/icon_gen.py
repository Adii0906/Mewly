"""
Generate a simple .ico file from the first sprite frame if no icon exists.
Run once during first launch or as a build step.
"""
from __future__ import annotations
import os
from PIL import Image


def generate_icon(assets_dir: str) -> None:
    ico_path = os.path.join(assets_dir, "icon.ico")
    if os.path.exists(ico_path):
        return

    # Try to make an icon from the first idle frame
    basic_path = os.path.join(assets_dir, "sprite_basic.png")
    if not os.path.exists(basic_path):
        return

    try:
        sheet = Image.open(basic_path).convert("RGBA")
        # Idle row 0, frame 1 (col 1 at 256px wide)
        frame = sheet.crop((256, 0, 512, 256))

        # Remove black background
        px = frame.load()
        for y in range(frame.height):
            for x in range(frame.width):
                r, g, b, a = px[x, y]
                if r < 25 and g < 25 and b < 25:
                    px[x, y] = (0, 0, 0, 0)

        # Save as multi-size ICO
        sizes = [(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]
        icons = [frame.resize(s, Image.LANCZOS) for s in sizes]
        icons[0].save(ico_path, format="ICO", sizes=sizes,
                      append_images=icons[1:])
        print(f"[icon_gen] Created {ico_path}")
    except Exception as e:
        print(f"[icon_gen] Could not create icon: {e}")


if __name__ == "__main__":
    assets = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
    generate_icon(assets)
