#!/usr/bin/env python3
"""
Builds the table styles' material tiles from Poly Haven's CC0 scans, for the game and the admin page's
table designer alike, so both draw from the same pictures:

  client/assets/tiles/table/wood_<name>.jpg      the rail woods, 512px, grain running left to right
  client/assets/tiles/table/<name>_shade.png     the leather and cloth grain: white where the scan is lighter
                                                 than its average, black where darker, the difference as alpha,
                                                 so drawn over any colour it lightens and darkens it. The velvet
                                                 is made here rather than scanned: soft sheen brushed along the nap
  server/casino_server/table_styles_web/textures/  the same files, plus the carpet, the dealer and the fine felt grain
                                                 (Roulette's and Craps' House cloth) for the designer
  server/casino_server/table_styles_web/fonts/     the game's lettering fonts, for the designer

Downloads are cached in .dev/polyhaven/. Every source and what's done to it is in docs/table_styles/LICENSES.md;
change that too if you change SOURCES. Run it with the server's venv (it needs Pillow):
  server/.venv/bin/python tools/build_table_tiles.py
"""
import json
import shutil
import urllib.request
from pathlib import Path

import numpy as np
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
    "baize": ("caban", 384, 5, 0.7),
}


def fetch(url: str) -> bytes:
    """Poly Haven turns away urllib's own User-Agent."""
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "CasinoWorld-tiles/1"})) as r:
        return r.read()


def source(asset_id: str) -> Image.Image:
    """The asset's 1k diffuse map, squashed to 1024x1024 (a few are 985-1026 tall: squashing keeps them tiling)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{asset_id}.jpg"
    if not path.exists():
        files = json.loads(fetch(f"https://api.polyhaven.com/files/{asset_id}"))
        path.write_bytes(fetch(files["Diffuse"]["1k"]["jpg"]["url"]))
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
    tiled = Image.new("L", (size * 3, size * 3))   # blurred as a 3x3 of itself, so the high-pass tiles without a seam
    for y in range(3):
        for x in range(3):
            tiled.paste(grey, (x * size, y * size))
    blurred = tiled.filter(ImageFilter.GaussianBlur(blur)).crop((size, size, 2 * size, 2 * size))
    hp = ImageChops.subtract(grey, blurred, scale=1.0, offset=128)
    k = 22.0 * gain / max(ImageStat.Stat(hp).stddev[0], 0.5)   # gain 1: a spread of 22 grey levels
    return shade_tile((np.asarray(hp, float) - 128) * k)


def shade_tile(d: np.ndarray) -> Image.Image:
    """Grey-level differences to a shade: white where lighter, black where darker, the difference (x2.2) as alpha."""
    v = np.where(d > 0, 255, 0)
    a = np.clip(np.round(np.abs(d) * 2.2), 0, 255)
    return Image.fromarray(np.stack([v, v, v, a], -1).astype(np.uint8), "RGBA")


def noise(size: int, wavelength: float, stretch: float = 1.0, angle: float = 0.0, seed: int = 0) -> np.ndarray:
    """Tiling noise with features about `wavelength` px across, `stretch` times longer along `angle` (radians):
    white noise low-passed in frequency space, so it wraps at the edges. Mean 0, deviation 1."""
    white = np.random.default_rng(seed).standard_normal((size, size))
    fy, fx = np.fft.fftfreq(size)[:, None], np.fft.fftfreq(size)[None, :]
    u = (fx * np.cos(angle) + fy * np.sin(angle)) * stretch
    v = -fx * np.sin(angle) + fy * np.cos(angle)
    out = np.real(np.fft.ifft2(np.fft.fft2(white) * np.exp(-(u * u + v * v) * wavelength ** 2)))
    return (out - out.mean()) / out.std()


def velvet(size: int = 512) -> Image.Image:
    """Velvet: broad soft sheen where the pile lies one way or the other, drawn out along the nap, over a very
    faint fine pile. No speckle, so it reads as plush rather than as carpet."""
    sheen = 0.8 * noise(size, 120, 2.2, 0.45, seed=1) + 0.4 * noise(size, 30, 2.9, 0.45, seed=2)
    d = sheen / sheen.std() + 0.18 * noise(size, 1.4, seed=3)
    return shade_tile(d * 5.5)


def main():
    OUT_GAME.mkdir(parents=True, exist_ok=True)
    OUT_WEB.mkdir(parents=True, exist_ok=True)
    for name in WOODS:
        im = wood(name)
        for out in (OUT_GAME, OUT_WEB):
            im.save(out / f"wood_{name}.jpg", quality=86)
    shades = {name: shade(name) for name in SHADES} | {"velvet": velvet()}
    for name, im in shades.items():
        for out in (OUT_GAME, OUT_WEB):
            im.save(out / f"{name}_shade.png", optimize=True)
    # The designer's stage: the floor's carpet and the dealer, as the game has them.
    shutil.copy(ROOT / "client" / "assets" / "tiles" / "carpet.png", OUT_WEB / "carpet.png")
    shutil.copy(ROOT / "client" / "assets" / "sprites" / "characters" / "dealer.png", OUT_WEB / "dealer.png")
    shutil.copy(ROOT / "client" / "assets" / "tiles" / "felt_grain.png", OUT_WEB / "felt_grain.png")
    # ...and the game's lettering, so the designer prints with the very same fonts.
    fonts = OUT_WEB.parent / "fonts"
    fonts.mkdir(exist_ok=True)
    for name in ("Cinzel-SemiBold", "CormorantSC-Bold", "JosefinSans-SemiBold", "Montserrat-SemiBold", "DejaVuSans-Bold"):
        shutil.copy(ROOT / "client" / "assets" / "fonts" / f"{name}.ttf", fonts / f"{name}.ttf")
    print(f"wrote {len(WOODS)} woods and {len(shades)} shades to {OUT_GAME.relative_to(ROOT)} and {OUT_WEB.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
