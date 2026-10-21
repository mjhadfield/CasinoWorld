#!/usr/bin/env python3
"""
Builds the table styles' material tiles from Poly Haven's CC0 scans, for the game and the admin page's
table designer alike, so both draw from the same pictures:

  client/assets/tiles/table/wood_<name>.jpg      the rail woods, 512px, grain running left to right
  client/assets/tiles/table/<name>_shade.png     the leather and felt grain: white where the scan is lighter
                                                 than its average, black where darker, the difference as alpha,
                                                 so drawn over any colour it lightens and darkens it
  server/casino_server/table_styles_web/textures/  the same files, plus the carpet and the dealer for the designer

Downloads are cached in .dev/polyhaven/. Every source and what's done to it is in docs/table_styles/LICENSES.md;
change that too if you change SOURCES. Run it with the server's venv (it needs Pillow):
  server/.venv/bin/python tools/build_table_tiles.py
"""
import json
import shutil
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps, ImageStat

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".dev" / "polyhaven"
OUT_GAME = ROOT / "client" / "assets" / "tiles" / "table"
OUT_WEB = ROOT / "server" / "casino_server" / "table_styles_web" / "textures"

# Our name: (Poly Haven id, turn 90°, brightness, saturation, contrast, warm tint (r, g, b, strength) laid over with "screen")
WOODS = {
    "mahogany": ("dark_wood", False, 1.0, 1.0, 1.0, (150, 60, 25, 0.10)),
    "walnut": ("lacquered_cherry_wood", False, 1.25, 1.0, 1.0, (120, 80, 45, 0.12)),
    "wenge": ("wood_table_001", True, 1.0, 1.0, 1.0, (90, 50, 30, 0.10)),
    "rosewood": ("rosewood_veneer1", True, 0.85, 1.0, 1.0, (150, 70, 30, 0.10)),
    "ebony": ("flamed_black_veneer", False, 0.55, 0.5, 2.2, (40, 40, 48, 0.25)),
}
# Our name: (Poly Haven id, size, blur radius for the high-pass, strength)
SHADES = {
    "leather": ("leather_white", 512, 16, 0.8),
    "weave": ("terlenka", 256, 8, 1.0),
    "velvet": ("velour_velvet", 512, 20, 1.0),
}


def source(asset_id: str) -> Image.Image:
    """The asset's 1k diffuse map, squashed to 1024x1024 (a few are 985-1026 tall: squashing keeps them tiling)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{asset_id}.jpg"
    if not path.exists():
        with urllib.request.urlopen(f"https://api.polyhaven.com/files/{asset_id}") as r:
            files = json.load(r)
        url = files["Diffuse"]["1k"]["jpg"]["url"]
        with urllib.request.urlopen(url) as r:
            path.write_bytes(r.read())
    return Image.open(path).convert("RGB").resize((1024, 1024), Image.LANCZOS)


def wood(name: str) -> Image.Image:
    asset, turn, bright, sat, contrast, warm = WOODS[name]
    im = source(asset)
    if turn:
        im = im.rotate(90, expand=True)
    im = im.resize((512, 512), Image.LANCZOS)
    im = ImageEnhance.Brightness(im).enhance(bright)
    im = ImageEnhance.Color(im).enhance(sat)
    im = ImageEnhance.Contrast(im).enhance(contrast)
    r, g, b, k = warm   # screen: 1 - (1 - a)(1 - b)
    tint = Image.new("RGB", im.size, (round(r * k), round(g * k), round(b * k)))
    return ImageChops.screen(im, tint)


def shade(name: str) -> Image.Image:
    asset, size, blur, gain = SHADES[name]
    grey = ImageOps.grayscale(source(asset)).resize((size, size), Image.LANCZOS)
    hp = ImageChops.subtract(grey, grey.filter(ImageFilter.GaussianBlur(blur)), scale=1.0, offset=128)
    k = 22.0 * gain / max(ImageStat.Stat(hp).stddev[0], 0.5)   # gain 1: a spread of 22 grey levels
    out = Image.new("RGBA", hp.size)
    px, src = out.load(), hp.load()
    for y in range(size):
        for x in range(size):
            d = (src[x, y] - 128) * k
            v = 255 if d > 0 else 0
            px[x, y] = (v, v, v, min(255, round(abs(d) * 2.2)))
    return out


def main():
    OUT_GAME.mkdir(parents=True, exist_ok=True)
    OUT_WEB.mkdir(parents=True, exist_ok=True)
    for name in WOODS:
        im = wood(name)
        for out in (OUT_GAME, OUT_WEB):
            im.save(out / f"wood_{name}.jpg", quality=86)
    for name in SHADES:
        im = shade(name)
        for out in (OUT_GAME, OUT_WEB):
            im.save(out / f"{name}_shade.png", optimize=True)
    # The designer's stage: the floor's carpet and the dealer, as the game has them.
    shutil.copy(ROOT / "client" / "assets" / "tiles" / "carpet.png", OUT_WEB / "carpet.png")
    shutil.copy(ROOT / "client" / "assets" / "sprites" / "characters" / "dealer.png", OUT_WEB / "dealer.png")
    print(f"wrote {len(WOODS)} woods and {len(SHADES)} shades to {OUT_GAME.relative_to(ROOT)} and {OUT_WEB.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
