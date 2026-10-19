"""Cut the Star Trek reference sheet (5x4 grid) into one padded 1024² reference per symbol.
usage: startrek_crop.py <sheet.png> <out_dir>"""
import sys
from pathlib import Path
from PIL import Image
NAMES = ["delta", "enterprise", "kirk", "spock", "worf",
         "earth", "red_planet", "nebula", "communicator", "phaser",
         "wild", "scatter", "red_delta", "mug", "ds9",
         "A", "K", "Q", "J", "10"]
sheet = Image.open(sys.argv[1]).convert("RGB"); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
# Measured on the 1536x1024 sheet: the rows and columns aren't evenly spaced.
XS, YS = [0, 305, 625, 920, 1195, 1536], [0, 298, 548, 822, 1024]
for i, name in enumerate(NAMES):
    c, r = i % 5, i // 5
    box = (XS[c], YS[r], XS[c + 1], YS[r + 1])
    cell = sheet.crop(box)
    side = max(cell.size)
    sq = Image.new("RGB", (side, side), (8, 12, 28))
    sq.paste(cell, ((side - cell.width) // 2, (side - cell.height) // 2))
    sq.resize((1024, 1024), Image.LANCZOS).save(out / f"{name}.png")
    print(name)
