"""Cut the Star Trek reference sheets into one padded 1024² reference per symbol.
usage (from docs/slots/startrek): python ../tools/startrek_crop.py   → ref/<name>.png"""
from pathlib import Path
from PIL import Image

def grid(names, xs, ys):
    """Boxes for a sheet laid out in rows: names row by row, cell edges xs/ys."""
    return {n: (xs[i % 5], ys[i // 5], xs[i % 5 + 1], ys[i // 5 + 1]) for i, n in enumerate(names)}

# Measured on the 1536x1024 sheets: the rows and columns aren't evenly spaced.
SHEETS = {
    "source/sheet.png": grid(["delta", "enterprise", "kirk", "spock", "worf",
                              "earth", "red_planet", "nebula", "communicator", "phaser",
                              "wild", "scatter", "red_delta", "mug", "ds9",
                              "A", "K", "Q", "J", "10"],
                             [0, 305, 625, 920, 1195, 1536], [0, 298, 548, 822, 1024]),
    # Sheet 2 is framed tiles with grey blanks; only the real tiles are cut.
    "source/sheet2.png": {**grid(["enterprise_d", "borg_cube", "bird_of_prey", "warbird", "delta_gold",
                                  "picard", "data", "worf_tng", "troi", "obrien"],
                                 [12, 312, 616, 920, 1222, 1524], [12, 280, 546]),
                          "tricorder": (634, 548, 912, 780), "gas_giant": (1228, 786, 1524, 1016)},
}
out = Path("ref"); out.mkdir(exist_ok=True)
for sheet, boxes in SHEETS.items():
    im = Image.open(sheet).convert("RGB")
    for name, box in boxes.items():
        cell = im.crop(box)
        side = max(cell.size)
        sq = Image.new("RGB", (side, side), (8, 12, 28))
        sq.paste(cell, ((side - cell.width) // 2, (side - cell.height) // 2))
        sq.resize((1024, 1024), Image.LANCZOS).save(out / f"{name}.png")
