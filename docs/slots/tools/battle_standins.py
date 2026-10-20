"""The wave battle's stand-in pictures (your ship, an enemy ship, the boss), drawn as plain vector shapes into
server/slot_art/armadillo/flux2/, where the Slot design wizard finds every art slot's stand-in. A slot replaces
them on its Bonus games step. Run: python3 battle_standins.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parents[3] / "server" / "slot_art" / "armadillo" / "flux2"
S = 4   # drawn 4x, then shrunk to 512 for smooth edges


def canvas():
    return Image.new("RGBA", (512 * S, 512 * S), (0, 0, 0, 0))


def pts(xy):
    return [(x * S, y * S) for x, y in xy]


def glow(im, box, colour):
    g = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([v * S for v in box], fill=colour)
    return Image.alpha_composite(im, g.filter(ImageFilter.GaussianBlur(10 * S)))


def finish(im, name):
    im.resize((512, 512), Image.LANCZOS).save(OUT / f"{name}.png")


def hero():
    """A saucer-and-nacelles starship side on, facing right."""
    im = canvas()
    im = glow(im, (40, 170, 250, 230), (90, 170, 255, 140))
    im = glow(im, (40, 290, 250, 350), (90, 170, 255, 140))
    d = ImageDraw.Draw(im)
    d.polygon(pts([(150, 260), (330, 240), (360, 280), (300, 300), (170, 300)]), fill=(150, 160, 175), outline=(60, 66, 80), width=3 * S)
    for y in (185, 305):   # nacelle pylons and nacelles
        d.polygon(pts([(200, 255 if y < 250 else 300), (230, y + 20), (250, y + 20), (240, 255 if y < 250 else 300)]), fill=(120, 128, 142))
        d.rounded_rectangle([v * S for v in (50, y, 250, y + 34)], radius=16 * S, fill=(176, 184, 198), outline=(60, 66, 80), width=3 * S)
        d.rounded_rectangle([v * S for v in (60, y + 22, 240, y + 30)], radius=4 * S, fill=(110, 190, 255))
        d.ellipse([v * S for v in (232, y + 4, 256, y + 30)], fill=(255, 90, 70))
    d.ellipse([v * S for v in (250, 200, 480, 270)], fill=(205, 212, 222), outline=(60, 66, 80), width=3 * S)   # the saucer
    d.ellipse([v * S for v in (330, 212, 400, 238)], fill=(225, 232, 240))
    d.line(pts([(260, 246), (470, 236)]), fill=(120, 128, 142), width=3 * S)
    finish(im, "b_hero")


def enemy(name="b_enemy", body=(70, 105, 70), wing=(96, 136, 84), trim=(180, 60, 40), scale=1.0):
    """A winged raider side on, facing left (the boss is a bigger, darker one with more guns)."""
    im = canvas()
    c = 256

    def p(xy):
        return pts([(c + (x - c) * scale, c + (y - c) * scale) for x, y in xy])
    d = ImageDraw.Draw(im)
    d.polygon(p([(250, 250), (430, 140), (460, 160), (330, 260)]), fill=wing, outline=(30, 40, 30), width=3 * S)    # upper wing
    d.polygon(p([(250, 270), (430, 380), (460, 360), (330, 262)]), fill=tuple(int(v * 0.8) for v in wing), outline=(30, 40, 30), width=3 * S)
    d.polygon(p([(60, 250), (120, 232), (300, 236), (390, 256), (300, 280), (120, 282)]), fill=body, outline=(30, 40, 30), width=3 * S)   # hull
    d.polygon(p([(40, 256), (90, 240), (120, 256), (90, 272)]), fill=tuple(min(255, v + 40) for v in body))   # the head
    d.ellipse(p([(70, 248), (86, 262)]), fill=(255, 200, 80))
    for wx, wy in ((440, 150), (440, 370)):   # wingtip cannons
        d.polygon(p([(wx, wy - 6), (wx - 90, wy - 4), (wx - 90, wy + 4), (wx, wy + 6)]), fill=trim)
    d.line(p([(130, 256), (360, 256)]), fill=trim, width=int(4 * S * scale))
    finish(im, name)


if __name__ == "__main__":
    hero()
    enemy()
    enemy("b_boss", body=(92, 44, 40), wing=(120, 58, 50), trim=(255, 120, 40), scale=1.12)
