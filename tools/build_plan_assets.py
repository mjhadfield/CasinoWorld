#!/usr/bin/env python3
"""
Builds the floor plan's built-in asset library from LPC packs on OpenGameArt: furniture and decor cut out of their
sprite sheets, rugs, and floor textures, in the Liberated Pixel Cup style the casino's people are drawn in.

  server/plan_assets/<id>.png          one picture per asset (per facing, when it has more than one)
  server/plan_assets/floors/<id>.png   floor textures (seamless tiles)
  server/plan_assets/catalogue.json    what plan_assets.py loads: each asset's name, category, how it stands
                                       (floor / flat / wall), its pictures and their anchor, its footprint
  server/plan_assets/CREDITS.md        every pack's credits, in full (their licences require it)

Downloads are pinned by checksum and cached in .dev/plan_assets_src/. Zips are read in memory (only the named
pictures and credit files). Each cut is a box on a sheet, trimmed to what's drawn in it. Run it with the server's
venv (it needs Pillow), then look at .dev/plan_assets_src/contact.png:
  server/.venv/bin/python tools/build_plan_assets.py
"""
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".dev" / "plan_assets_src"
OUT = ROOT / "server" / "plan_assets"
OGA = "https://opengameart.org/sites/default/files/"

# Pack: (file, sha256 prefix, the picture inside a zip, its credits file inside the zip, its page, licences, credit)
PACKS = {
    "wood": ("dark-wood_4.png", "04c47b995e6c768e", None, None, "https://opengameart.org/content/lpc-wooden-furniture",
             "CC-BY-SA 4.0 / CC-BY-SA 3.0 / GPL 3.0", None),
    "wood_credits": ("credits-furniture.txt_.zip", "793bca5fca20c968", None, "CREDITS-furniture.txt", None, None, None),
    "upholstery": ("upholstery_3.png", "3e1f3b7566506a03", None, None, "https://opengameart.org/content/lpc-upholstery",
                   "CC-BY 4.0 / CC-BY 3.0 / CC-BY-SA 4.0 / CC-BY-SA 3.0 / GPL 3.0 / OGA-BY 3.0",
                   '"[LPC] Upholstery" by bluecarrot16, Lanea Zimmerman (Sharm). Please link back to '
                   "https://opengameart.org/content/lpc-upholstery and https://opengameart.org/content/lpc-interior-castle-tiles ."),
    "tavern_furniture": ("lpc-tavern.zip", "f8a5ac0db7456c1f", "lpc-tavern/tavern-furniture.png", "lpc-tavern/CREDITS-tavern.txt",
                         "https://opengameart.org/content/lpc-tavern", "CC-BY-SA 3.0", None),
    "tavern_deco": ("lpc-tavern.zip", "f8a5ac0db7456c1f", "lpc-tavern/tavern-deco.png", "lpc-tavern/CREDITS-tavern.txt",
                    "https://opengameart.org/content/lpc-tavern", "CC-BY-SA 3.0", None),
    "floors": ("lpc-floors.zip", "68403971cdc51c58", "lpc-floors/floors.png", "lpc-floors/CREDITS-floors.txt",
               "https://opengameart.org/content/lpc-floors", "CC-BY-SA 4.0", None),
    "medieval": ("decoration_medieval.zip", "c061a00c301aec11", "decoration_medieval/decorations-medieval.png",
                 "decoration_medieval/CREDITS-decorations-medieval.txt",
                 "https://opengameart.org/content/lpc-medieval-village-decorations", "CC-BY-SA 4.0 / CC-BY-SA 3.0", None),
    "plant": ("potted_plant.png", "ac186707f34fbac7", None, None, "https://opengameart.org/content/potted-plant",
              "CC-BY 3.0 / CC-BY 4.0 / OGA-BY 3.0 / OGA-BY 4.0",
              "Potted plant by Jordan Irwin (AntumDeluge), from Arum Maculatum by Firkin and \"Die Giftpflanzen Deutschlands\", "
              "Peter Esser, 1910 (attribution to Firkin and Peter Esser optional)."),
    "fountain": ("WaterFountain.png", "0e2dc51f551c9329", None, None, "https://opengameart.org/content/lpc-water-fountain",
                 "CC-BY 3.0", "LPC water fountain by Lanea Zimmerman (Sharm); submitted by Curt. Attribution: Curt, Sharm, "
                 "William.Thompsonj, https://opengameart.org/content/lpc-water-fountain"),
}

# id: (name, category, mount, pack, box (x0, y0, x1, y1) on its sheet, body depth (px) or None for the default)
# A body is the footprint on the floor that blocks walking: the bottom `depth` px of the picture, a little in from
# its sides. Rugs (flat) and wall pieces have none.
ASSETS = {
    # Seating
    "bar_stool": ("Bar stool", "Seating", "floor", "tavern_furniture", (575, 395, 612, 440), 8),
    "stool": ("Round stool", "Seating", "floor", "tavern_furniture", (575, 204, 612, 244), 8),
    "bench": ("Bench", "Seating", "floor", "wood", (262, 852, 346, 898), 14),
    "low_bench": ("Low bench", "Seating", "floor", "wood", (270, 896, 340, 926), 12),
    "sofa": ("Sofa", "Seating", "floor", "upholstery", (194, 126, 253, 161), 16),
    "long_sofa": ("Long sofa", "Seating", "floor", "upholstery", (126, 223, 194, 257), 16),
    "ornate_sofa": ("Ornate sofa", "Seating", "floor", "upholstery", (0, 335, 64, 370), 16),
    "armchair": ("Armchair", "Seating", "floor", "upholstery", (126, 158, 162, 193), 14),
    "ottoman": ("Ottoman", "Seating", "floor", "upholstery", (222, 351, 258, 385), 12),
    # Tables & desks
    "round_table": ("Round table", "Tables & desks", "floor", "wood", (223, 225, 290, 283), 26),
    "long_table": ("Long table", "Tables & desks", "floor", "wood", (0, 231, 98, 278), 20),
    "coffee_table": ("Coffee table", "Tables & desks", "floor", "wood", (326, 256, 410, 285), 14),
    "desk": ("Writing desk", "Tables & desks", "floor", "wood", (64, 767, 128, 801), 18),
    "desk_hutch": ("Desk with shelves", "Tables & desks", "floor", "wood", (64, 705, 128, 767), 18),
    "reception_desk": ("Reception desk", "Tables & desks", "floor", "wood", (128, 705, 192, 767), 18),
    # Bar & counters
    "bar_counter": ("Long bar counter", "Bar & counters", "floor", "tavern_furniture", (3, 9, 60, 130), None),
    "wine_rack_green": ("Wine rack (green)", "Bar & counters", "floor", "tavern_furniture", (740, 12, 824, 110), 20),
    "wine_rack_red": ("Wine rack (red)", "Bar & counters", "floor", "tavern_furniture", (836, 12, 916, 110), 20),
    "wine_rack_mixed": ("Wine rack (mixed)", "Bar & counters", "floor", "tavern_furniture", (932, 12, 1012, 110), 20),
    "barrel": ("Barrel", "Bar & counters", "floor", "tavern_deco", (0, 16, 33, 63), 14),
    "barrel_stack": ("Stacked barrels", "Bar & counters", "floor", "tavern_deco", (32, 31, 97, 94), 22),
    "keg": ("Keg with tap", "Bar & counters", "floor", "tavern_deco", (0, 62, 33, 98), 14),
    # Plants
    "plant_low": ("Potted plant", "Plants", "floor", "plant", (0, 0, 32, 64), 10),
    "plant_tall": ("Tall potted plant", "Plants", "floor", "plant", (32, 0, 64, 64), 10),
    "plant_leaning": ("Leaning potted plant", "Plants", "floor", "plant", (64, 0, 96, 64), 10),
    # Lighting
    "table_lamp": ("Table lamp", "Lighting", "floor", "upholstery", (2, 62, 30, 97), 8),
    "candelabra": ("Candelabra", "Lighting", "floor", "tavern_deco", (290, 415, 319, 470), 8),
    "lantern": ("Lantern", "Lighting", "floor", "tavern_deco", (416, 447, 449, 482), 8),
    # Statues & fountains
    "fountain": ("Fountain", "Statues & fountains", "floor", "fountain", (0, 0, 64, 96), 34),
    "stone_fountain": ("Stone fountain", "Statues & fountains", "floor", "medieval", (0, 514, 66, 578), 30),
    "statue_lady": ("Lady statue", "Statues & fountains", "floor", "medieval", (2, 292, 30, 354), 12),
    "statue_kneeling": ("Kneeling statue", "Statues & fountains", "floor", "medieval", (34, 290, 62, 354), 12),
    "statue_hooded": ("Hooded statue", "Statues & fountains", "floor", "medieval", (97, 286, 127, 354), 14),
    "statue_cherub": ("Cherub statue", "Statues & fountains", "floor", "medieval", (127, 290, 159, 352), 14),
    "bird_bath": ("Bird bath", "Statues & fountains", "floor", "medieval", (128, 228, 158, 290), 10),
    "pedestal": ("Pedestal", "Statues & fountains", "floor", "medieval", (97, 230, 126, 286), 12),
    # Decor
    "grand_piano": ("Grand piano", "Decor", "floor", "wood", (0, 847, 66, 925), 28),
    "upright_piano": ("Upright piano", "Decor", "floor", "wood", (78, 841, 147, 898), 14),
    "grandfather_clock": ("Grandfather clock", "Decor", "floor", "wood", (261, 746, 283, 821), 10),
    "fireplace": ("Fireplace", "Decor", "floor", "wood", (383, 750, 481, 826), 16),
    "wardrobe": ("Wardrobe", "Decor", "floor", "wood", (0, 627, 63, 704), 14),
    "bookcase": ("Bookcase", "Decor", "floor", "wood", (352, 128, 384, 187), 10),
    "bookcase_full": ("Bookcase (full)", "Decor", "floor", "wood", (384, 128, 416, 187), 10),
    "folding_screen": ("Folding screen", "Decor", "floor", "upholstery", (128, 64, 160, 128), 8),
    # Rugs
    "rug_red": ("Red rug", "Rugs", "flat", "floors", (192, 64, 288, 160), None),
    "rug_blue": ("Blue rug", "Rugs", "flat", "floors", (288, 224, 384, 320), None),
    "rug_green": ("Green rug", "Rugs", "flat", "floors", (192, 384, 288, 480), None),
    "rug_gold": ("Gold rug", "Rugs", "flat", "floors", (192, 544, 288, 640), None),
    "rug_red_large": ("Large red rug", "Rugs", "flat", "floors", (386, 960, 510, 1056), None),
    "rug_green_large": ("Large green rug", "Rugs", "flat", "floors", (510, 960, 638, 1056), None),
    "rug_blue_large": ("Large blue rug", "Rugs", "flat", "floors", (638, 960, 766, 1056), None),
    "rug_gold_large": ("Large gold rug", "Rugs", "flat", "floors", (766, 960, 896, 1056), None),
    "bear_rug": ("Bearskin rug", "Rugs", "flat", "tavern_deco", (417, 1092, 507, 1151), None),
    # Wall decor
    "banner_cream": ("Cream banner", "Wall decor", "wall", "tavern_deco", (288, 1312, 320, 1376), None),
    "banner_blue": ("Blue banner", "Wall decor", "wall", "tavern_deco", (384, 1312, 416, 1376), None),
    "banner_green": ("Green banner", "Wall decor", "wall", "tavern_deco", (416, 1312, 448, 1376), None),
    "banner_red": ("Red banner", "Wall decor", "wall", "tavern_deco", (448, 1312, 480, 1376), None),
}
# Other ways an asset faces: id: {facing: (pack, box) or "mirror:<facing>"}.
FACINGS = {
    "armchair": {"up": ("upholstery", (126, 191, 162, 225)), "left": ("upholstery", (162, 158, 187, 193)), "right": "mirror:left"},
}

# Floor textures: id: (name, box) on the floors sheet; each box is one seamless tile.
FLOORS = {
    "carpet_green": ("Green carpet", (256, 672, 320, 704)),
    "carpet_red": ("Red carpet", (256, 704, 320, 736)),
    "carpet_blue": ("Blue carpet", (256, 736, 320, 768)),
    "carpet_gold": ("Gold carpet", (256, 800, 320, 832)),
    "herringbone": ("Herringbone oak", (0, 1184, 64, 1248)),
    "planks": ("Oak planks", (192, 1248, 256, 1312)),
    "parquet_dark": ("Dark parquet", (64, 1312, 128, 1376)),
    "marble_tiles": ("Marble tiles", (64, 1644, 128, 1676)),
    "stone_slabs": ("Stone slabs", (384, 1644, 448, 1708)),
}


def fetch(file: str, sha: str) -> bytes:
    path = CACHE / file
    if not path.is_file():
        CACHE.mkdir(parents=True, exist_ok=True)
        print("downloading", file)
        with urllib.request.urlopen(OGA + file, timeout=60) as r:
            path.write_bytes(r.read())
    data = path.read_bytes()
    if not hashlib.sha256(data).hexdigest().startswith(sha):
        raise SystemExit(f"{file}: not the file this was made from (checksum); delete {path} and check the source")
    return data


def member(data: bytes, name: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read(name)


_sheets = {}


def sheet(pack: str) -> Image.Image:
    if pack not in _sheets:
        file, sha, inner = PACKS[pack][:3]
        data = fetch(file, sha)
        _sheets[pack] = Image.open(io.BytesIO(member(data, inner) if inner else data)).convert("RGBA")
    return _sheets[pack]


def cut(pack: str, box) -> Image.Image:
    im = sheet(pack).crop(box)
    bb = im.getchannel("A").point(lambda a: 255 if a >= 16 else 0).getbbox()
    return im.crop(bb) if bb else im


def body(w: int, h: int, depth: int | None) -> list:
    d = depth if depth is not None else max(8, min(28, round(h * 0.4)))
    inset = max(1, round(w * 0.08))
    return [-w / 2 + inset, -d, w - 2 * inset, d]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "floors").mkdir(exist_ok=True)
    catalogue = {"assets": {}, "floors": {}}
    contact = []
    for aid, (name, cat, mount, pack, box, depth) in ASSETS.items():
        im = cut(pack, box)
        im.save(OUT / f"{aid}.png")
        w, h = im.size
        anchor = [w // 2, h // 2] if mount == "flat" else [w // 2, h]
        entry = {"name": name, "category": cat, "mount": mount, "credit": pack.split("_")[0] if pack.startswith("tavern") else pack,
                 "facings": {"down": {"file": f"{aid}.png", "anchor": anchor}},
                 "rect": [-anchor[0], -anchor[1], w, h], "body": body(w, h, depth) if mount == "floor" else None}
        for facing, src in FACINGS.get(aid, {}).items():
            if isinstance(src, str):
                other = entry["facings"][src.split(":")[1]]
                entry["facings"][facing] = {**other, "mirror": True}
                entry.setdefault("by_facing", {})[facing] = entry["by_facing"][src.split(":")[1]]
                continue
            fim = cut(*src)
            fim.save(OUT / f"{aid}_{facing}.png")
            fw, fh = fim.size
            entry["facings"][facing] = {"file": f"{aid}_{facing}.png", "anchor": [fw // 2, fh]}
            entry.setdefault("by_facing", {})[facing] = {"rect": [-(fw // 2), -fh, fw, fh], "body": body(fw, fh, depth)}
            contact.append((f"{aid}_{facing}", fim))
        catalogue["assets"][aid] = entry
        contact.append((aid, im))
    for fid, (name, box) in FLOORS.items():
        tile = sheet("floors").crop(box)
        tile.save(OUT / "floors" / f"{fid}.png")
        catalogue["floors"][fid] = {"name": name, "file": f"floors/{fid}.png", "credit": "floors"}
        big = Image.new("RGBA", (tile.size[0] * 3, tile.size[1] * 3))
        for i in range(3):
            for j in range(3):
                big.paste(tile, (i * tile.size[0], j * tile.size[1]))
        contact.append((fid, big))
    (OUT / "catalogue.json").write_text(json.dumps(catalogue, indent=1) + "\n")
    write_credits()
    write_contact(contact)
    print(f"{len(catalogue['assets'])} assets, {len(catalogue['floors'])} floors in {OUT}")


def write_credits():
    lines = ["# The floor plan's built-in assets: credits", "",
             "Cut from these packs by `tools/build_plan_assets.py`. Each pack's own credits follow in full, as their",
             "licences ask. Pick any one of a pack's licences.", ""]
    done = set()
    for key, (file, sha, inner, credits, page, licences, notice) in PACKS.items():
        if page is None or (file, credits) in done:
            continue
        done.add((file, credits))
        lines += [f"## {key.split('_')[0].capitalize() if key.startswith('tavern') else key.capitalize()}: {page}", "",
                  f"Licences: {licences}", ""]
        if notice:
            lines += [notice, ""]
        text = None
        if credits:
            text = member(fetch(file, sha), credits).decode("utf-8", "replace")
        elif key == "wood":
            text = member(fetch(*PACKS["wood_credits"][:2]), PACKS["wood_credits"][3]).decode("utf-8", "replace")
        if text:
            lines += ["```", text.strip(), "```", ""]
    (OUT / "CREDITS.md").write_text("\n".join(lines))


def write_contact(items):
    S, cols, cell = 2, 8, 220
    rows = (len(items) + cols - 1) // cols
    sheet_ = Image.new("RGBA", (cols * cell, rows * cell), (34, 52, 52, 255))
    d = ImageDraw.Draw(sheet_)
    for n, (name, im) in enumerate(items):
        x, y = (n % cols) * cell, (n // cols) * cell
        k = min(S, (cell - 20) / max(im.size))
        big = im.resize((max(1, int(im.size[0] * k)), max(1, int(im.size[1] * k))), Image.NEAREST)
        sheet_.alpha_composite(big, (x + (cell - big.size[0]) // 2, y + 4))
        d.text((x + 4, y + cell - 14), name, fill=(255, 230, 150, 255))
    sheet_.save(CACHE / "contact.png")


if __name__ == "__main__":
    main()
