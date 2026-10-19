"""Generate 3 FLUX.2-klein variants of each Star Trek symbol from its sheet crop (ref/<name>.png) into
raw/<name>_<n>.png, skipping existing. Edits run at 512² — larger references OOM the 12 GB card, because
CPU offload keeps the text encoder on the GPU while the VAE encodes the reference.
usage (from docs/slots/startrek): python ../tools/startrek_gen.py [names...]"""
import os, subprocess, sys
from pathlib import Path
TOOLS = Path(__file__).parent
GREEN = {"Q", "ds9"}  # purple symbols: key on green instead of magenta
KEEP = {"wild": "Keep the word WILD exactly as it is.", "scatter": "Keep the word SCATTER exactly as it is.",
        "A": "Keep the letter A.", "K": "Keep the letter K.", "Q": "Keep the letter Q.",
        "J": "Keep the letter J.", "10": "Keep the number 10."}
STYLES = {
    1: "Redraw this exact slot machine symbol, keeping its design, colours, shape and pose, in crisp high-detail glossy casino slot game art.",
    2: "Re-render this slot machine symbol as a premium glossy 3D casino slot icon: same subject, same colours, polished chrome and gold trim, strong rim lighting, rich fine detail.",
    3: "A bold new take on this slot machine symbol: same subject and colour scheme, but a punchy cartoon style with a thick dark outline, bright saturated colours and simple strong shading.",
}
def prompt(name, n):
    bg = "flat solid bright green" if name in GREEN else "flat solid magenta"
    return (f"{STYLES[n]} {KEEP.get(name, '')} Centred, filling most of the frame. Isolate it on a perfectly {bg} "
            "background: remove the starfield, the outer glow and the dark background. No extra text, no border.")
names = sys.argv[1:] or [p.stem for p in sorted(Path("ref").glob("*.png"))]
for name in names:
    for n in (1, 2, 3):
        out = f"raw/{name}_{n}.png"
        if os.path.exists(out):
            continue
        r = subprocess.run([sys.executable, "-I", str(TOOLS / "flux_edit.py"), f"ref/{name}.png", out, prompt(name, n), "512x512"],
                           capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip()[-300:], flush=True)
print("DONE", flush=True)
