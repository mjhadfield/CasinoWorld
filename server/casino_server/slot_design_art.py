"""
The image side of the Slot design board (slot_design.py): asking the image model for art and turning what
comes back into 512x512 symbols.

The image model is whichever diffusers model Mike has started from Odysseus's Cookbook (FLUX.2-klein,
Qwen-Image-2.1, ...): it runs in Odysseus's diffusion server, inside its Docker container, behind an
OpenAI-style /v1/images API, so nothing here depends on which one. Edits need a model that takes a reference
image; one that can't says so and the board shows it. (The code still says "flux" for the model, from when
FLUX was the only one.) Reference edits run at 512²: with FLUX.2-klein, larger references ran the 12 GB card
out of memory, because CPU offload keeps the ~8 GB text encoder on the GPU while the VAE encodes the
reference. Text-only generations (a New symbol with no reference) run at 1024².

Every picture is asked for on a flat magenta background (green for purple symbols) and keyed out here.
Objects get the set's drop shadow; characters are drawn as a bust only and put into the board's shared
portrait frame (compose_character), so every character matches.
"""
import base64
import io
import json
import os
import subprocess

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

CONTAINER = os.environ.get("CASINO_FLUX_CONTAINER", "odysseus-odysseus-1")
FLUX_URL = "localhost:8000"
S = 512


class FluxError(RuntimeError):
    """The image model isn't reachable or refused the request (shown on the board as-is)."""


# ------------------------------------------------------------------ prompts
STYLES = {
    1: "Redraw this exact slot machine symbol, keeping its design, colours, shape and pose, in crisp high-detail glossy casino slot game art.",
    2: "Re-render this slot machine symbol as a premium glossy 3D casino slot icon: same subject, same colours, polished chrome and gold trim, strong rim lighting, rich fine detail.",
    3: "A bold new take on this slot machine symbol: same subject and colour scheme, but a punchy cartoon style with a thick dark outline, bright saturated colours and simple strong shading.",
}
TEXT_STYLES = {
    1: "crisp high-detail glossy casino slot game art",
    2: "premium glossy 3D casino slot icon, rich fine detail",
    3: "punchy cartoon style, thick dark outline, bright saturated colours, simple strong shading",
}
BUST = ("a slot machine character portrait in a bold painted style like premium mobile casino slot art: a thick "
        "dark ink outline around the figure, smooth soft painted shading, glossy highlights, no cross-hatching. "
        "Head and shoulders, facing the viewer, the shoulders wide and cut off flat at the bottom edge of the "
        "image, the head in the upper half. Maintain the original facial features.")


def _bg(key: str) -> str:
    colour = "flat solid bright green" if key == "green" else "flat solid magenta"
    return f"Isolate it on a perfectly {colour} background"


def _keep(text: str | None) -> str:
    return f" Keep the {text} exactly as it is." if text else ""


def default_prompts() -> dict:
    """The style prompts a design starts with; its Art step can rewrite them (Design.prompts)."""
    return {"redraw": [STYLES[n] for n in (1, 2, 3)], "text": [TEXT_STYLES[n] for n in (1, 2, 3)], "bust": BUST}


def object_prompt(style: str, key: str, keep_text: str | None = None, note: str = "") -> str:
    """Redraw a reference in a style (by default 1 faithful, 2 premium, 3 bold)."""
    extra = f" {note.rstrip('.')}." if note else ""
    return (f"{style.strip()}{_keep(keep_text)}{extra} Centred, filling most of the frame. {_bg(key)}: "
            "remove the coloured frame, the starfield, the outer glow and the dark background. No extra text, no border.")


def object_text_prompt(style: str, key: str, description: str) -> str:
    return (f"a single slot machine symbol: {description}, {style.strip().rstrip('.,')}, centred and filling most "
            f"of the frame. {_bg(key)}. No border.")


def bust_prompt(key: str, note: str = "", bust: str = BUST) -> str:
    extra = f" {note.rstrip('.')}." if note else ""
    return (f"Redraw this character as {bust.strip()} Same face, hair, expression and uniform.{extra} "
            f"Remove the frame, the border and the whole background. {_bg(key)}. No text.")


def bust_text_prompt(key: str, description: str, bust: str = BUST) -> str:
    return f"{description}, drawn as {bust.strip()} {_bg(key)}. No frame, no text."


def variation_prompt(kind: str, key: str, note: str = "", bust: str = BUST) -> str:
    """Another take on an image already on the board (Reiterate)."""
    change = f" Change: {note.rstrip('.')}." if note else ""
    if kind == "character":
        return (f"Make a fresh variation of this character portrait, drawn as {bust.strip()}{change} "
                f"{_bg(key)}. No frame, no background, no text.")
    return (f"Make a fresh variation of this slot machine symbol: same subject, same style and colours, crisp "
            f"high-detail glossy casino slot game art.{change} Centred, filling most of the frame. {_bg(key)}. "
            "No extra text, no border.")


def refine_prompt(kind: str, key: str, instruction: str) -> str:
    """A targeted edit of one image: everything stays except what the instruction names."""
    what = "character portrait" if kind == "character" else "slot machine symbol"
    return (f"Keep this {what} exactly as it is: the same subject, pose, style, colours and composition. Change only "
            f"this: {instruction.strip().rstrip('.')}. {_bg(key)}, as it is now. No text, no border.")


def background_prompt(description: str) -> str:
    return (f"A wide painterly slot machine game background: {description.strip().rstrip('.')}. Cinematic lighting, "
            "rich colour, darker and calmer in the middle where the reels sit. No text, no slot machine, no reels, "
            "no people in the foreground.")


def themed(prompt: str, theme: str = "") -> str:
    """Lead with the design's theme brief (Concept), so every picture belongs to the same slot."""
    return f"Theme: {theme.strip().rstrip('.')}. {prompt}" if theme and theme.strip() else prompt


# ------------------------------------------------------------------ FLUX
def _docker(args: list[str], data: bytes | None = None, timeout: float = 900) -> bytes:
    cmd = ["docker", "exec", "-i", "-u", "odysseus", "-e", "HOME=/app", CONTAINER, "curl", "-s", *args]
    try:
        r = subprocess.run(cmd, input=data, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise FluxError(f"Couldn't reach Odysseus: {e}")
    if r.returncode != 0:
        raise FluxError((r.stderr.decode(errors="replace").strip() or "docker exec failed")[-300:])
    return r.stdout


def image_model() -> str | None:
    """The image model loaded in Odysseus right now (its id, e.g. "Qwen-Image-2.1"), or None."""
    try:
        out = _docker(["-m", "4", f"{FLUX_URL}/v1/models"], timeout=10)
        return next((m["id"] for m in json.loads(out).get("data", []) if m.get("id")), None)
    except (FluxError, ValueError, AttributeError, TypeError, KeyError):
        return None


def flux_ready() -> bool:
    """Is an image model loaded in Odysseus right now?"""
    return image_model() is not None


def _image(out: bytes) -> Image.Image:
    try:
        d = json.loads(out)
    except ValueError:
        raise FluxError("The image model failed (most likely out of GPU memory; see the Odysseus diffusion log)")
    if "data" not in d:
        raise FluxError(f"The image model said: {str(d)[:300]}")
    return Image.open(io.BytesIO(base64.b64decode(d["data"][0]["b64_json"]))).convert("RGB")


def flux_edit(ref: Image.Image, prompt: str) -> Image.Image:
    """Redraw a reference image (512²)."""
    buf = io.BytesIO()
    fit_square(ref.convert("RGB"), 1024).save(buf, "PNG")
    return _image(_docker(["-X", "POST", f"{FLUX_URL}/v1/images/edits",
                           "-F", "image=@-;type=image/png;filename=ref.png", "--form-string", f"prompt={prompt}",
                           "--form-string", "size=512x512", "--form-string", "quality=high"], buf.getvalue()))


def flux_generate(prompt: str, size: str = "1024x1024") -> Image.Image:
    """Draw from a prompt alone (1024², or a background's 1344×768)."""
    body = json.dumps({"prompt": prompt, "size": size, "quality": "high"}).encode()
    return _image(_docker(["-X", "POST", f"{FLUX_URL}/v1/images/generations",
                           "-H", "Content-Type: application/json", "--data-binary", "@-"], body))


def fit_square(im: Image.Image, size: int, fill=(8, 12, 28)) -> Image.Image:
    """Pad to a square (so FLUX doesn't crop the reference) and scale to size."""
    side = max(im.size)
    sq = Image.new("RGB", (side, side), fill)
    sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im if im.mode == "RGBA" else None)
    return sq.resize((size, size), Image.LANCZOS)


def fit_cover(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Scale and centre-crop to fill `size` exactly (a background)."""
    k = max(size[0] / im.width, size[1] / im.height)
    im = im.resize((max(size[0], round(im.width * k)), max(size[1], round(im.height * k))), Image.LANCZOS)
    x, y = (im.width - size[0]) // 2, (im.height - size[1]) // 2
    return im.crop((x, y, x + size[0], y + size[1]))


def is_colour(v) -> bool:
    return isinstance(v, str) and len(v) == 7 and v[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in v[1:])


def render_logo(lines: list[str], font_path, top: str, bottom: str, outline: str, emblem: Image.Image | None = None) -> Image.Image:
    """The logo's lettering: each line fitted to the width (the first biggest), filled with a top-to-bottom
    gradient, outlined and shadowed, with an optional emblem to the left; trimmed to fit the screen's logo box."""
    from PIL import ImageDraw, ImageFont
    W, H = 1200, 420
    tx, tw = (0, W) if emblem is None else (int(H * 0.95), W - int(H * 0.95))
    weights = [1.25] + [1.0] * (len(lines) - 1)
    heights = [H * w / sum(weights) for w in weights]
    mask = Image.new("L", (W, H), 0)
    stroke = Image.new("L", (W, H), 0)
    y = 0.0
    for line, lh in zip(lines, heights):
        size = int(lh * 0.86)
        while size > 10:
            font = ImageFont.truetype(str(font_path), size)
            box = font.getbbox(line, stroke_width=max(2, size // 14))
            if box[2] - box[0] <= tw - 16 and box[3] - box[1] <= lh:
                break
            size -= 4
        sw = max(2, size // 14)
        x = tx + (tw - (box[2] - box[0])) / 2 - box[0]
        yy = y + (lh - (box[3] - box[1])) / 2 - box[1]
        ImageDraw.Draw(stroke).text((x, yy), line, font=font, fill=255, stroke_width=sw, stroke_fill=255)
        ImageDraw.Draw(mask).text((x, yy), line, font=font, fill=255)
        y += lh
    t, b = _rgb(top), _rgb(bottom)
    col = (t[None, :] * (1 - np.linspace(0, 1, H)[:, None]) + b[None, :] * np.linspace(0, 1, H)[:, None]).astype(np.uint8)
    grad = Image.fromarray(np.dstack([np.repeat(col[:, None, :], W, axis=1), np.full((H, W), 255, np.uint8)]), "RGBA")
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow.putalpha(stroke.filter(ImageFilter.GaussianBlur(8)).point(lambda v: int(v * 0.6)))
    out.alpha_composite(shadow, (0, 6))
    ring = Image.new("RGBA", (W, H), tuple(int(c) for c in _rgb(outline)) + (255,))
    ring.putalpha(stroke)
    out.alpha_composite(ring)
    grad.putalpha(mask)
    out.alpha_composite(grad)
    if emblem is not None:
        e = emblem.copy()
        e.thumbnail((int(H * 0.95), int(H * 0.95)), Image.LANCZOS)
        out.alpha_composite(e, ((tx - e.width) // 2, (H - e.height) // 2))
    bbox = out.getchannel("A").getbbox()
    return out.crop(bbox) if bbox else out


# ------------------------------------------------------------------ keying
def cutout(im: Image.Image) -> Image.Image:
    """Key a FLUX picture off its flat magenta/green background (sampled from the border)."""
    rgb = np.asarray(im.convert("RGB"), dtype=np.float32)
    border = np.concatenate([rgb[:4].reshape(-1, 3), rgb[-4:].reshape(-1, 3),
                             rgb[:, :4].reshape(-1, 3), rgb[:, -4:].reshape(-1, 3)])
    key = np.median(border, axis=0)
    dist = np.linalg.norm(rgb - key, axis=2)
    alpha = np.clip((dist - 30) / 50, 0, 1)  # <30 from the key = background, >80 = solid (pink skin sits ~140 away)
    # FLUX paints soft shadows onto the background: darker key colour, far from the key by distance.
    # Key those by how much a pixel leans towards the key hue instead (magenta: R,B over G; green: G over R,B).
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    green = key[1] > max(key[0], key[2])
    lean = g - np.maximum(r, b) if green else np.minimum(r, b) - g
    alpha = np.minimum(alpha, np.clip((110 - lean) / 70, 0, 1))  # lean >110 = background, <40 = solid
    m = 4  # FLUX sometimes leaves a thin off-colour strip along the frame edge
    alpha[:m] = 0; alpha[-m:] = 0; alpha[:, :m] = 0; alpha[:, -m:] = 0
    # Unmix the key colour out of semi-transparent edge pixels (C = aF + (1-a)K), then take off leftover spill.
    a = alpha[..., None]
    fg = np.where(a > 0.02, (rgb - (1 - a) * key) / np.maximum(a, 0.02), rgb)
    edge = alpha < 0.98
    if green:
        fg[..., 1] -= np.where(edge, np.maximum(0, fg[..., 1] - np.maximum(fg[..., 0], fg[..., 2]) - 20), 0)
    else:
        spill = np.where(edge, np.maximum(0, np.minimum(fg[..., 0], fg[..., 2]) - fg[..., 1] - 20), 0)
        fg[..., 0] -= spill; fg[..., 2] -= spill
    return Image.fromarray(np.dstack([np.clip(fg, 0, 255), alpha * 255]).astype(np.uint8), "RGBA")


def _shadow(im: Image.Image, dy: int) -> Image.Image:
    shadow = Image.new("RGBA", im.size, (22, 8, 2, 0))
    sa = Image.new("L", im.size, 0)
    sa.paste(im.getchannel("A"), (0, dy))
    shadow.putalpha(sa.filter(ImageFilter.GaussianBlur(12)).point(lambda v: int(v * 0.55)))
    return Image.alpha_composite(shadow, im)


FIT = {"scale": 1.0, "dx": 0.0, "dy": 0.0, "rot": 0.0}


def fit_values(fit: dict | None) -> dict:
    """A Fit (Art step): scale 0.5-1.6, nudge ±160 px, rotate ±45°; anything else is clamped."""
    f = {**FIT, **{k: float(v) for k, v in (fit or {}).items() if k in FIT}}
    f["scale"] = min(1.6, max(0.5, f["scale"]))
    f["dx"], f["dy"] = (min(160.0, max(-160.0, f[k])) for k in ("dx", "dy"))
    f["rot"] = min(45.0, max(-45.0, f["rot"]))
    return f


def symbol(im: Image.Image, fit: dict | None = None) -> Image.Image:
    """A keyed object, trimmed, fitted to 86% of 512² and given the set's drop shadow. An RGBA picture is taken
    as already keyed (a tile with no raw FLUX picture behind it)."""
    f = fit_values(fit)
    im = im if im.mode == "RGBA" else cutout(im)
    bbox = im.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    if not bbox:
        raise FluxError("The image model returned an empty picture")
    im = im.crop(bbox)
    if f["rot"]:
        im = im.rotate(-f["rot"], resample=Image.BICUBIC, expand=True)
    scale = 0.86 * S / max(im.size) * f["scale"]
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    layer.paste(im, (round((S - im.width) / 2 + f["dx"]), round((S - im.height) / 2 - 6 + f["dy"])))
    return _shadow(layer, 14)


# ------------------------------------------------------------------ an art slot's hand tweaks
# The Bonus games and Features steps' Adjust panel: size, a nudge (% of the picture), rotation, mirror and flip,
# brightness and colour. Applied in the order a CSS transform "translate rotate scale" draws it, so the page's
# live preview matches the baked picture.
ADJUST = {"scale": 1.0, "dx": 0.0, "dy": 0.0, "rot": 0.0, "mirror": False, "flip": False, "bright": 1.0, "sat": 1.0}
ADJUST_LIMITS = {"scale": (0.3, 2.0), "dx": (-50.0, 50.0), "dy": (-50.0, 50.0), "rot": (-180.0, 180.0),
                 "bright": (0.4, 1.6), "sat": (0.0, 2.0)}


def adjust_values(a: dict | None) -> dict:
    """An art slot's adjustments, every key filled in and clamped."""
    a = a or {}
    out = dict(ADJUST)
    for k, (lo, hi) in ADJUST_LIMITS.items():
        if k in a:
            out[k] = round(min(hi, max(lo, float(a[k]))), 3)
    for k in ("mirror", "flip"):
        if k in a:
            out[k] = bool(a[k])
    return out


def adjust(im: Image.Image, a: dict) -> Image.Image:
    """The picture with its adjustments, on a transparent canvas the size of the original (what goes past the
    edge is cut off, as in its box in the game)."""
    a = adjust_values(a)
    im = im.convert("RGBA")
    w, h = im.size
    if a["mirror"]:
        im = ImageOps.mirror(im)
    if a["flip"]:
        im = ImageOps.flip(im)
    if a["bright"] != 1 or a["sat"] != 1:
        alpha = im.getchannel("A")
        rgb = ImageEnhance.Color(ImageEnhance.Brightness(im.convert("RGB")).enhance(a["bright"])).enhance(a["sat"])
        im = rgb.convert("RGBA")
        im.putalpha(alpha)
    if a["scale"] != 1:
        im = im.resize((max(1, round(w * a["scale"])), max(1, round(h * a["scale"]))), Image.LANCZOS)
    if a["rot"]:
        im = im.rotate(-a["rot"], resample=Image.BICUBIC, expand=True)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(im, (round((w - im.width) / 2 + a["dx"] * w / 100), round((h - im.height) / 2 + a["dy"] * h / 100)))
    return canvas


# ------------------------------------------------------------------ the character frame
# One frame for every character: the rounded metallic frame and radial glow of the Star Trek Kirk 1 /
# Worf 1 favourites, with the head breaking out over the top border.
OUT = (40, 92, 472, 492)  # outer frame rect
R_OUT, BORDER, POKE = 54, 17, 62
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


def _rgb(h): return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float32)


def _ramp(t, stops):
    t = np.clip(t, 0, 1)[..., None] * (len(stops) - 1)
    i = np.minimum(t.astype(int), len(stops) - 2)[..., 0]
    f = t - i[..., None]
    s = np.stack(stops)
    return s[i] * (1 - f) + s[i + 1] * f


def _rrect_sdf(box, r):
    """Signed distance to a rounded rect (negative inside), per pixel."""
    y, x = np.mgrid[0:S, 0:S].astype(np.float32) + 0.5
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    qx = np.abs(x - cx) - ((box[2] - box[0]) / 2 - r)
    qy = np.abs(y - cy) - ((box[3] - box[1]) / 2 - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def _background(hue):
    centre, edge = _rgb(HUES[hue][3]), _rgb(HUES[hue][4])
    y, x = np.mgrid[0:S, 0:S].astype(np.float32)
    cx, cy = (IN[0] + IN[2]) / 2, IN[1] + (IN[3] - IN[1]) * 0.42
    t = np.hypot(x - cx, (y - cy) * 1.1) / ((IN[2] - IN[0]) * 0.72)
    col = _ramp(t, [np.minimum(centre * 1.35 + 40, 255), centre, edge * 1.4, edge])
    rays = (0.5 + 0.5 * np.cos(np.arctan2(y - cy, x - cx) * 16)) ** 8 * np.clip(1 - t, 0, 1) * 0.35
    col = col + (np.minimum(centre * 1.4 + 60, 255) - col) * rays[..., None]
    rng = np.random.default_rng(7)  # the same sparkle on every tile
    for sx, sy, sr in zip(rng.uniform(IN[0], IN[2], 40), rng.uniform(IN[1], IN[3], 40), rng.uniform(0.6, 1.8, 40)):
        col = col + (255 - col) * (np.exp(-((x - sx) ** 2 + (y - sy) ** 2) / sr ** 2) * 0.8)[..., None]
    return col


def _frame(hue):
    """(border RGBA, inner-window alpha) for a frame colour."""
    dark, mid, light = (_rgb(c) for c in HUES[hue][:3])
    d = _rrect_sdf(OUT, R_OUT)
    u = -d / BORDER  # 0 at the outer edge, 1 at the inner edge
    y = np.mgrid[0:S, 0:S][0].astype(np.float32)
    # Bevel across the border: dark rim, bright ridge, darker lower face, dark inner lip; lit from above.
    prof = np.interp(u, [0, 0.1, 0.18, 0.38, 0.55, 0.8, 0.9, 1.0], [0.05, 0.15, 0.7, 1.0, 0.55, 0.42, 0.12, 0.05])
    col = _ramp(prof * (1.12 - 0.42 * (y - OUT[1]) / (OUT[3] - OUT[1])), [_rgb("#0b0604"), dark, mid, light])
    ring = np.clip(np.minimum(d + BORDER, -d) + 0.5, 0, 1)
    outline = np.clip(3.5 - np.abs(d - 1.5), 0, 1) * (d > 0)
    border = np.dstack([col * ring[..., None], np.maximum(ring, outline) * 255])
    border[..., :3] = np.where((outline > ring)[..., None], 8, border[..., :3])
    return border, np.clip(-(d + BORDER) + 0.5, 0, 1)


def _over(dst, src):
    sa, da = src[..., 3:] / 255, dst[..., 3:] / 255
    oa = sa + da * (1 - sa)
    return np.dstack([(src[..., :3] * sa + dst[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6), oa * 255])


def _place(bust: Image.Image, fit: dict) -> np.ndarray:
    """Scale the bust so the head pokes POKE px above the window and the shoulders run off the bottom; a Fit
    scales it about that and nudges it."""
    a = np.asarray(bust)[..., 3]
    ys, _ = np.nonzero(a > 24)
    if not len(ys):
        raise FluxError("The image model returned an empty picture")
    top, bottom = ys.min(), ys.max()
    hx = np.nonzero(a[top:top + (bottom - top) * 2 // 5] > 24)[1].mean()  # centre on the head
    scale = (IN[3] + 12 - (IN[1] - POKE)) / (bottom - top) * fit["scale"]
    im = bust.resize((round(bust.width * scale), round(bust.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    canvas.paste(im, (round(S / 2 - hx * scale + fit["dx"]), round(IN[1] - POKE - top * scale + fit["dy"])), im)
    return np.asarray(canvas).astype(np.float32)


def compose_character(raw: Image.Image, fit: dict | None = None, hues=None) -> dict[str, Image.Image]:
    """A FLUX bust in the shared frame, in every frame colour (or just `hues`)."""
    char = _place(cutout(raw), fit_values(fit))
    above = char.copy()
    above[..., 3] *= np.mgrid[0:S, 0:S][0] < IN[1] + 2
    out = {}
    for hue in hues or HUES:
        border, inner = _frame(hue)
        inside = char.copy()
        inside[..., 3] *= inner
        tile = _over(_over(_over(np.dstack([_background(hue), inner * 255]), inside), border), above)
        out[hue] = _shadow(Image.fromarray(np.clip(tile, 0, 255).astype(np.uint8), "RGBA"), 12)
    return out


if __name__ == "__main__":
    # python -m casino_server.slot_design_art rebuild <design>: redo every framed character from its raw bust
    # and its Fit (after changing the frame, or on a fresh checkout, where chars/ isn't kept).
    import sys
    from pathlib import Path
    if sys.argv[1:2] != ["rebuild"] or len(sys.argv) != 3:
        sys.exit("usage: python -m casino_server.slot_design_art rebuild <design>")
    root = Path(os.environ.get("CASINO_DESIGNS_DIR") or Path(__file__).resolve().parents[1] / "slot_designs") / sys.argv[2]
    (root / "chars").mkdir(exist_ok=True)
    fits = {vid: f["fit"] for s in json.loads((root / "design.json").read_text())["symbols"]
            for vid, f in s.get("fits", {}).items()}
    for p in sorted((root / "raw").glob("bust_*.png")):
        for hue, im in compose_character(Image.open(p).convert("RGB"), fits.get(f"bust/{p.stem[5:]}")).items():
            im.save(root / f"chars/{p.stem[5:]}_{hue}.png", optimize=True)
        print(p.stem, flush=True)
