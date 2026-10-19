"""Key the Star Trek FLUX variants off their flat magenta/green backgrounds and normalise them to 512²
with the same drop shadow as the Armadillo set. Unlike process_flux.py, it keys every background-coloured
pixel (not just the region touching the border), so frames with background showing inside come out clean.
usage (from docs/slots/startrek): python ../tools/startrek_cut.py [names...]"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent))
from process_flux import normalise

def cutout(src: Path) -> Image.Image:
    rgb = np.asarray(Image.open(src).convert("RGB"), dtype=np.float32)
    border = np.concatenate([rgb[:4].reshape(-1, 3), rgb[-4:].reshape(-1, 3), rgb[:, :4].reshape(-1, 3), rgb[:, -4:].reshape(-1, 3)])
    key = np.median(border, axis=0)
    dist = np.linalg.norm(rgb - key, axis=2)
    alpha = np.clip((dist - 30) / 50, 0, 1)  # <30 from the key = background, >80 = solid (pink skin sits ~140 away)
    # FLUX paints soft shadows onto the background: darker key colour, far from the key by distance.
    # Key those by how much a pixel leans towards the key hue instead (magenta: R,B over G; green: G over R,B).
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    green = key[1] > max(key[0], key[2])
    lean = g - np.maximum(r, b) if green else np.minimum(r, b) - g
    alpha = np.minimum(alpha, np.clip((110 - lean) / 70, 0, 1))  # lean >110 = background, <40 = solid
    # FLUX sometimes leaves a thin off-colour strip along the frame edge.
    m = 4; alpha[:m] = 0; alpha[-m:] = 0; alpha[:, :m] = 0; alpha[:, -m:] = 0
    # Unmix the key colour out of semi-transparent edge pixels: C = aF + (1-a)K.
    a = alpha[..., None]
    fg = np.where(a > 0.02, (rgb - (1 - a) * key) / np.maximum(a, 0.02), rgb)
    # Then take leftover spill off edge pixels (only the part that leans towards the key hue).
    edge = alpha < 0.98
    fr, fgr, fb = fg[..., 0], fg[..., 1], fg[..., 2]
    if green:
        fg[..., 1] -= np.where(edge, np.maximum(0, fgr - np.maximum(fr, fb) - 20), 0)
    else:
        spill = np.where(edge, np.maximum(0, np.minimum(fr, fb) - fgr - 20), 0)
        fg[..., 0] -= spill; fg[..., 2] -= spill
    out = np.dstack([np.clip(fg, 0, 255), alpha * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")

if __name__ == "__main__":
    Path("cut").mkdir(exist_ok=True)
    names = sys.argv[1:]
    files = [p for p in sorted(Path("raw").glob("*.png")) if not names or p.stem.rsplit("_", 1)[0] in names]
    for p in files:
        normalise(cutout(p)).save(f"cut/{p.name}", optimize=True)
        print(p.stem, flush=True)
