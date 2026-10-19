"""Cut FLUX candidates out of their magenta backgrounds and normalise them to 512x512 with the
same drop shadow as the SVG set. usage: process_flux.py <in_dir> <out_dir> [names...]"""
import colorsys, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageChops

def is_bg(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return (h > 0.74 or h < 0.02) and s > 0.28 and v > 0.18 and r > g + 30 and b > g + 10

def cutout(src: Path) -> Image.Image:
    im = Image.open(src).convert("RGB")
    w, h = im.size
    px = im.load()
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            if is_bg(*px[x, y]):
                mp[x, y] = 255
    # Background = the bg-coloured region connected to the border.
    for x in range(w):
        for y in (0, h - 1):
            if mp[x, y] == 255: ImageDraw.floodfill(mask, (x, y), 128)
    for y in range(h):
        for x in (0, w - 1):
            if mp[x, y] == 255: ImageDraw.floodfill(mask, (x, y), 128)
    alpha = mask.point(lambda v: 0 if v == 128 else 255)
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    # Pull the magenta tint out of the fringe.
    rgba = im.convert("RGBA")
    rp = rgba.load(); ap = alpha.load()
    for y in range(h):
        for x in range(w):
            a = ap[x, y]
            r, g, b, _ = rp[x, y]
            if 0 < a < 250 and r > g and b > g:
                m = min(r, b)
                rp[x, y] = (r - (m - g) // 2, g, b - (m - g) // 2, a)
            else:
                rp[x, y] = (r, g, b, a)
    return rgba

def normalise(im: Image.Image, size=512, fill=0.86) -> Image.Image:
    bbox = im.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    im = im.crop(bbox)
    scale = fill * size / max(im.size)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x, y = (size - im.width) // 2, (size - im.height) // 2 - 6
    shadow = Image.new("RGBA", (size, size), (22, 8, 2, 0))
    sa = Image.new("L", (size, size), 0)
    sa.paste(im.getchannel("A"), (x, y + 14))
    sa = sa.filter(ImageFilter.GaussianBlur(12)).point(lambda v: int(v * 0.55))
    shadow.putalpha(sa)
    out = Image.alpha_composite(out, shadow)
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0)); layer.paste(im, (x, y))
    return Image.alpha_composite(out, layer)

if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2]); dst.mkdir(parents=True, exist_ok=True)
    names = sys.argv[3:] or sorted(p.stem for p in src.glob("*.png"))
    for n in names:
        p = src / f"{n}.png"
        if n.startswith("bg"):
            Image.open(p).convert("RGB").resize((1280, 720), Image.LANCZOS).save(dst / f"{n}.jpg", quality=86)
        elif n.startswith("logo"):
            normalise(cutout(p), size=1024, fill=0.96).resize((800, 800), Image.LANCZOS).save(dst / f"{n}.png", optimize=True)
        else:
            normalise(cutout(p)).save(dst / f"{n}.png", optimize=True)
        print(n, flush=True)
