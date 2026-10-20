"""The island voyage's stand-in pictures (your ship, the five islands, the final island, the treasure chest, a relic,
a key and the four artefacts), drawn as plain vector shapes into server/slot_art/armadillo/flux2/, where the Slot
design wizard finds every art slot's stand-in. A slot replaces them on its Bonus games step.
Run: python3 voyage_standins.py"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parents[3] / "server" / "slot_art" / "armadillo" / "flux2"
S = 4   # drawn 4x, then shrunk to 512 for smooth edges
INK = (40, 24, 12)
GOLD, GOLD_HI, GOLD_LO = (240, 190, 70), (255, 236, 160), (150, 100, 30)
SAND, SAND_LO = (232, 205, 140), (196, 160, 96)
LEAF, LEAF_LO = (70, 150, 70), (40, 100, 50)
WOOD, WOOD_LO = (130, 82, 44), (90, 54, 28)
ROCK, ROCK_LO = (120, 116, 110), (78, 74, 70)
SEA = (60, 140, 190, 150)


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


def line(d, xy, fill=INK, w=4):
    d.line(pts(xy), fill=fill, width=w * S, joint="curve")


def island(d, cx=256, cy=330, rx=200, ry=70, sand=SAND):
    """A sandy island in a ring of shallow water."""
    d.ellipse(box((cx - rx - 26, cy - ry - 14, cx + rx + 26, cy + ry + 22)), fill=SEA)
    d.ellipse(box((cx - rx, cy - ry, cx + rx, cy + ry)), fill=sand, outline=SAND_LO, width=4 * S)
    d.ellipse(box((cx - rx + 30, cy - ry + 10, cx + rx - 50, cy + ry - 30)), fill=tuple(min(255, v + 12) for v in sand))


def palm(d, x, y, h=170, lean=30):
    top = (x + lean, y - h)
    for k in range(6):   # the trunk, in rings
        t0, t1 = k / 6, (k + 1) / 6
        a = (x + lean * t0 * t0, y - h * t0)
        b = (x + lean * t1 * t1, y - h * t1)
        line(d, [a, b], fill=WOOD if k % 2 else WOOD_LO, w=14 - k)
    for ang in (-160, -120, -60, -20, 20, 200):   # the fronds
        r = math.radians(ang)
        tip = (top[0] + 95 * math.cos(r), top[1] + 55 * math.sin(r) + 30)
        mid = (top[0] + 50 * math.cos(r), top[1] + 35 * math.sin(r) - 10)
        d.polygon(pts([top, mid, tip, (mid[0], mid[1] + 18)]), fill=LEAF, outline=LEAF_LO)
    d.ellipse(box((top[0] - 12, top[1] - 4, top[0] + 10, top[1] + 18)), fill=WOOD_LO)


def chest(d, cx, cy, w=150, open_=True, locks=0):
    h = w * 0.55
    x0, x1 = cx - w / 2, cx + w / 2
    if open_:   # the lid tipped back, gold heaped up
        d.polygon(pts([(x0 + 6, cy - h * 0.2), (x0 + 20, cy - h * 1.15), (x1 - 20, cy - h * 1.15), (x1 - 6, cy - h * 0.2)]),
                  fill=WOOD_LO, outline=INK, width=3 * S)
        d.ellipse(box((x0 + 4, cy - h * 0.6, x1 - 4, cy + h * 0.2)), fill=GOLD, outline=GOLD_LO, width=3 * S)
        for i in range(9):
            gx = x0 + 22 + (i * 37) % (w - 44)
            gy = cy - h * 0.38 + (i * 13) % 26 - 6
            d.ellipse(box((gx - 14, gy - 9, gx + 14, gy + 9)), fill=GOLD_HI, outline=GOLD_LO, width=2 * S)
    d.rounded_rectangle(box((x0, cy - h * 0.15, x1, cy + h * 0.7)), radius=8 * S, fill=WOOD, outline=INK, width=4 * S)
    for fx in (x0 + 16, x1 - 28):
        d.rectangle(box((fx, cy - h * 0.15, fx + 12, cy + h * 0.7)), fill=GOLD_LO)
    if not open_:
        d.rounded_rectangle(box((x0, cy - h * 0.75, x1, cy - h * 0.1)), radius=18 * S, fill=WOOD, outline=INK, width=4 * S)
    for k in range(locks):   # padlocks along the front
        lx = cx - (locks - 1) * 26 + k * 52
        ly = cy + h * 0.26
        d.arc(box((lx - 12, ly - 26, lx + 12, ly + 2)), 180, 360, fill=ROCK, width=5 * S)
        d.rounded_rectangle(box((lx - 16, ly - 12, lx + 16, ly + 18)), radius=4 * S, fill=GOLD, outline=INK, width=2 * S)
        d.ellipse(box((lx - 4, ly - 2, lx + 4, ly + 6)), fill=INK)


def ship():
    """A three-masted galleon side on, facing right, black flag up."""
    im = canvas()
    d = ImageDraw.Draw(im)
    d.ellipse(box((70, 380, 450, 430)), fill=SEA)
    for x, top, w in ((170, 110, 110), (260, 80, 130), (350, 130, 96)):   # the masts and sails
        line(d, [(x, 380), (x, top)], fill=WOOD_LO, w=8)
        for k, (sy, sh) in enumerate(((top + 20, 80), (top + 110, 90))):
            bulge = 18
            d.polygon(pts([(x - w / 2, sy), (x + w / 2, sy), (x + w / 2 - 6, sy + sh), (x - w / 2 + 6, sy + sh)]),
                      fill=(245, 238, 220), outline=(170, 160, 140), width=3 * S)
            d.arc(box((x - w / 2, sy + sh - bulge, x + w / 2, sy + sh + bulge)), 0, 180, fill=(170, 160, 140), width=3 * S)
    d.polygon(pts([(260, 80), (300, 92), (260, 104)]), fill=(20, 20, 20))   # the flag
    d.ellipse(box((272, 86, 284, 98)), fill=(235, 235, 235))
    d.polygon(pts([(60, 330), (450, 330), (420, 400), (110, 400)]), fill=WOOD, outline=INK, width=4 * S)   # the hull
    d.polygon(pts([(60, 330), (110, 300), (150, 300), (150, 330)]), fill=WOOD_LO, outline=INK, width=3 * S)   # the stern
    d.polygon(pts([(450, 330), (488, 300), (492, 312), (440, 352)]), fill=WOOD_LO, outline=INK, width=3 * S)   # the bowsprit
    d.line(pts([(80, 352), (440, 352)]), fill=GOLD, width=5 * S)
    for k in range(6):
        d.rectangle(box((130 + k * 48, 362, 146 + k * 48, 376)), fill=INK)
    finish(im, "v_ship")


def treasure():
    im = canvas()
    im = glow(im, (130, 200, 380, 360), (255, 220, 120, 150))
    d = ImageDraw.Draw(im)
    island(d)
    palm(d, 140, 330)
    chest(d, 300, 310, 160)
    finish(im, "v_treasure")


def wreck():
    im = canvas()
    d = ImageDraw.Draw(im)
    island(d, rx=180, sand=(222, 196, 140))
    for rx, ry in ((120, 320), (390, 330)):
        d.ellipse(box((rx - 40, ry - 30, rx + 40, ry + 24)), fill=ROCK, outline=ROCK_LO, width=3 * S)
    d.polygon(pts([(150, 340), (360, 300), (400, 250), (380, 340), (190, 380)]), fill=WOOD_LO, outline=INK, width=4 * S)   # the broken hull
    for k in range(5):
        x = 190 + k * 40
        line(d, [(x, 370 - k * 9), (x + 18, 300 - k * 8)], fill=WOOD, w=7)
    line(d, [(300, 300), (250, 130)], fill=WOOD_LO, w=9)   # the snapped mast and a rag of sail
    d.polygon(pts([(254, 150), (330, 170), (300, 230), (262, 200)]), fill=(225, 214, 190), outline=(160, 150, 130), width=3 * S)
    finish(im, "v_wreck")


def skull_shape(d, cx, cy, s, fill, eye):
    d.ellipse(box((cx - 90 * s, cy - 100 * s, cx + 90 * s, cy + 60 * s)), fill=fill, outline=INK, width=4 * S)
    d.rounded_rectangle(box((cx - 55 * s, cy + 20 * s, cx + 55 * s, cy + 95 * s)), radius=16 * S, fill=fill, outline=INK, width=4 * S)
    for ex in (-38, 38):
        d.ellipse(box((cx + (ex - 26) * s, cy - 40 * s, cx + (ex + 26) * s, cy + 14 * s)), fill=eye)
    d.polygon(pts([(cx, cy + 18 * s), (cx - 14 * s, cy + 44 * s), (cx + 14 * s, cy + 44 * s)]), fill=eye)
    for tx in (-36, -12, 12, 36):
        d.line(pts([(cx + tx * s, cy + 60 * s), (cx + tx * s, cy + 92 * s)]), fill=INK, width=3 * S)


def skull():
    im = canvas()
    im = glow(im, (150, 120, 360, 320), (120, 255, 140, 70))
    d = ImageDraw.Draw(im)
    island(d, sand=(150, 140, 120))
    d.polygon(pts([(90, 340), (150, 200), (360, 190), (430, 340)]), fill=ROCK_LO)
    skull_shape(d, 256, 230, 1.1, ROCK, (30, 60, 30))
    finish(im, "v_skull")


def port():
    im = canvas()
    d = ImageDraw.Draw(im)
    island(d, rx=210)
    d.rectangle(box((80, 320, 440, 345)), fill=WOOD)   # the quay
    for k in range(8):
        d.rectangle(box((88 + k * 46, 345, 96 + k * 46, 380)), fill=WOOD_LO)
    roofs = [(110, 250, 70, (190, 70, 50)), (190, 220, 80, (170, 90, 60)), (280, 240, 70, (200, 110, 60))]
    for x, top, w, roof in roofs:   # the town
        d.rectangle(box((x, top, x + w, 322)), fill=(236, 226, 205), outline=INK, width=3 * S)
        d.polygon(pts([(x - 10, top), (x + w / 2, top - 46), (x + w + 10, top)]), fill=roof, outline=INK, width=3 * S)
        d.rectangle(box((x + w / 2 - 10, 290, x + w / 2 + 10, 322)), fill=WOOD_LO)
        d.rectangle(box((x + 10, top + 16, x + 26, top + 32)), fill=(90, 150, 200))
    d.rectangle(box((360, 200, 420, 322)), fill=(170, 160, 150), outline=INK, width=3 * S)   # the fort's tower
    for k in range(3):
        d.rectangle(box((360 + k * 22, 186, 374 + k * 22, 202)), fill=(170, 160, 150), outline=INK, width=2 * S)
    line(d, [(390, 186), (390, 120)], fill=INK, w=4)
    d.polygon(pts([(392, 120), (440, 132), (392, 146)]), fill=(200, 40, 40))
    finish(im, "v_port")


def cove():
    im = canvas()
    im = glow(im, (180, 210, 330, 330), (255, 200, 90, 160), blur=10)
    d = ImageDraw.Draw(im)
    island(d, sand=(210, 190, 140))
    d.polygon(pts([(70, 345), (110, 160), (200, 100), (320, 100), (410, 170), (440, 345)]), fill=ROCK, outline=INK, width=4 * S)
    d.chord(box((180, 200, 330, 420)), 180, 360, fill=(30, 22, 18))   # the cave mouth
    d.rectangle(box((180, 309, 330, 345)), fill=(30, 22, 18))
    for gx, gy in ((220, 320), (250, 310), (282, 322), (236, 334), (268, 336)):
        d.ellipse(box((gx - 14, gy - 9, gx + 14, gy + 9)), fill=GOLD, outline=GOLD_LO, width=2 * S)
    lx, ly = 256, 250   # the padlock
    d.arc(box((lx - 26, ly - 56, lx + 26, ly + 4)), 180, 360, fill=(200, 200, 205), width=9 * S)
    d.rounded_rectangle(box((lx - 36, ly - 26, lx + 36, ly + 40)), radius=8 * S, fill=GOLD, outline=INK, width=4 * S)
    d.ellipse(box((lx - 8, ly - 4, lx + 8, ly + 12)), fill=INK)
    d.rectangle(box((lx - 3, ly + 8, lx + 3, ly + 26)), fill=INK)
    finish(im, "v_cove")


def final():
    """The final island: a dark peak with a skull-faced cave and gold light inside."""
    im = canvas()
    im = glow(im, (160, 200, 360, 380), (255, 210, 90, 170))
    d = ImageDraw.Draw(im)
    island(d, rx=220, ry=78, sand=(190, 170, 130))
    d.polygon(pts([(50, 350), (170, 120), (256, 50), (340, 110), (460, 350)]), fill=(80, 70, 66), outline=INK, width=4 * S)
    d.polygon(pts([(230, 70), (256, 50), (290, 76), (262, 90)]), fill=(150, 145, 140))
    skull_shape(d, 256, 250, 0.9, (110, 100, 94), (255, 200, 80))
    finish(im, "v_final")


def legendary_chest():
    im = canvas()
    im = glow(im, (90, 120, 420, 420), (255, 220, 120, 170))
    d = ImageDraw.Draw(im)
    chest(d, 256, 300, 340, locks=4)
    finish(im, "v_chest")


def relic():
    """A gold goblet set with a red stone."""
    im = canvas()
    im = glow(im, (140, 100, 370, 420), (255, 220, 120, 120))
    d = ImageDraw.Draw(im)
    d.chord(box((150, 90, 362, 330)), 0, 180, fill=GOLD, outline=GOLD_LO, width=5 * S)
    d.ellipse(box((150, 170, 362, 220)), fill=GOLD_HI, outline=GOLD_LO, width=4 * S)
    d.ellipse(box((170, 180, 342, 210)), fill=(120, 30, 40))
    d.rectangle(box((238, 300, 274, 380)), fill=GOLD, outline=GOLD_LO, width=4 * S)
    d.ellipse(box((176, 360, 336, 410)), fill=GOLD, outline=GOLD_LO, width=5 * S)
    d.ellipse(box((236, 236, 276, 276)), fill=(210, 40, 50), outline=INK, width=3 * S)
    finish(im, "v_relic")


def key():
    im = canvas()
    im = glow(im, (90, 160, 420, 360), (255, 220, 120, 100))
    d = ImageDraw.Draw(im)
    d.ellipse(box((80, 180, 230, 330)), fill=GOLD, outline=GOLD_LO, width=6 * S)   # the bow
    d.ellipse(box((120, 220, 190, 290)), fill=(0, 0, 0, 0), outline=GOLD_LO, width=6 * S)   # (a hole: drawing replaces)
    d.rounded_rectangle(box((220, 238, 440, 272)), radius=10 * S, fill=GOLD, outline=GOLD_LO, width=5 * S)   # the shaft
    for x, h in ((380, 60), (420, 44)):   # the bit
        d.rectangle(box((x - 16, 268, x + 10, 268 + h)), fill=GOLD, outline=GOLD_LO, width=4 * S)
    finish(im, "v_key")


def compass():
    im = canvas()
    d = ImageDraw.Draw(im)
    d.ellipse(box((86, 86, 426, 426)), fill=GOLD, outline=GOLD_LO, width=8 * S)
    d.ellipse(box((116, 116, 396, 396)), fill=(245, 236, 210), outline=GOLD_LO, width=4 * S)
    for k in range(16):
        a = k * math.pi / 8
        r0 = 120 if k % 4 else 100
        d.line(pts([(256 + r0 * math.cos(a), 256 + r0 * math.sin(a)), (256 + 136 * math.cos(a), 256 + 136 * math.sin(a))]), fill=INK, width=3 * S)
    d.polygon(pts([(256, 130), (280, 256), (256, 270), (232, 256)]), fill=(200, 40, 40), outline=INK, width=2 * S)
    d.polygon(pts([(256, 382), (280, 256), (256, 242), (232, 256)]), fill=(60, 60, 70), outline=INK, width=2 * S)
    d.ellipse(box((244, 244, 268, 268)), fill=GOLD_HI, outline=INK, width=2 * S)
    d.ellipse(box((236, 50, 276, 96)), outline=GOLD_LO, width=8 * S)   # the ring
    finish(im, "v_art1")


def medallion():
    im = canvas()
    im = glow(im, (90, 110, 420, 440), (255, 220, 120, 110))
    d = ImageDraw.Draw(im)
    d.line(pts([(150, 40), (256, 130), (362, 40)]), fill=(120, 90, 40), width=6 * S)   # the chain
    d.ellipse(box((110, 130, 402, 422)), fill=GOLD, outline=GOLD_LO, width=8 * S)
    d.ellipse(box((140, 160, 372, 392)), outline=GOLD_LO, width=4 * S)
    skull_shape(d, 256, 270, 0.62, GOLD_HI, GOLD_LO)
    for k in range(12):
        a = k * math.pi / 6
        d.ellipse(box((256 + 132 * math.cos(a) - 6, 276 + 132 * math.sin(a) - 6, 256 + 132 * math.cos(a) + 6, 276 + 132 * math.sin(a) + 6)), fill=GOLD_LO)
    finish(im, "v_art2")


def spyglass():
    im = canvas()
    d = ImageDraw.Draw(im)

    def tube(x0, y0, x1, y1, w, fill):
        a = math.atan2(y1 - y0, x1 - x0) + math.pi / 2
        dx, dy = math.cos(a) * w / 2, math.sin(a) * w / 2
        d.polygon(pts([(x0 + dx, y0 + dy), (x1 + dx, y1 + dy), (x1 - dx, y1 - dy), (x0 - dx, y0 - dy)]), fill=fill, outline=INK, width=3 * S)
    tube(80, 400, 200, 300, 60, WOOD)
    tube(190, 308, 330, 192, 76, GOLD)
    tube(320, 200, 440, 100, 96, WOOD_LO)
    tube(430, 108, 452, 90, 110, GOLD)
    for x, y, w in ((200, 300, 64), (330, 192, 82)):
        tube(x - 6, y + 5, x + 6, y - 5, w + 6, GOLD_HI)
    finish(im, "v_art3")


def cutlass():
    im = canvas()
    d = ImageDraw.Draw(im)
    d.polygon(pts([(150, 360), (200, 330), (400, 110), (440, 70), (430, 130), (230, 370), (186, 396)]), fill=(214, 220, 228), outline=INK, width=4 * S)
    d.line(pts([(200, 350), (420, 100)]), fill=(250, 252, 255), width=3 * S)
    d.arc(box((80, 300, 230, 470)), 120, 300, fill=GOLD, width=10 * S)   # the guard
    d.polygon(pts([(140, 340), (210, 410), (196, 424), (126, 354)]), fill=GOLD, outline=INK, width=3 * S)
    d.polygon(pts([(110, 400), (160, 380), (120, 440), (80, 470), (70, 450)]), fill=WOOD, outline=INK, width=3 * S)   # the grip
    d.ellipse(box((56, 450, 90, 484)), fill=GOLD, outline=INK, width=3 * S)
    finish(im, "v_art4")


if __name__ == "__main__":
    ship()
    treasure()
    wreck()
    skull()
    port()
    cove()
    final()
    legendary_chest()
    relic()
    key()
    compass()
    medallion()
    spyglass()
    cutlass()
