"""Put Star Trek character busts into one shared portrait frame, so every character matches: the
rounded metallic frame and radial glow of the Kirk 1 / Worf 1 favourites, with the head breaking out
over the top border. Each bust is rendered in every frame colour, for the picker to choose from.
usage (from docs/slots/startrek): python ../tools/startrek_frame.py [names...]
  raw/bust_<name>_<n>.png → chars/<name>_<n>_<hue>.png (512², drop shadow as the rest of the set)"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
sys.path.insert(0, str(Path(__file__).parent))
from startrek_cut import cutout

S = 512
OUT = (40, 92, 472, 492)  # outer frame rect
R_OUT, BORDER = 54, 17
IN = (OUT[0] + BORDER, OUT[1] + BORDER, OUT[2] - BORDER, OUT[3] - BORDER)
# hue: (frame dark, frame mid, frame light, glow centre, glow edge)
HUES = {
    "gold":   ("#4a2c06", "#d39a26", "#fff3bd", "#ffd84a", "#7a3f02"),
    "red":    ("#4a0e06", "#d0562e", "#ffd0b0", "#e4402a", "#3a0505"),
    "blue":   ("#0a1f55", "#3a7be0", "#d6ecff", "#3d9bff", "#061033"),
    "purple": ("#2a0c4a", "#9550d8", "#f0dcff", "#a856f0", "#1c0636"),
    "silver": ("#2c3038", "#9aa4b2", "#ffffff", "#9fb4cc", "#151a24"),
    "green":  ("#0b3312", "#3fae4c", "#d8ffd0", "#3fdc5a", "#04220a"),
}
DEFAULT_HUE = {"kirk": "gold", "spock": "blue", "worf": "red", "picard": "red",
               "data": "gold", "troi": "purple", "obrien": "gold"}

def rgb(h): return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float32)

def ramp(t, stops):
    """Piecewise-linear colour ramp: t in [0,1] over evenly spaced stops."""
    t = np.clip(t, 0, 1)[..., None] * (len(stops) - 1)
    i = np.minimum(t.astype(int), len(stops) - 2)
    f = t - i
    s = np.stack(stops)
    return s[i[..., 0]] * (1 - f) + s[i[..., 0] + 1] * f

def rrect_sdf(box, r):
    """Signed distance to a rounded rect (negative inside), per pixel of the canvas."""
    y, x = np.mgrid[0:S, 0:S].astype(np.float32) + 0.5
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    hx, hy = (box[2] - box[0]) / 2 - r, (box[3] - box[1]) / 2 - r
    qx, qy = np.abs(x - cx) - hx, np.abs(y - cy) - hy
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r

def background(hue):
    dark, mid, light, centre, edge = map(rgb, HUES[hue])
    y, x = np.mgrid[0:S, 0:S].astype(np.float32)
    cx, cy = (IN[0] + IN[2]) / 2, IN[1] + (IN[3] - IN[1]) * 0.42
    t = np.hypot(x - cx, (y - cy) * 1.1) / ((IN[2] - IN[0]) * 0.72)
    col = ramp(t, [np.minimum(centre * 1.35 + 40, 255), centre, edge * 1.4, edge])
    rays = (0.5 + 0.5 * np.cos(np.arctan2(y - cy, x - cx) * 16)) ** 8 * np.clip(1 - t, 0, 1) * 0.35
    col = col + (np.minimum(centre * 1.4 + 60, 255) - col) * rays[..., None]
    rng = np.random.default_rng(7)  # same sparkle on every tile
    for sx, sy, sr in zip(rng.uniform(IN[0], IN[2], 40), rng.uniform(IN[1], IN[3], 40), rng.uniform(0.6, 1.8, 40)):
        star = np.exp(-((x - sx) ** 2 + (y - sy) ** 2) / (sr ** 2)) * 0.8
        col = col + (255 - col) * star[..., None]
    return col

def frame_layers(hue):
    """(border RGBA, inner-window alpha) for a frame colour."""
    dark, mid, light = rgb(HUES[hue][0]), rgb(HUES[hue][1]), rgb(HUES[hue][2])
    d = rrect_sdf(OUT, R_OUT)
    u = -d / BORDER  # 0 at the outer edge, 1 at the inner edge
    y = np.mgrid[0:S, 0:S][0].astype(np.float32)
    # Bevel across the border: dark rim, bright ridge, darker lower face, dark inner lip.
    prof = np.interp(u, [0, 0.1, 0.18, 0.38, 0.55, 0.8, 0.9, 1.0], [0.05, 0.15, 0.7, 1.0, 0.55, 0.42, 0.12, 0.05])
    light_dir = 1.12 - 0.42 * (y - OUT[1]) / (OUT[3] - OUT[1])
    col = ramp(prof * light_dir, [rgb("#0b0604"), dark, mid, light])
    ring = np.clip(np.minimum(d + BORDER, -d) + 0.5, 0, 1)  # antialiased ring
    outline = np.clip(3.5 - np.abs(d - 1.5), 0, 1) * (d > 0)  # thin black outline outside
    border = np.dstack([col * ring[..., None], np.maximum(ring, outline) * 255])
    border[..., :3] = np.where((outline > ring)[..., None], 8, border[..., :3])
    inner = np.clip(-(d + BORDER) + 0.5, 0, 1)
    return border.astype(np.float32), inner

def over(dst, src):
    """Alpha-composite float RGBA arrays (0-255)."""
    sa, da = src[..., 3:] / 255, dst[..., 3:] / 255
    oa = sa + da * (1 - sa)
    rgbo = (src[..., :3] * sa + dst[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6)
    return np.dstack([rgbo, oa * 255])

def place(bust: Image.Image) -> np.ndarray:
    """Scale the bust so the head pokes ~44px above the window and the shoulders run off the bottom."""
    a = np.asarray(bust)[..., 3]
    ys, xs = np.nonzero(a > 24)
    top, bottom = ys.min(), ys.max()
    head = a[top:top + (bottom - top) * 2 // 5] > 24  # centre on the head, not the whole bust
    hx = np.nonzero(head)[1].mean()
    scale = (IN[3] + 12 - (IN[1] - 62)) / (bottom - top)
    im = bust.resize((round(bust.width * scale), round(bust.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    canvas.paste(im, (round(S / 2 - hx * scale), round(IN[1] - 62 - top * scale)), im)
    return np.asarray(canvas).astype(np.float32)

def compose(bust: Image.Image, hue: str) -> Image.Image:
    border, inner = frame_layers(hue)
    char = place(bust)
    out = np.dstack([background(hue), inner * 255])
    inside = char.copy(); inside[..., 3] *= inner
    out = over(out, inside)
    out = over(out, border)
    # The head breaks out over the top border.
    top = char.copy(); top[..., 3] *= (np.mgrid[0:S, 0:S][0] < IN[1] + 2)
    out = over(out, top)
    im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")
    shadow = Image.new("RGBA", (S, S), (22, 8, 2, 0))
    sa = Image.new("L", (S, S), 0); sa.paste(im.getchannel("A"), (0, 12))
    shadow.putalpha(sa.filter(ImageFilter.GaussianBlur(12)).point(lambda v: int(v * 0.55)))
    return Image.alpha_composite(shadow, im)

if __name__ == "__main__":
    Path("chars").mkdir(exist_ok=True)
    names = sys.argv[1:]
    for p in sorted(Path("raw").glob("bust_*.png")):
        name = p.stem[5:].rsplit("_", 1)[0]
        if names and name not in names:
            continue
        bust = cutout(p)
        for hue in HUES:
            compose(bust, hue).save(f"chars/{p.stem[5:]}_{hue}.png", optimize=True)
        print(p.stem, flush=True)
