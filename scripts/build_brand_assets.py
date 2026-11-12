"""Generate web brand assets from the Elaris presentation board.

The source file is a 2000x2000 presentation image with a cream background.
Run with: .venv/bin/python scripts/build_brand_assets.py
"""

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "design" / "logo-elaris-source.png"
OUT = ROOT / "static" / "brand"

# Crop boxes measured from the source presentation board.
CROPS = {
    "logo-horizontal.png": (380, 315, 1560, 1015),
    "logo-horizontal-no-tagline.png": (380, 315, 1560, 900),
    "isotype.png": (640, 1150, 1370, 1910),
}

CREAM = np.array([250, 245, 236], dtype=np.int16)


def remove_cream_background(image: Image.Image) -> Image.Image:
    """Make the flat cream paper background transparent."""
    rgba = image.convert("RGBA")
    arr = np.asarray(rgba).copy()
    rgb = arr[:, :, :3].astype(np.int16)
    distance = np.abs(rgb - CREAM).max(axis=2)

    # Keep the soft blue glow, but drop the paper texture and flat cream.
    alpha = np.clip((distance - 6) / 15, 0, 1)
    alpha = (alpha * 255).astype(np.uint8)
    arr[:, :, 3] = alpha
    return Image.fromarray(arr, "RGBA")


def save_icon(isotype: Image.Image, size: int, name: str) -> None:
    canvas = Image.new("RGB", (size, size), tuple(CREAM.tolist()))
    padding = int(size * 0.10)
    max_side = size - padding * 2
    icon = isotype.copy()
    icon.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    x = (size - icon.width) // 2
    y = (size - icon.height) // 2
    canvas.paste(icon, (x, y), icon)
    canvas.save(OUT / name, optimize=True)


def save_width(image: Image.Image, width: int, name: str) -> None:
    height = round(image.height * width / image.width)
    resized = image.resize((width, height), Image.Resampling.LANCZOS)
    resized.save(OUT / name, optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE)

    transparent: dict[str, Image.Image] = {}
    for filename, box in CROPS.items():
        crop = source.crop(box)
        transparent[filename] = remove_cream_background(crop)
        transparent[filename].save(OUT / filename, optimize=True)

    isotype = transparent["isotype.png"]
    save_icon(isotype, 512, "icon-512.png")
    save_icon(isotype, 180, "favicon-180.png")
    save_icon(isotype, 32, "favicon-32.png")

    save_width(transparent["logo-horizontal-no-tagline.png"], 600, "logo-header.png")
    save_width(isotype, 320, "isotype-320.png")

    print(f"Brand assets written to {OUT}")


if __name__ == "__main__":
    main()
