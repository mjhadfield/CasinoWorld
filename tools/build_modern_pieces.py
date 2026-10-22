#!/usr/bin/env python3
"""
Draws the Modern lobby's furniture (tools/modern_pieces/pieces.js, designed on the "Modern Lobby" mockup) and installs
it in a data dir's floor plan library as uploads, so each piece can be edited or deleted on the admin page's
Floor plan > Assets like any other upload:

  <data>/plan_assets/modern_<id>.png (+ modern_<id>_<facing>.png)   the pictures
  <data>/plan_assets/floor_<id>.png                                 the floor tiles (porcelain, basalt)
  <data>/plan_assets/uploads.json                                   their entries, merged in (other uploads stay)

Running it again redraws them all, bringing back any that were deleted (--only picks some). Chromium draws them (the
server's venv has Playwright). Restart the server afterwards so the library picks them up:
  server/.venv/bin/python tools/build_modern_pieces.py [--data server/data] [--only sofa,atm]
A contact sheet of everything goes to .dev/modern_pieces_contact.png.
"""
import argparse
import asyncio
import base64
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "tools" / "modern_pieces" / "pieces.js"
CREDIT = "Drawn for Casino World's Modern lobby (tools/modern_pieces)"
# The mockup's groups, as the library's categories.
CATEGORY = {
    "reception_side": "Tables & desks", "reception_front": "Tables & desks", "back_credenza": "Tables & desks",
    "coffee_table_round": "Tables & desks", "side_table": "Tables & desks",
    "sofa": "Seating", "lounge_chair": "Seating", "bench_modern": "Seating",
    "arc_lamp": "Lighting", "planter_fig": "Plants", "planter_snake": "Plants", "rug_round": "Rugs", "runner": "Rugs",
    "stanchion_ns": "Decor", "stanchion_ew": "Decor", "atm": "Decor", "info_kiosk": "Decor", "console_flowers": "Decor",
    "dice_sculpture": "Statues & fountains", "jackpot_screen": "Wall decor", "art_canvas": "Wall decor",
}
# Facings drawn as another facing turned over.
MIRRORS = {"lounge_chair": {"right": "left"}, "reception_side": {"right": "left"}}


async def render() -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content("<!doctype html><meta charset=utf-8><script>" + JS.read_text() + "</script>")
        out = await page.evaluate("renderAll()")
        await browser.close()
    return out


def png(data_url: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1]))).convert("RGBA")


def entry(pid: str, piece: dict, files: dict) -> dict:
    """The library entry: every facing the piece has (down always, for the palette), mirrors, per-facing shapes."""
    w, h = piece["size"]
    ax, ay = piece["anchor"]
    rect = [-ax, -ay, w, h]
    body = piece["body"] if piece["mount"] == "floor" else None
    first = next(iter(files))
    facings = {f: {"file": files[f], "anchor": [ax, ay]} for f in files}
    facings.setdefault("down", {"file": files[first], "anchor": [ax, ay]})
    for f, of in MIRRORS.get(pid, {}).items():
        facings[f] = {**facings[of], "mirror": True}
    a = {"name": piece["name"], "category": CATEGORY.get(pid, "Decor"), "mount": piece["mount"], "credit": CREDIT,
         "facings": facings, "rect": rect, "body": body}
    others = [f for f in facings if f != "down"]
    if others:
        a["by_facing"] = {f: {"rect": rect, "body": body} for f in others}
    if piece.get("screen"):
        a["screen"] = piece["screen"]
    return a


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default=str(ROOT / "server" / "data"), help="the server's data dir (default: the live one)")
    ap.add_argument("--only", default="", help="comma-separated piece ids (as in pieces.js) to install")
    args = ap.parse_args()
    lib = Path(args.data) / "plan_assets"
    lib.mkdir(parents=True, exist_ok=True)
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    drawn = asyncio.run(render())
    path = lib / "uploads.json"
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        data = {"assets": {}, "floors": {}}
    contact = []
    for pid, piece in drawn["pieces"].items():
        if only and pid not in only:
            continue
        aid = "modern_" + pid
        files = {}
        for n, (f, url) in enumerate(piece["pictures"].items()):
            file = f"{aid}.png" if n == 0 else f"{aid}_{f}.png"
            im = png(url)
            im.save(lib / file)
            files[f] = file
            contact.append((f"{aid} {f}", im))
        data["assets"][aid] = entry(pid, piece, files)
    for fid, fl in drawn["floors"].items():
        if only and fid not in only:
            continue
        im = png(fl["png"])
        im.save(lib / f"floor_{fid}.png")
        data["floors"][fid] = {"name": fl["name"], "file": f"floor_{fid}.png", "credit": CREDIT}
        contact.append((fid, im))
    tmp = lib / "uploads.tmp"
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)
    write_contact(contact)
    print(f"{sum(1 for k in data['assets'] if k.startswith('modern_'))} modern pieces and "
          f"{len(drawn['floors'])} floors in {lib}; restart the server to load them")


def write_contact(items):
    cols, cell = 6, 240
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (34, 34, 40, 255))
    d = ImageDraw.Draw(sheet)
    for n, (name, im) in enumerate(items):
        x, y = (n % cols) * cell, (n // cols) * cell
        k = max(1, min(3, int((cell - 24) / max(im.size))))
        big = im.resize((im.size[0] * k, im.size[1] * k), Image.NEAREST)
        if max(big.size) > cell - 20:
            big.thumbnail((cell - 20, cell - 20), Image.NEAREST)
        sheet.alpha_composite(big, (x + (cell - big.size[0]) // 2, y + 4))
        d.text((x + 4, y + cell - 14), name, fill=(255, 230, 150, 255))
    (ROOT / ".dev").mkdir(exist_ok=True)
    sheet.save(ROOT / ".dev" / "modern_pieces_contact.png")


if __name__ == "__main__":
    main()
