#!/usr/bin/env python3
"""
Builds Casino World's generated art:

  client/assets/sprites/characters/<look>.png   one sheet per character look
  client/assets/sprites/characters/looks.json   the look ids, for the server and client
  client/assets/sprites/CREDITS.md              attribution for every LPC file used
  client/assets/tiles/carpet.png                the casino carpet tile (`build_art.py tiles` rebuilds just the tiles)
  client/assets/tiles/felt_grain.png            the grain drawn over the table felt
  client/assets/tiles/leather_grain.png         the fine grain on the leather padding of the dealers' rail

Characters are composited by the server's art module (server/casino_server/art.py)
from the Universal LPC Spritesheet Character Generator's layers, pinned to one
commit, so rebuilding is reproducible. Downloads are cached in server/lpc_cache/.

Sheet layout (64x64 frames, rows in LPC's up/left/down/right order):
  rows 0-3   walk, 9 frames
  rows 4-7   idle, 2 frames
  rows 8-11  sit (on a chair), 1 frame -- LPC's sit sheet column 2

Add or change a look in LOOKS below and rerun:
  python3 tools/build_art.py
"""
import json
import random
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from casino_server import art  # noqa: E402  (the shared compositor: layers, recolouring, sheets)

OUT_CHARS = ROOT / "client" / "assets" / "sprites" / "characters"
OUT_CREDITS = ROOT / "client" / "assets" / "sprites" / "CREDITS.md"
OUT_TILES = ROOT / "client" / "assets" / "tiles"
COMMIT = art.COMMIT
FRAME, WALK_FRAMES, IDLE_FRAMES = art.FRAME, art.WALK_FRAMES, art.IDLE_FRAMES


def look(body, skin, hair, top, bottom, shoes, **extra):
    return {"body": body, "skin": skin, "hair": list(hair), "top": list(top), "bottom": list(bottom),
            "shoes": list(shoes), **{k: list(v) for k, v in extra.items()}}


# The looks that ship inside the game (designed NPCs are built by the server instead).
LOOKS = {
    "player_default": look("male", "light", ("plain", "dark_brown"), ("longsleeve", "blue"), ("pants", "charcoal"), ("shoes", "black")),
    # The reference photo's dealer: white collared shirt, black vest and bow tie.
    "dealer": look("male", "brown", ("afro", "black"), ("formal", "white"), ("formal", "black"), ("shoes", "black"),
                   over=("vest", "black"), neck=("bowtie", "black")),
    "npc_1": look("male", "olive", ("parted", "black"), ("longsleeve", "maroon"), ("pants", "navy"), ("shoes", "brown")),
    "npc_2": look("female", "light", ("bob", "blonde"), ("longsleeve", "teal"), ("pants", "black"), ("shoes", "black")),
    "npc_3": look("male", "black", ("buzzcut", "black"), ("longsleeve", "white"), ("pants", "tan"), ("shoes", "black")),
    "npc_4": look("female", "amber", ("bangsshort", "chestnut"), ("longsleeve", "rose"), ("pants", "navy"), ("shoes", "brown")),
    "npc_5": look("male", "light", ("messy1", "ginger"), ("longsleeve", "forest"), ("pants", "gray"), ("shoes", "black")),
    "npc_6": look("female", "bronze", ("afro", "dark_brown"), ("longsleeve", "lavender"), ("pants", "charcoal"), ("shoes", "black")),
    "npc_7": look("male", "taupe", ("plain", "gray"), ("longsleeve", "sky"), ("pants", "walnut"), ("shoes", "brown")),
    "npc_8": look("female", "light", ("parted", "raven"), ("longsleeve", "red"), ("pants", "slate"), ("shoes", "black")),
}


def write_credits():
    lines = ["# Art credits", "",
             "Character sprites are built from the "
             "[Universal LPC Spritesheet Character Generator]"
             f"(https://github.com/LiberatedPixelCup/Universal-LPC-Spritesheet-Character-Generator/tree/{COMMIT}) "
             "by `server/casino_server/art.py` (the looks in the game by `tools/build_art.py`; the NPCs "
             "designed on the admin page by the server, which also lists these at /credits). "
             "They're licensed under the terms below (CC-BY-SA 3.0 / GPL 3.0 / OGA-BY 3.0 as listed); "
             "derivative sprite sheets carry the same licences.", ""]
    for c in art.credits():
        lines.append(f"## {c['name']} — `{c['file']}`")
        lines.append(f"- **Authors:** {', '.join(c['authors'])}")
        lines.append(f"- **Licences:** {', '.join(c['licenses'])}")
        for url in c["urls"]:
            lines.append(f"- {url}")
        lines.append("")
    OUT_CREDITS.write_text("\n".join(lines))


# ---------------------------------------------------------------------- carpet
CARPET_COLOUR = (31, 58, 62)  # deep slate teal, so the red felt tables stand out


def build_carpet():
    """A 128x128 seamless carpet tile: one plain colour with a fine fibre
    texture and soft mottling (both wrap, so the tile repeats invisibly)."""
    from PIL import ImageFilter
    rng = random.Random(7)
    size = 128

    def wrapped_noise(spread, blur):
        noise = Image.new("L", (size, size))
        noise.putdata([128 + rng.randint(-spread, spread) for _ in range(size * size)])
        if blur:  # blur a 3x3 tiling and keep the middle, so the edges still meet
            big = Image.new("L", (size * 3, size * 3))
            for ty in range(3):
                for tx in range(3):
                    big.paste(noise, (tx * size, ty * size))
            noise = big.filter(ImageFilter.GaussianBlur(blur)).crop((size, size, size * 2, size * 2))
        return noise.load()

    fibre, mottle = wrapped_noise(10, 0), wrapped_noise(90, 9)
    img = Image.new("RGBA", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            n = (fibre[x, y] - 128) * 0.6 + (mottle[x, y] - 128) * 0.35
            px[x, y] = tuple(max(0, min(255, round(c + n))) for c in CARPET_COLOUR) + (255,)
    OUT_TILES.mkdir(parents=True, exist_ok=True)
    img.save(OUT_TILES / "carpet.png")


def build_felt_grain():
    """A 64x64 seamless grain for the table felt: white and black specks with
    soft alpha, drawn over the felt colour so it reads as woven baize."""
    rng = random.Random(11)
    size = 64
    img = Image.new("RGBA", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            # fine weave: a faint diagonal twill plus random fibre specks
            n = rng.gauss(0, 1) + (0.35 if (x + y) % 4 < 2 else -0.35)
            px[x, y] = (255, 255, 255, min(255, round(n * 40))) if n > 0 else (0, 0, 0, min(255, round(-n * 55)))
    OUT_TILES.mkdir(parents=True, exist_ok=True)
    img.save(OUT_TILES / "felt_grain.png")


def build_leather_grain():
    """A 64x64 seamless fine grain for smooth leather: soft, barely-there light and dark
    flecks (blurred noise), drawn faintly over the leather colour."""
    from PIL import ImageFilter
    rng = random.Random(31)
    size = 64
    noise = Image.new("L", (size, size))
    noise.putdata([128 + round(rng.gauss(0, 40)) for _ in range(size * size)])
    big = Image.new("L", (size * 3, size * 3))
    for ty in range(3):
        for tx in range(3):
            big.paste(noise, (tx * size, ty * size))
    noise = big.filter(ImageFilter.GaussianBlur(0.7)).crop((size, size, size * 2, size * 2)).load()
    img = Image.new("RGBA", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            n = (noise[x, y] - 128) / 128
            px[x, y] = (255, 230, 200, min(255, round(n * 160))) if n > 0 else (0, 0, 0, min(255, round(-n * 200)))
    OUT_TILES.mkdir(parents=True, exist_ok=True)
    img.save(OUT_TILES / "leather_grain.png")


def main():
    OUT_CHARS.mkdir(parents=True, exist_ok=True)
    for name, spec in LOOKS.items():
        print(f"building {name}")
        art.build_sheet(spec).save(OUT_CHARS / f"{name}.png")
    (OUT_CHARS / "looks.json").write_text(json.dumps({
        "frame": FRAME, "walk_frames": WALK_FRAMES, "idle_frames": IDLE_FRAMES,
        "looks": list(LOOKS), "npc_looks": [n for n in LOOKS if n.startswith("npc_")],
    }, indent=2) + "\n")
    write_credits()
    build_carpet()
    build_felt_grain()
    build_leather_grain()
    print(f"wrote {len(LOOKS)} looks, CREDITS.md, carpet.png, felt_grain.png and leather_grain.png")


if __name__ == "__main__":
    if sys.argv[1:] in (["carpet"], ["tiles"]):  # just the tiles, no sprite downloads
        build_carpet()
        build_felt_grain()
        build_leather_grain()
        print("wrote carpet.png, felt_grain.png and leather_grain.png")
    else:
        main()
