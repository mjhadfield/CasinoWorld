"""Generate 3 FLUX.2-klein variants of each Star Trek symbol from its sheet crop (ref/<name>.png), skipping
existing: objects into raw/<name>_<n>.png (three styles), characters into raw/bust_<char>_<n>.png (one bust
style, three takes; startrek_frame.py puts them in the shared frame). Edits run at 512² — larger references OOM the 12 GB card, because
CPU offload keeps the text encoder on the GPU while the VAE encodes the reference.
usage (from docs/slots/startrek): python ../tools/startrek_gen.py [names...]"""
import os, subprocess, sys
from pathlib import Path
TOOLS = Path(__file__).parent
GREEN = {"Q", "ds9", "gas_giant", "troi"}  # purple symbols: key on green instead of magenta
KEEP = {"wild": "Keep the word WILD exactly as it is.", "scatter": "Keep the word SCATTER exactly as it is.",
        "A": "Keep the letter A.", "K": "Keep the letter K.", "Q": "Keep the letter Q.",
        "J": "Keep the letter J.", "10": "Keep the number 10."}
STYLES = {
    1: "Redraw this exact slot machine symbol, keeping its design, colours, shape and pose, in crisp high-detail glossy casino slot game art.",
    2: "Re-render this slot machine symbol as a premium glossy 3D casino slot icon: same subject, same colours, polished chrome and gold trim, strong rim lighting, rich fine detail.",
    3: "A bold new take on this slot machine symbol: same subject and colour scheme, but a punchy cartoon style with a thick dark outline, bright saturated colours and simple strong shading.",
}
# character → its reference crop
CHARS = {"kirk": "kirk", "spock": "spock", "worf": "worf_tng", "picard": "picard",
         "data": "data", "troi": "troi", "obrien": "obrien"}
BUST = ("Redraw this character as a slot machine character portrait in a bold painted style like premium mobile "
        "casino slot art: a thick dark ink outline around the figure, smooth soft painted shading, glossy highlights, "
        "no cross-hatching. Same face, hair, expression and uniform. Head and shoulders, facing the viewer, the "
        "shoulders wide and cut off flat at the bottom edge of the image, the head in the upper half.")
def key(name):
    bg = "flat solid bright green" if name in GREEN else "flat solid magenta"
    return f"Isolate it on a perfectly {bg} background"
def bust_prompt(char):
    return f"{BUST} Remove the frame, the border and the whole background. {key(char)}. No text."
def prompt(name, n):
    return (f"{STYLES[n]} {KEEP.get(name, '')} Centred, filling most of the frame. {key(name)}: remove the "
            "coloured frame, the starfield, the outer glow and the dark background. No extra text, no border.")
def run(ref, out, text):
    if os.path.exists(out):
        return
    r = subprocess.run([sys.executable, "-I", str(TOOLS / "flux_edit.py"), ref, out, text, "512x512"],
                       capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip()[-300:], flush=True)
if __name__ == "__main__":
    names = sys.argv[1:] or [p.stem for p in sorted(Path("ref").glob("*.png"))] + list(CHARS)
    for name in names:
        for n in (1, 2, 3):
            if name in CHARS:
                run(f"ref/{CHARS[name]}.png", f"raw/bust_{name}_{n}.png", bust_prompt(name))
            elif name not in CHARS.values():
                run(f"ref/{name}.png", f"raw/{name}_{n}.png", prompt(name, n))
    print("DONE", flush=True)
