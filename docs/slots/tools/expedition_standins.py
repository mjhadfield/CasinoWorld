"""The expedition's stand-in pictures (your ship, an unexplored planet, what a planet can hold, a hazard and the final
destination), drawn as plain vector shapes into server/slot_art/armadillo/flux2/, where the Slot design wizard finds
every art slot's stand-in. A slot replaces them on its Bonus games step.
Run: python3 expedition_standins.py"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parents[3] / "server" / "slot_art" / "armadillo" / "flux2"
S = 4   # drawn 4x, then shrunk to 512 for smooth edges
INK = (14, 18, 34)
HULL, HULL_HI, HULL_LO = (196, 204, 216), (236, 240, 246), (120, 128, 144)
GLOW = (110, 190, 255)
GOLD, GOLD_HI, GOLD_LO = (240, 190, 70), (255, 236, 160), (150, 100, 30)
VIOLET, VIOLET_LO = (150, 110, 230), (70, 50, 130)
RED = (230, 70, 60)
GREEN = (90, 230, 120)


def canvas():
    return Image.new("RGBA", (512 * S, 512 * S), (0, 0, 0, 0))


def pts(xy):
    return [(x * S, y * S) for x, y in xy]


def box(b):
    return [v * S for v in b]


def glow(im, b, colour, blur=14):
    g = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse(box(b), fill=colour)
    return Image.alpha_composite(im, g.filter(ImageFilter.GaussianBlur(blur * S)))


def finish(im, name):
    im.resize((512, 512), Image.LANCZOS).save(OUT / f"{name}.png")


def star(d, cx, cy, r, fill, inner=0.32, n=4, turn=0.0):
    p = []
    for k in range(2 * n):
        a = turn + math.pi * k / n - math.pi / 2
        rr = r if k % 2 == 0 else r * inner
        p.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts(p), fill=fill)


def ship_shape(d, cx, cy, s=1.0):
    """A long-saucered explorer seen from above, nose up, two nacelles swept back."""
    for side in (-1, 1):   # pylons and nacelles
        d.polygon(pts([(cx + side * 40 * s, cy + 40 * s), (cx + side * 120 * s, cy + 90 * s),
                       (cx + side * 128 * s, cy + 104 * s), (cx + side * 44 * s, cy + 70 * s)]), fill=HULL_LO, outline=INK, width=3 * S)
        nx = cx + side * 124 * s
        d.rounded_rectangle(box((nx - 16 * s, cy + 30 * s, nx + 16 * s, cy + 190 * s)), radius=int(14 * s * S) // S * S,
                            fill=HULL, outline=INK, width=3 * S)
        d.rounded_rectangle(box((nx - 7 * s, cy + 50 * s, nx + 7 * s, cy + 175 * s)), radius=6 * S, fill=GLOW)
    d.polygon(pts([(cx - 46 * s, cy + 10 * s), (cx + 46 * s, cy + 10 * s), (cx + 30 * s, cy + 170 * s),
                   (cx - 30 * s, cy + 170 * s)]), fill=HULL_LO, outline=INK, width=3 * S)   # the engineering hull
    d.ellipse(box((cx - 96 * s, cy - 160 * s, cx + 96 * s, cy + 60 * s)), fill=HULL, outline=INK, width=4 * S)   # the saucer
    d.ellipse(box((cx - 60 * s, cy - 120 * s, cx + 60 * s, cy + 20 * s)), fill=HULL_HI)
    d.ellipse(box((cx - 22 * s, cy - 70 * s, cx + 22 * s, cy - 26 * s)), fill=HULL, outline=HULL_LO, width=3 * S)   # the bridge
    d.ellipse(box((cx - 10 * s, cy + 150 * s, cx + 10 * s, cy + 170 * s)), fill=(255, 140, 80))   # the deflector


def ship():
    im = glow(canvas(), (150, 100, 362, 440), (110, 190, 255, 70), 30)
    ship_shape(ImageDraw.Draw(im), 256, 220, 1.1)
    finish(im, "x_ship")


def planet_disc(im, cx, cy, r, base, lo, bands=()):
    d = ImageDraw.Draw(im)
    d.ellipse(box((cx - r, cy - r, cx + r, cy + r)), fill=base, outline=INK, width=4 * S)
    for y, h, c in bands:   # stripes, clipped to the disc by redrawing the edge after
        d.chord(box((cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4)), 0, 360, fill=None)
        d.ellipse(box((cx - r * 0.95, cy + y - h, cx + r * 0.95, cy + y + h)), fill=c)
    shade = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(shade).ellipse(box((cx - r * 0.55, cy - r * 0.75, cx + r * 1.5, cy + r * 1.2)), fill=lo + (150,))
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).ellipse(box((cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3)), fill=255)
    shade.putalpha(Image.composite(shade.getchannel("A"), Image.new("L", im.size, 0), mask))
    im.alpha_composite(shade)
    ImageDraw.Draw(im).ellipse(box((cx - r, cy - r, cx + r, cy + r)), outline=INK, width=4 * S)


def planet():
    im = glow(canvas(), (60, 60, 452, 452), (130, 120, 220, 70), 24)
    planet_disc(im, 256, 256, 170, (92, 84, 140), (30, 26, 60), bands=[(-50, 14, (110, 100, 160)), (30, 22, (78, 70, 124))])
    d = ImageDraw.Draw(im)
    d.arc(box((196, 150, 316, 270)), 190, 400, fill=(220, 216, 255), width=22 * S)   # a question mark, drawn
    d.line(pts([(282, 256), (256, 290), (256, 318)]), fill=(220, 216, 255), width=22 * S, joint="curve")
    d.ellipse(box((242, 340, 270, 368)), fill=(220, 216, 255))
    finish(im, "x_planet")


def credits():
    im = glow(canvas(), (90, 160, 422, 420), (255, 210, 90, 70), 26)
    d = ImageDraw.Draw(im)
    for i, (x, y) in enumerate([(140, 330), (260, 330), (200, 260), (200, 190)]):   # a stack of bars
        d.polygon(pts([(x, y), (x + 120, y), (x + 100, y + 60), (x - 20, y + 60)]), fill=GOLD, outline=INK, width=4 * S)
        d.polygon(pts([(x + 10, y + 8), (x + 110, y + 8), (x + 100, y + 22), (x, y + 22)]), fill=GOLD_HI)
    finish(im, "x_credits")


def mult():
    im = glow(canvas(), (80, 80, 432, 432), (110, 190, 255, 80), 26)
    d = ImageDraw.Draw(im)
    hexa = [(256 + 170 * math.cos(math.pi / 3 * k + math.pi / 6), 256 + 170 * math.sin(math.pi / 3 * k + math.pi / 6)) for k in range(6)]
    d.polygon(pts(hexa), fill=(26, 48, 96), outline=GLOW, width=8 * S)
    for a in (45, -45):   # the times sign
        r = math.radians(a)
        dx, dy = 90 * math.cos(r), 90 * math.sin(r)
        d.line(pts([(256 - dx, 256 - dy), (256 + dx, 256 + dy)]), fill=(240, 248, 255), width=34 * S)
    finish(im, "x_mult")


def scanner():
    im = canvas()
    d = ImageDraw.Draw(im)
    d.ellipse(box((66, 66, 446, 446)), fill=(10, 40, 34), outline=GREEN, width=6 * S)
    for r in (130, 80, 30):
        d.ellipse(box((256 - r, 256 - r, 256 + r, 256 + r)), outline=(60, 160, 90), width=3 * S)
    d.line(pts([(66, 256), (446, 256)]), fill=(60, 160, 90), width=2 * S)
    d.line(pts([(256, 66), (256, 446)]), fill=(60, 160, 90), width=2 * S)
    d.pieslice(box((76, 76, 436, 436)), 280, 340, fill=(90, 230, 120, 130))   # the sweep
    for x, y in ((330, 150), (170, 320), (300, 340)):
        d.ellipse(box((x - 12, y - 12, x + 12, y + 12)), fill=(200, 255, 210))
    finish(im, "x_scanner")


def shuttle():
    im = glow(canvas(), (110, 120, 402, 400), (110, 190, 255, 60), 26)
    d = ImageDraw.Draw(im)
    for side in (-1, 1):
        x = 256 + side * 112
        d.rounded_rectangle(box((x - 22, 230, x + 22, 390)), radius=14 * S, fill=HULL, outline=INK, width=3 * S)
        d.rounded_rectangle(box((x - 9, 250, x + 9, 375)), radius=6 * S, fill=GLOW)
        d.polygon(pts([(256 + side * 50, 250), (x - side * 20, 280), (x - side * 20, 320), (256 + side * 50, 320)]), fill=HULL_LO, outline=INK, width=3 * S)
    d.polygon(pts([(256, 110), (330, 250), (318, 380), (194, 380), (182, 250)]), fill=HULL, outline=INK, width=4 * S)   # the wedge
    d.polygon(pts([(256, 150), (296, 236), (216, 236)]), fill=(40, 70, 120))   # the window
    finish(im, "x_shuttle")


def shields():
    im = canvas()
    d = ImageDraw.Draw(im)
    d.ellipse(box((50, 70, 462, 482)), fill=(110, 190, 255, 60), outline=GLOW, width=8 * S)
    for row in range(-3, 4):   # a hex mesh across the bubble
        for col in range(-3, 4):
            cx, cy = 256 + col * 70 + (35 if row % 2 else 0), 276 + row * 60
            if (cx - 256) ** 2 + (cy - 276) ** 2 > 180 ** 2:
                continue
            hexa = [(cx + 32 * math.cos(math.pi / 3 * k), cy + 32 * math.sin(math.pi / 3 * k)) for k in range(6)]
            d.polygon(pts(hexa), outline=(170, 220, 255, 200), width=3 * S)
    ship_shape(d, 256, 250, 0.55)
    finish(im, "x_shields")


def artefact():
    im = glow(canvas(), (120, 80, 392, 440), (200, 150, 255, 90), 30)
    d = ImageDraw.Draw(im)
    d.polygon(pts([(256, 70), (330, 200), (300, 430), (212, 430), (182, 200)]), fill=VIOLET, outline=INK, width=4 * S)   # a crystal
    d.polygon(pts([(256, 70), (330, 200), (256, 250), (182, 200)]), fill=(200, 170, 255))
    d.line(pts([(256, 250), (256, 430)]), fill=VIOLET_LO, width=4 * S)
    for k in range(4):   # glyphs in its face
        y = 290 + k * 32
        d.line(pts([(236, y), (276, y)]), fill=GOLD_HI, width=6 * S)
    d.rounded_rectangle(box((150, 410, 362, 456)), radius=10 * S, fill=GOLD_LO, outline=INK, width=4 * S)   # its plinth
    finish(im, "x_artefact")


def wormhole():
    im = glow(canvas(), (40, 120, 472, 392), (130, 120, 255, 90), 30)
    d = ImageDraw.Draw(im)
    for k in range(9):   # rings narrowing to a bright throat
        t = k / 8
        rx, ry = 210 * (1 - t) + 20, 110 * (1 - t) + 10
        c = (int(80 + 170 * t), int(70 + 180 * t), 255)
        d.ellipse(box((256 - rx, 256 - ry, 256 + rx, 256 + ry)), outline=c, width=(10 - k) * S)
    d.ellipse(box((236, 246, 276, 266)), fill=(255, 255, 255))
    finish(im, "x_wormhole")


def spins():
    im = glow(canvas(), (90, 90, 422, 422), (255, 220, 120, 80), 30)
    d = ImageDraw.Draw(im)
    star(d, 220, 230, 150, GOLD, turn=0.0)
    star(d, 340, 330, 90, GOLD_HI, turn=0.4)
    star(d, 150, 370, 60, (255, 250, 220), turn=0.2)
    finish(im, "x_spins")


def hazard():
    im = glow(canvas(), (80, 80, 432, 432), (90, 230, 120, 70), 30)
    d = ImageDraw.Draw(im)
    front = [(130, 190), (330, 190), (330, 400), (130, 400)]
    top = [(130, 190), (200, 120), (400, 120), (330, 190)]
    side = [(330, 190), (400, 120), (400, 330), (330, 400)]
    for face, fill in ((front, (40, 46, 50)), (top, (60, 66, 70)), (side, (26, 30, 34))):
        d.polygon(pts(face), fill=fill, outline=INK, width=4 * S)
    for k in range(1, 5):   # its green grid
        x, y = 130 + 40 * k, 190 + 42 * k
        d.line(pts([(x, 190), (x, 400)]), fill=GREEN, width=2 * S)
        d.line(pts([(130, y), (330, y)]), fill=GREEN, width=2 * S)
    d.polygon(pts([(256, 230), (296, 300), (216, 300)]), outline=RED, width=8 * S)   # a warning mark
    finish(im, "x_hazard")


def final():
    im = glow(canvas(), (60, 60, 452, 452), (110, 190, 255, 100), 34)
    d = ImageDraw.Draw(im)
    d.ellipse(box((86, 86, 426, 426)), outline=HULL, width=34 * S)   # the gateway ring
    for k in range(8):   # its emitters
        a = math.pi / 4 * k
        x, y = 256 + 170 * math.cos(a), 256 + 170 * math.sin(a)
        d.rounded_rectangle(box((x - 18, y - 18, x + 18, y + 18)), radius=6 * S, fill=HULL_LO, outline=INK, width=3 * S)
        d.ellipse(box((x - 7, y - 7, x + 7, y + 7)), fill=GLOW)
    for r, c in ((130, (60, 120, 220)), (90, (110, 180, 255)), (48, (200, 235, 255)), (18, (255, 255, 255))):
        d.ellipse(box((256 - r, 256 - r, 256 + r, 256 + r)), fill=c)
    finish(im, "x_final")


if __name__ == "__main__":
    ship()
    planet()
    credits()
    mult()
    scanner()
    shuttle()
    shields()
    artefact()
    wormhole()
    spins()
    hazard()
    final()
