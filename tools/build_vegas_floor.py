#!/usr/bin/env python3
"""
The Vegas floor: a modern Las Vegas casino floor as a floor plan blueprint, with its own furniture and floors.

  pieces    tools/vegas_floor/pieces.js, painted in headless Chromium at twice the game's resolution (scale 2), and
            installed into a data dir's library as uploads (ids vegas_<id>), so each can be edited or deleted on the
            admin page's Floor plan > Assets like any other upload
  floors    marble slabs (white and black) and walnut planks cut from ambientCG's CC0 scans (tools/vegas_floor/
            textures/), and seven Vegas carpets (the floor's, five variations, the pits') drawn here and woven over a real
            carpet's fibre; floor ids vegas_*
  room      "Casino Floor (Vegas)": the raised stage with the Master Table, Roulette, Craps, four slot banks, the Amber
            Bar, the cashier, a lounge and its staff, sent to a running server's draft as a blueprint (unplaced unless
            --place); its tables get "Dark Modern" styles, the master table's look (Roulette's and Craps' are made
            here if missing)

  server/.venv/bin/python tools/build_vegas_floor.py [--data DIR] [--only pieces,floors] [--no-room]
                                                    [--server URL] [--place]

--data is where the art goes (default: the live server/data); restart that server afterwards so its library picks the
art up. --server is the server whose draft gets the room (default: the live one on 8660); running it again replaces the
room in the draft, keeping its tables' ids. --place puts it on the plan (for a dev instance), else it lands in the
library; either way it goes where it meets the Modern lobby's door. A contact sheet of the art goes to
.dev/vegas_contact.png.
"""
import argparse
import asyncio
import base64
import io
import json
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "tools" / "vegas_floor"
TEXTURES = HERE / "textures"
FONTS = ROOT / "client" / "assets" / "fonts"
sys.path.insert(0, str(ROOT / "server"))

CREDIT = "Drawn for Casino World's Vegas floor (tools/vegas_floor); textures ambientCG (CC0)"
SCALE = 2
PREFIX = "vegas_"
ROOM_ID = "vegas_floor"
# The library's categories for the mockup's groups (anything else: Decor).
CATEGORY = {"Stage": "Decor", "Signs": "Decor", "Services": "Decor"}


# ------------------------------------------------------------------ pieces
def data_url(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


async def render() -> dict:
    from playwright.async_api import async_playwright
    textures = {p.stem: data_url(p, "image/jpeg") for p in TEXTURES.glob("*.jpg")}
    fonts = {"Montserrat": data_url(FONTS / "Montserrat-SemiBold.ttf", "font/ttf"),
             "Josefin Sans": data_url(FONTS / "JosefinSans-SemiBold.ttf", "font/ttf"),
             "Cinzel": data_url(FONTS / "Cinzel-SemiBold.ttf", "font/ttf")}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content("<!doctype html><meta charset=utf-8><script>" + (HERE / "pieces.js").read_text() + "</script>")
        out = await page.evaluate("([t, f]) => renderAll(t, f)", [textures, fonts])
        await browser.close()
    return out


def png(url: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGBA")


def entry(piece: dict, files: dict) -> dict:
    """The library entry: every facing drawn, the mirrored ones, per-facing shapes, all in game pixels."""
    w, h = piece["size"]
    ax, ay = piece["anchor"]
    rect = [-ax, -ay, w, h]
    body = piece["body"] if piece["mount"] == "floor" else None
    facings = {f: {"file": file, "anchor": [ax, ay], "scale": SCALE} for f, file in files.items()}
    facings.setdefault("down", dict(next(iter(facings.values()))))
    for f, of in (piece.get("mirrors") or {}).items():
        facings[f] = {**facings[of], "mirror": True}
    a = {"name": piece["name"], "category": CATEGORY.get(piece["cat"], piece["cat"]), "mount": piece["mount"],
         "credit": CREDIT, "facings": facings, "rect": rect, "body": body}
    others = [f for f in facings if f != "down"]
    if others:
        a["by_facing"] = {f: {"rect": rect, "body": body} for f in others}
    for k in ("screen", "interact"):
        if piece.get(k):
            a[k] = piece[k]
    return a


# ------------------------------------------------------------------ floors
def _tex(name: str) -> np.ndarray:
    return np.asarray(Image.open(TEXTURES / f"{name}.jpg").convert("RGB"), dtype=np.float32) / 255.0


def _hex(h: str) -> np.ndarray:
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float32) / 255.0


def slabs(name: str, seed: int, n: int = 2, slab: int = 128, tone: float = .05, grout: str = "#000000",
          grout_a: float = .55) -> Image.Image:
    """Polished stone slabs, n by n to a tile, each its own cut of the scan (turned any way), a fine grout line
    along the top and left of each (so the tile repeats seamlessly) and a sheen across it."""
    src = _tex(name)
    rs = np.random.default_rng(seed)
    size = n * slab
    out = np.zeros((size, size, 3), np.float32)
    yy, xx = np.mgrid[0:slab, 0:slab].astype(np.float32) / slab
    sheen = np.clip(1 - np.abs((xx + yy) - .7) * 2.2, 0, 1) ** 2 * .05
    for j in range(n):
        for i in range(n):
            ox, oy = rs.integers(0, src.shape[1]), rs.integers(0, src.shape[0])
            cut = np.roll(np.roll(src, -oy, 0), -ox, 1)[:256, :256]
            cut = np.asarray(Image.fromarray((cut * 255).astype(np.uint8)).resize((slab, slab), Image.LANCZOS),
                             np.float32) / 255
            cut = np.rot90(cut, rs.integers(0, 4))
            cut = cut * (1 + rs.uniform(-tone, tone)) + sheen[..., None]
            out[j * slab:(j + 1) * slab, i * slab:(i + 1) * slab] = cut
    g = _hex(grout)
    for k in range(n):
        for line, a in ((0, grout_a), (1, grout_a * .35)):
            out[k * slab + line, :] = out[k * slab + line, :] * (1 - a) + g * a
            out[:, k * slab + line] = out[:, k * slab + line] * (1 - a) + g * a
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def planks(name: str, seed: int, size: int = 256, width: int = 32) -> Image.Image:
    """Wood planks running east-west, staggered, each its own cut of the scan, with a dark seam and bevel."""
    src = _tex(name)
    rs = np.random.default_rng(seed)
    out = np.zeros((size, size, 3), np.float32)
    rows = size // width
    for r in range(rows):
        cuts = sorted(rs.choice(np.arange(48, size - 48, 8), 2, replace=False))
        edges = [0, *cuts, size]
        shift = rs.integers(0, size)
        for a, b in zip(edges, edges[1:]):
            ox, oy = rs.integers(0, src.shape[1]), rs.integers(0, src.shape[0])
            board = np.roll(np.roll(src, -oy, 0), -ox, 1)[:width, :b - a]
            board = board * (1 + rs.uniform(-.08, .08))
            out[r * width:(r + 1) * width, a:b] = board
            out[r * width:(r + 1) * width, a] *= .45
        out[r * width:(r + 1) * width] = np.roll(out[r * width:(r + 1) * width], shift, 1)
        out[r * width] *= .4
        out[r * width + 1] *= 1.12
    out *= .82
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def _fibre(size: int) -> np.ndarray:
    """The real carpet's pile as a multiplier about 1 (seamless: the scan tiles)."""
    f = np.asarray(Image.open(TEXTURES / "carpet_fibre.jpg").convert("L").resize((size, size), Image.LANCZOS), np.float32) / 255
    return 1 + (f - f.mean()) * 1.6


def _layer(base: np.ndarray, mask: np.ndarray, colour: str) -> np.ndarray:
    m = np.clip(mask, 0, 1)[..., None]
    return base * (1 - m) + _hex(colour) * m


def vegas_carpet(size: int = 256) -> Image.Image:
    """The floor's carpet: a deep aubergine-charcoal field, tonal swirls, two flowing ribbons (amber edged in copper,
    deep teal) and gold starbursts, all periodic so the tile repeats. 128 game pixels a repeat at scale 2 (about two and
    a half figures tall: a real casino carpet's repeat)."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    tau = 2 * np.pi
    wu = xx + .07 * np.sin(tau * (yy + .2)) + .03 * np.sin(tau * 2 * (yy + xx))
    wv = yy + .07 * np.sin(tau * (xx + .55)) + .03 * np.sin(tau * 3 * xx)
    img = np.broadcast_to(_hex("#1a1418"), (size, size, 3)).copy()
    swirl = np.sin(tau * (2 * wu + wv)) * .5 + np.sin(tau * (wu - 2 * wv) + 1.3) * .5
    img = _layer(img, (swirl > .35) * .55, "#241a22")
    img = _layer(img, (swirl < -.55) * .5, "#130f12")
    # the ribbons: bands along the zero lines of two fields
    f1 = np.sin(tau * (wu + 2 * wv) + .6) + .55 * np.sin(tau * (3 * wu - wv))
    f2 = np.sin(tau * (2 * wu - wv) + 2.1) + .5 * np.sin(tau * (wu + 3 * wv) + .4)
    def band(f, w, soft=.012):
        return np.clip((w - np.abs(f)) / soft, 0, 1)
    img = _layer(img, band(f2, .085), "#0f3b3d")
    img = _layer(img, band(f2, .03), "#1f6461")
    img = _layer(img, band(f1, .12), "#7a3b22")
    img = _layer(img, band(f1, .085), "#c98a3e")
    img = _layer(img, band(f1, .028), "#f0c070")
    # starbursts on a lattice (4 a tile), and small copper dots between
    for cx, cy, r in ((.25, .25, .07), (.75, .75, .07), (.75, .25, .045), (.25, .75, .045)):
        dx = (xx - cx + .5) % 1 - .5
        dy = (yy - cy + .5) % 1 - .5
        d = np.hypot(dx, dy)
        th = np.arctan2(dy, dx)
        star = r * (.35 + .65 * np.abs(np.cos(4 * th)) ** 4)
        img = _layer(img, np.clip((star - d) / .006, 0, 1) * .95, "#d9b56a")
        img = _layer(img, np.clip((r * .28 - d) / .005, 0, 1), "#1a1418")
        img = _layer(img, np.clip((r * .14 - d) / .005, 0, 1), "#f2b25c")
    for cx in np.arange(.125, 1, .25):
        for cy in np.arange(.125, 1, .25):
            dx = (xx - cx + .5) % 1 - .5
            dy = (yy - cy + .5) % 1 - .5
            img = _layer(img, np.clip((.009 - np.hypot(dx, dy)) / .004, 0, 1) * .8, "#b0603a")
    out = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.7))
    img = np.asarray(out, np.float32) / 255 * _fibre(size)[..., None]
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


def pit_carpet(size: int = 128) -> Image.Image:
    """The pits' carpet: a darker oxblood field with a fine gold diamond lattice and small medallions, quieter than the
    floor's so the tables stand out. 64 game pixels a repeat at scale 2."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    img = np.broadcast_to(_hex("#240d12"), (size, size, 3)).copy()
    tau = 2 * np.pi
    img = _layer(img, (np.sin(tau * 2 * xx) * np.sin(tau * 2 * yy) > .5) * .35, "#2e1118")
    d1 = np.abs(((xx + yy) * 2) % 1 - .5)
    d2 = np.abs(((xx - yy) * 2) % 1 - .5)
    img = _layer(img, np.clip((.012 - np.minimum(d1, d2)) / .006, 0, 1) * .75, "#9a7a3e")
    for cx, cy in ((.25, .0), (.75, .5), (.25, .5), (.75, .0)):
        dx = (xx - cx + .5) % 1 - .5
        dy = (yy - cy + .5) % 1 - .5
        d = np.abs(dx) + np.abs(dy)
        img = _layer(img, np.clip((.06 - d) / .006, 0, 1), "#3b1219")
        img = _layer(img, np.clip((.06 - d) / .006, 0, 1) * np.clip((d - .045) / .006, 0, 1), "#c9a24a")
        img = _layer(img, np.clip((.018 - d) / .006, 0, 1), "#c45454")
    out = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.6))
    img = np.asarray(out, np.float32) / 255 * _fibre(size)[..., None]
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


# The variations: each 128 game pixels a repeat at scale 2, like the floor's carpet, every shape placed with wrapped
# distances so the tile repeats seamlessly, and all woven over the same fibre.
def _uv(size: int):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    return xx, yy


def _wrap(v, c):
    """The way from c to v across a repeating tile (-0.5..0.5)."""
    return (v - c + .5) % 1 - .5


def _woven(img: np.ndarray, size: int, blur: float = .6) -> Image.Image:
    out = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur))
    img = np.asarray(out, np.float32) / 255 * _fibre(size)[..., None]
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


def _soft(d, r, edge=.005):
    """1 inside radius r, fading out over `edge`."""
    return np.clip((r - d) / edge, 0, 1)


def deco_fans(size: int = 256) -> Image.Image:
    """Art deco fans: overlapping scallops (seigaiha) on midnight navy, each ringed in gold and pale teal. Each pixel
    shows the scallop whose middle is furthest below it, so every row lies over the one above, across the tile's edge
    too, and only the tops of the fans show."""
    xx, yy = _uv(size)
    R = .19
    best_d = np.full((size, size), np.inf, np.float32)
    best_dy = np.full((size, size), np.inf, np.float32)
    for row in range(8):
        for col in range(4):
            cx, cy = col / 4 + (.125 if row % 2 else 0), row / 8
            dy = _wrap(yy, cy)
            d = np.hypot(_wrap(xx, cx), dy)
            take = (d < R) & (dy < best_dy)
            best_d, best_dy = np.where(take, d, best_d), np.where(take, dy, best_dy)
    img = np.broadcast_to(_hex("#0c142b"), (size, size, 3)).copy()
    ring = (best_d / R * 5) % 1
    inside = np.isfinite(best_d)
    img = _layer(img, inside * np.clip((ring - .8) / .04, 0, 1), "#d9b56a")
    img = _layer(img, inside * (best_d < R * .8) * np.clip(1 - np.abs(ring - .44) / .07, 0, 1), "#3f7f86")
    img = _layer(img, inside * (best_d < R * .4) * np.clip(1 - np.abs(ring - .44) / .07, 0, 1), "#b08a4a")
    return _woven(img, size)


def neon_geo(size: int = 256) -> Image.Image:
    """Neon geometry: a triangle lattice in magenta, cyan and amber lines on charcoal, some triangles tinted, glowing
    nodes where the lines cross."""
    xx, yy = _uv(size)
    img = np.broadcast_to(_hex("#121217"), (size, size, 3)).copy()
    u, v, w = 4 * xx, 4 * (xx + yy), 4 * (xx - yy)
    cell = (np.floor(u) * 7 + np.floor(v) * 13 + np.floor(w) * 5) % 9   # (which triangle: periodic, as the lines are)
    for k, col in ((1, "#24152e"), (4, "#0f2430"), (7, "#2a1f12")):
        img = _layer(img, (cell == k) * .9, col)
    glow = np.zeros((size, size), np.float32)
    for f, col in ((u, "#e0408f"), (v, "#33c6d6"), (w, "#f2b25c")):
        d = np.abs(((f + .5) % 1) - .5) / 4   # distance to the nearest line, in tile units
        glow = np.maximum(glow, np.clip(1 - d / .03, 0, 1) * .35)
        img = _layer(img, np.clip((.006 - d) / .004, 0, 1), col)
    img = img + glow[..., None] * np.array([.25, .12, .22], np.float32)
    for cx in np.arange(0, 1, .25):
        for cy in np.arange(0, 1, .25):
            for ox in (0, .125):
                d = np.hypot(_wrap(xx, cx + ox), _wrap(yy, cy + ox))
                img = _layer(img, _soft(d, .012, .004), "#fff1d2")
    return _woven(img, size, .5)


def damask(size: int = 256) -> Image.Image:
    """Royal damask: gold six-petal medallions with rose hearts on deep burgundy, small rose quatrefoils between, and
    thin gold vines curling through."""
    xx, yy = _uv(size)
    tau = 2 * np.pi
    img = np.broadcast_to(_hex("#330b14"), (size, size, 3)).copy()
    tone = np.sin(tau * (xx + yy)) * np.sin(tau * (xx - yy))
    img = _layer(img, (tone > .4) * .4, "#3f1019")
    vine = np.sin(tau * (2 * xx + .15 * np.sin(tau * 2 * yy))) - np.sin(tau * 2 * yy)
    img = _layer(img, np.clip((.06 - np.abs(vine)) / .03, 0, 1) * .8, "#8a6a2e")
    for cx, cy in ((.25, .25), (.75, .75)):
        dx, dy = _wrap(xx, cx), _wrap(yy, cy)
        d, th = np.hypot(dx, dy), np.arctan2(dy, dx)
        petal = .15 * (.55 + .45 * np.abs(np.cos(3 * th)))
        img = _layer(img, _soft(d, petal), "#c9963e")
        img = _layer(img, _soft(d, petal * .78), "#5a1420")
        img = _layer(img, _soft(d, .15 * .55 * (.6 + .4 * np.abs(np.cos(3 * th + .5)))), "#b8434e")
        img = _layer(img, _soft(d, .028), "#e8c070")
    for cx, cy in ((.75, .25), (.25, .75)):
        dx, dy = _wrap(xx, cx), _wrap(yy, cy)
        d, th = np.hypot(dx, dy), np.arctan2(dy, dx)
        img = _layer(img, _soft(d, .07 * (.5 + .5 * np.abs(np.cos(2 * th)))), "#9c3a44")
        img = _layer(img, _soft(d, .016), "#d9b56a")
    return _woven(img, size)


def confetti(size: int = 256) -> Image.Image:
    """Starburst confetti: retro-modern sparkles, starbursts, rings and dots in gold, coral and teal scattered over
    deep purple."""
    xx, yy = _uv(size)
    img = np.broadcast_to(_hex("#1b0e29"), (size, size, 3)).copy()
    img = _layer(img, (np.sin(2 * np.pi * 3 * xx) * np.sin(2 * np.pi * 3 * yy) > .7) * .3, "#24123a")
    rs = np.random.default_rng(42)
    for n in range(46):
        cx, cy, kind = rs.random(), rs.random(), n % 4
        dx, dy = _wrap(xx, cx), _wrap(yy, cy)
        d, th = np.hypot(dx, dy), np.arctan2(dy, dx) + rs.random()
        if kind == 0:     # a four-point sparkle
            r = .035 + rs.random() * .02
            img = _layer(img, _soft(d, r * (.12 + .88 * np.abs(np.cos(2 * th)) ** 8), .004), "#f2c96a")
        elif kind == 1:   # an eight-point starburst
            r = .03 + rs.random() * .015
            img = _layer(img, _soft(d, r * (.4 + .6 * np.abs(np.cos(4 * th)) ** 3), .004), "#e8735a")
            img = _layer(img, _soft(d, r * .3, .003), "#1b0e29")
        elif kind == 2:   # a ring
            r = .018 + rs.random() * .012
            img = _layer(img, _soft(d, r, .003) * (1 - _soft(d, r * .62, .003)), "#3fb7a8")
        else:             # a dot
            img = _layer(img, _soft(d, .008 + rs.random() * .006, .003), ("#f2c96a", "#e8735a", "#3fb7a8")[n % 3])
    return _woven(img, size)


def emerald_waves(size: int = 256) -> Image.Image:
    """Emerald waves: layered swells in jade and deep green, each crest edged in gold with a row of small gold
    diamonds riding it."""
    xx, yy = _uv(size)
    tau = 2 * np.pi
    img = np.broadcast_to(_hex("#0a2920"), (size, size, 3)).copy()
    f = 6 * yy + .55 * np.sin(tau * 2 * xx) + .18 * np.sin(tau * 5 * xx + 1.1)
    band, frac = np.floor(f) % 3, f % 1
    for k, col in ((0, "#0f3d31"), (1, "#1a5a48"), (2, "#0b2f26")):
        img = _layer(img, (band == k) * (.4 + .6 * frac), col)   # (each swell darkening into the next)
    img = _layer(img, np.clip((frac - .94) / .02, 0, 1), "#d9b56a")
    img = _layer(img, np.clip((frac - .9) / .02, 0, 1) * np.clip((.93 - frac) / .02, 0, 1) * .7, "#2f7a62")
    for k in range(6):   # diamonds along each crest
        cyf = (k + 1 - .03)
        for i in range(8):
            cx = (i + (.5 if k % 2 else 0)) / 8
            crest = (cyf - .55 * np.sin(tau * 2 * cx) - .18 * np.sin(tau * 5 * cx + 1.1)) / 6
            d = np.abs(_wrap(xx, cx)) + np.abs(_wrap(yy, crest))
            img = _layer(img, _soft(d, .014, .003), "#e8c070")
    return _woven(img, size)


FLOORS = {
    "carpet": ("Vegas carpet, amber ribbons", lambda: vegas_carpet()),
    "carpet_deco": ("Vegas carpet, deco fans", lambda: deco_fans()),
    "carpet_neon": ("Vegas carpet, neon geometry", lambda: neon_geo()),
    "carpet_damask": ("Vegas carpet, royal damask", lambda: damask()),
    "carpet_confetti": ("Vegas carpet, starburst confetti", lambda: confetti()),
    "carpet_waves": ("Vegas carpet, emerald waves", lambda: emerald_waves()),
    "pit_carpet": ("Vegas pit carpet, oxblood", lambda: pit_carpet()),
    "marble_white": ("White marble slabs", lambda: slabs("marble_white", 3, grout="#6d665c", grout_a=.5)),
    "marble_black": ("Black marble slabs", lambda: slabs("marble_black", 5, grout="#000000", grout_a=.6)),
    "walnut": ("Walnut planks", lambda: planks("walnut", 7)),
}


# ------------------------------------------------------------------ the room
def staff_looks(data_dir: Path) -> dict:
    """The staff figures' looks, dressed in the house uniforms (built into the data dir's looks)."""
    from casino_server import art, staff
    looks = art.LookCache(data_dir)
    people = {
        "bartender_f": ("bartender", {"body": "female", "skin": "amber", "hair": ["lob", "black"]}),
        "bartender_m": ("bartender", {"body": "male", "skin": "black", "hair": ["curly_short", "black"]}),
        "cashier_f": ("cashier", {"body": "female", "skin": "light", "hair": ["bangsshort", "chestnut"]}),
        "cashier_m": ("cashier", {"body": "male", "skin": "olive", "hair": ["parted", "dark_brown"]}),
        "host": ("pit_boss", {"body": "male", "skin": "taupe", "hair": ["high_and_tight", "black"]}),
        "waitress": ("cocktail_waiter", {"body": "female", "skin": "brown", "hair": ["curly_long", "black"]}),
    }
    out = {}
    for key, (role, person) in people.items():
        pieces = art.UNIFORMS[role][person["body"]]
        spec = staff.dress(person, pieces)
        out[key] = looks.ensure(spec)
    return out


def room(looks: dict) -> dict:
    """The blueprint. The room is 1312×992, both multiples of the Floor plan's 32 px room grid; you come in through a
    doorway in the bottom wall at its middle (x 656), so it goes with that over the door below it: above the Modern
    lobby (x 0, y -64, its door at 304) that's x -352, y -1056, on the grid and flush with the lobby's top wall. The
    lobby's door opens through both walls, so the room needs no door of its own."""
    W, H = 1312, 992
    PAD = 16   # what's placed below is laid out on a 1280-wide floor, PAD in from each side wall
    items = []

    def put(asset, x, y, facing="down", **props):
        items.append({"asset": asset, "x": x, "y": y, "facing": facing, "props": props})

    def figure(look, x, y, facing="down"):
        put("npc", x, y, facing, look=looks[look], name="")

    # Light first: flat pieces draw in the order they're placed.
    put("a:vegas_stage", 640, 404)
    for x, y in ((300, 596), (980, 586)):
        put("a:vegas_glow_warm", x, y)
    put("a:vegas_glow_warm", 196, 250)
    for x, y in ((1010, 330), (640, 740), (640, 946), (176, 870), (1104, 870), (420, 880), (860, 880)):
        put("a:vegas_glow_spot", x, y)

    # The stage: the Master Table on its raised deck, glass all round but the steps, a palm in each back corner.
    items.append({"asset": "table:master_table", "x": 640, "y": 290, "rot": 0,
                  "props": {"label": "Card Table", "limits": {"main": [500, 50000], "side": [300, 5000]}, "anim": "dust", "speed": 1.0}})
    for x in (432, 496, 560, 720, 784, 848):
        put("a:vegas_rail_glass_ew", x, 407)
    for x in (402, 878):
        for y in range(116, 405, 32):
            put("a:vegas_rail_glass_ns", x, y)
    put("a:vegas_planter_palm", 428, 120)
    put("a:vegas_planter_palm", 852, 120)
    put("a:vegas_led_column", 382, 436)
    put("a:vegas_led_column", 898, 436)
    put("a:vegas_video_wall", 640, 64)
    figure("host", 572, 454)

    # The pits.
    items.append({"asset": "table:roulette", "x": 300, "y": 640, "rot": 0, "props": {"label": "Roulette", "sign": "left"}})
    items.append({"asset": "table:craps", "x": 980, "y": 640, "rot": 0, "props": {"label": "Craps"}})
    put("a:vegas_pylon_roulette", 530, 484)
    put("a:vegas_pylon_craps", 752, 484)

    # The Amber Bar, top left: the back bar on the wall, the counter, its bartenders, stools and high-tops.
    put("a:vegas_back_bar", 196, 68)
    put("a:vegas_bar_counter", 196, 176)
    figure("bartender_f", 146, 134)
    figure("bartender_m", 252, 134)
    for x in (86, 130, 174, 218, 262, 306):
        put("a:vegas_bar_stool", x, 198)
    for x, y in ((96, 300), (214, 324), (322, 290)):
        put("a:vegas_high_top", x, y)
        put("a:vegas_bar_stool", x - 19, y + 2)
        put("a:vegas_bar_stool", x + 19, y + 2)
    figure("waitress", 356, 222)
    put("a:vegas_planter_palm", 42, 456)
    put("a:vegas_planter_trough", 196, 446)

    # The cashier, top right, with the cash machine beside it, and a lounge in front.
    put("a:vegas_cashier_cage", 1100, 170)
    figure("cashier_f", 1013, 140)
    figure("cashier_m", 1187, 140)
    put("a:vegas_atm", 942, 168)
    put("a:vegas_armchair", 954, 318, "right")
    put("a:vegas_armchair", 1066, 318, "left")
    put("a:vegas_side_table", 1010, 314)
    put("a:vegas_sofa", 1010, 376, "up")
    put("a:vegas_planter_palm", 1238, 456)
    put("a:vegas_planter_palm", 1238, 300)
    put("a:vegas_planter_trough", 1150, 418)

    # The back wall's sconces.
    for x in (372, 908, 1000, 1200):
        put("a:vegas_wall_sconce", x, 60)

    # Slots: two banks of six on the outside, two of four by the walkway, totems at the cross aisle.
    put("bank:6", 176, 872, slots=["startrek", "voyager", "armadillo", "pirates_of_the_carribean", "startrek", "voyager"])
    put("bank:6", 1104, 872, slots=["voyager", "startrek", "pirates_of_the_carribean", "armadillo", "voyager", "startrek"])
    put("bank:4", 420, 880, slots=["armadillo", "pirates_of_the_carribean", "armadillo", "pirates_of_the_carribean"])
    put("bank:4", 860, 880, slots=["pirates_of_the_carribean", "armadillo", "pirates_of_the_carribean", "armadillo"])
    put("a:vegas_pylon_slots", 546, 792)
    put("a:vegas_pylon_slots", 734, 792)

    # The way in: columns either side of the door, the chip tower where the aisles cross, palms in the corners.
    put("a:vegas_led_column", 546, 970)
    put("a:vegas_led_column", 734, 970)
    put("a:vegas_chip_sculpture", 640, 744)
    put("a:vegas_planter_palm", 42, 966)
    put("a:vegas_planter_palm", 1238, 966)

    gold = {"style": "inlay", "colour": "#c9a24a", "width": 4}
    walk = {"texture": "vegas_marble_white", "tint": "#ffffff", "shape": "rect", "radius": 0,
            "pattern": {"kind": "none", "colour": "#000000", "size": 16, "opacity": 30}, "border": gold}
    patches = [
        # walnut floors either side of the stage: the bar's and the cashier's lounge (black marble there ran into the stage)
        {**walk, "x": 8, "y": 70, "w": 372, "h": 400, "texture": "vegas_walnut", "border": {"style": "line", "colour": "#1a1210", "width": 2}},
        {**walk, "x": 928, "y": 70, "w": 344, "h": 382, "texture": "vegas_walnut", "border": {"style": "line", "colour": "#1a1210", "width": 2}},
        # the pits
        {**walk, "x": 92, "y": 468, "w": 452, "h": 236, "texture": "vegas_pit_carpet", "shape": "rounded", "radius": 28, "border": {"style": "double", "colour": "#c9a24a", "width": 6}},
        {**walk, "x": 752, "y": 470, "w": 492, "h": 236, "texture": "vegas_pit_carpet", "shape": "rounded", "radius": 28, "border": {"style": "double", "colour": "#c9a24a", "width": 6}},
        # marble walkways: the apron in front of the stage, the way in from the door, the cross aisle
        {**walk, "x": 352, "y": 412, "w": 576, "h": 52},
        {**walk, "x": 560, "y": 456, "w": 160, "h": 536},
        {**walk, "x": 16, "y": 712, "w": 1248, "h": 56},
        # the black marble medallion under the chip tower
        {**walk, "x": 584, "y": 700, "w": 112, "h": 80, "texture": "vegas_marble_black", "shape": "oval", "border": {"style": "double", "colour": "#d9b56a", "width": 5}},
    ]
    points = [
        {"name": "floor_spawn", "x": 640, "y": 936, "kind": "spawn", "weight": 1, "linger": 0},
        {"name": "bar", "x": 196, "y": 228, "kind": "wander", "weight": 3, "linger": 40},
        {"name": "high_tops", "x": 160, "y": 372, "kind": "wander", "weight": 2, "linger": 30},
        {"name": "lounge", "x": 1010, "y": 420, "kind": "wander", "weight": 2, "linger": 30},
        {"name": "cashier", "x": 1100, "y": 214, "kind": "wander", "weight": 1, "linger": 12},
        {"name": "stage_left", "x": 470, "y": 446, "kind": "wander", "weight": 1, "linger": 15},
        {"name": "stage_right", "x": 810, "y": 446, "kind": "wander", "weight": 1, "linger": 15},
        {"name": "aisle_west", "x": 300, "y": 740, "kind": "wander", "weight": 1, "linger": 8},
        {"name": "aisle_east", "x": 980, "y": 740, "kind": "wander", "weight": 1, "linger": 8},
        {"name": "chip_tower", "x": 600, "y": 780, "kind": "wander", "weight": 1, "linger": 10},
    ]
    zones = [
        {"x": 8, "y": 70, "w": 340, "h": 64, "kind": "block"},      # behind the bar
        {"x": 960, "y": 70, "w": 280, "h": 58, "kind": "block"},    # behind the cage
        {"x": 400, "y": 70, "w": 480, "h": 26, "kind": "block"},    # behind the stage
    ]
    for thing in items + points:
        thing["x"] += PAD
    for area in patches + zones:   # (one that ran to a side wall still does)
        left, right = area["x"] <= 8, area["x"] + area["w"] >= 1272
        area["x"] += PAD
        if left:
            area["w"], area["x"] = area["w"] + area["x"] - 8, 8
        if right:
            area["w"] = W - 8 - area["x"]
    return {"id": ROOM_ID, "name": "Casino Floor (Vegas)", "map_name": "Casino Floor", "placed": False,
            "x": -352, "y": -1056, "w": W, "h": H,
            "floor": {"texture": "vegas_carpet", "tint": "#ffffff"}, "patches": patches,
            "walls": {"style": "bronze", "sign": "", "sign_at": W / 2}, "doors": [], "items": items,
            "paths": {"points": points, "zones": zones}}


def _call(server: str, method: str, path: str, body=None):
    req = urllib.request.Request(server + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def send_room(server: str, looks: dict, place: bool) -> dict:
    """Put the room in the server's draft (replacing an earlier one, its items keeping their ids where the asset is
    the same, so the tables keep their styles, and staying placed or not; it goes back over the lobby's door)."""
    def call(method, path, body=None):
        return _call(server, method, path, body)
    view = call("GET", "/api/plan")
    draft = view["draft"]
    new = room(looks)
    old = next((r for r in draft["rooms"] if r["id"] == ROOM_ID), None)
    if old:
        new["placed"] = old["placed"]
        for it, was in zip(new["items"], old["items"]):
            if it["asset"] == was["asset"]:
                it["id"] = was["id"]
    if place:
        new["placed"] = True
    rooms = [r for r in draft["rooms"] if r["id"] != ROOM_ID] + [new]
    out = call("PUT", "/api/plan/draft", {"rooms": rooms, "spawn": draft["spawn"], "base_rev": draft["rev"]})
    mine = [p for p in out["problems"] if p["room"] == ROOM_ID]
    for p in mine:
        print("problem:", p["message"])
    saved = next(r for r in out["draft"]["rooms"] if r["id"] == ROOM_ID)
    return {i["id"]: i["asset"] for i in saved["items"] if i["asset"].startswith("table:")}


# ------------------------------------------------------------------ table styles
# Roulette and Craps in the master table's "Dark Modern" (Mike's card table style): charcoal felt, warm LED edge,
# mahogany and chrome, Montserrat in cream and gold.
STYLES = {
    "roulette": {"name": "Dark Modern", "design": {
        "felt": {"colour": "#2b2f33", "texture": "weave", "vignette": 0.45}, "border": "led", "led": "#ffd28a",
        "rail": {"wood": "mahogany", "armrest": "all", "leather": "#1b1a1a", "bead": "chrome"},
        "print": {"font": "montserrat", "ink": "#f1e4c4", "accent": "#d9b56a"},
        "numbers": {"red": "#b8322b", "black": "#0d0e10", "zero": "#1f8a52"}, "float": "steel",
        "wheel": {"wood": "match", "metal": "chrome"}, "chairs": {"frame": "gunmetal", "upholstery": "#1b1a1a"}}},
    "craps": {"name": "Dark Modern", "design": {
        "felt": {"colour": "#2b2f33", "texture": "weave", "vignette": 0.45},
        "rail": {"wood": "mahogany", "armrest": "all", "leather": "#1b1a1a", "bead": "chrome"},
        "print": {"font": "montserrat", "ink": "#f1e4c4", "accent": "#d9b56a", "red": "#c45454"},
        "rubber": "#141416", "rack": "steel", "dice": "amber"}},
}
STYLE_ID = "dark_modern"
KIND_OF = {"table:master_table": "cards", "table:roulette": "roulette", "table:craps": "craps"}


def apply_styles(server: str, tables: dict):
    """Each of the room's tables in Dark Modern: the Roulette and Craps styles made if they aren't there yet (an
    existing one is left as it is), and only tables without a style of their own assigned."""
    for tid, asset in tables.items():
        kind = KIND_OF.get(asset)
        if kind is None:
            continue
        have = _call(server, "GET", f"/api/table-styles?kind={kind}")
        if STYLE_ID not in have["styles"]:
            if kind not in STYLES:
                print(f"no {STYLE_ID} {kind} style to give {tid}")
                continue
            _call(server, "PUT", f"/api/table-styles/styles/{STYLE_ID}?kind={kind}", STYLES[kind])
        if tid not in have["tables"]:
            _call(server, "PUT", f"/api/table-styles/tables?kind={kind}", {"tables": {tid: STYLE_ID}})
            print(f"{tid}: {STYLE_ID}")


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default=str(ROOT / "server" / "data"), help="the data dir the art goes into (default: the live one)")
    ap.add_argument("--only", default="pieces,floors", help="what art to build: pieces, floors, both, or none")
    ap.add_argument("--no-room", action="store_true", help="don't send the room to a server")
    ap.add_argument("--server", default="http://127.0.0.1:8660", help="the server whose draft gets the room")
    ap.add_argument("--place", action="store_true", help="put the room on the plan (a dev instance), not in the library")
    args = ap.parse_args()
    data_dir = Path(args.data)
    lib = data_dir / "plan_assets"
    lib.mkdir(parents=True, exist_ok=True)
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    path = lib / "uploads.json"
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        data = {"assets": {}, "floors": {}}
    contact = []
    if "pieces" in only:
        for pid, piece in asyncio.run(render()).items():
            aid = PREFIX + pid
            files = {}
            for n, (f, url) in enumerate(piece["pictures"].items()):
                file = f"{aid}.png" if n == 0 else f"{aid}_{f}.png"
                im = png(url)
                im.save(lib / file)
                files[f] = file
                contact.append((f"{aid} {f}", im))
            data["assets"][aid] = entry(piece, files)
    if "floors" in only:
        for fid, (name, make) in FLOORS.items():
            im = make()
            im.save(lib / f"floor_{PREFIX}{fid}.png")
            data["floors"][PREFIX + fid] = {"name": name, "file": f"floor_{PREFIX}{fid}.png", "credit": CREDIT, "scale": SCALE}
            contact.append((PREFIX + fid, im))
    if only & {"pieces", "floors"}:
        tmp = lib / "uploads.tmp"
        tmp.write_text(json.dumps(data, indent=1))
        tmp.replace(path)
        write_contact(contact)
        print(f"{sum(1 for k in data['assets'] if k.startswith(PREFIX))} Vegas pieces and "
              f"{sum(1 for k in data['floors'] if k.startswith(PREFIX))} floors in {lib}; restart the server to load them")
    if not args.no_room:
        tables = send_room(args.server, staff_looks(data_dir), args.place)
        print("room", ROOM_ID, "in the draft at", args.server, "with tables", tables)
        apply_styles(args.server, tables)


def write_contact(items):
    cols, cell = 5, 300
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (40, 34, 38, 255))
    d = ImageDraw.Draw(sheet)
    for n, (name, im) in enumerate(items):
        x, y = (n % cols) * cell, (n // cols) * cell
        im = im.convert("RGBA")
        im.thumbnail((cell - 12, cell - 24), Image.LANCZOS)
        sheet.alpha_composite(im, (x + (cell - im.size[0]) // 2, y + 4))
        d.text((x + 4, y + cell - 16), name, fill=(255, 230, 150, 255))
    (ROOT / ".dev").mkdir(exist_ok=True)
    sheet.save(ROOT / ".dev" / "vegas_contact.png")


if __name__ == "__main__":
    main()
