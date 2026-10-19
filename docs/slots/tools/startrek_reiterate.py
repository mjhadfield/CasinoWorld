"""Make 3 more variants of every symbol marked "Reiterate" in the picker, using the chosen image as the FLUX
reference and the row's note as extra direction. New takes are numbered on from the last, cut out (or put in
the character frame) and show up in the picker on reload. Clears the flag and logs the round in the row's
history.  usage (from docs/slots/startrek): python ../tools/startrek_reiterate.py [--dry-run]"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from startrek_gen import CHARS, BUST, key, run
from startrek_cut import cutout
from process_flux import normalise
from startrek_frame import HUES, compose

SEL = Path("selections.json")

def next_n(prefix):
    ns = [int(m.group(1)) for p in Path("raw").glob(f"{prefix}_*.png")
          if (m := re.fullmatch(re.escape(prefix) + r"_(\d+)", p.stem))]
    return max(ns + [3]) + 1  # round 1 used 1-3 for every symbol

def main(dry):
    sel = json.loads(SEL.read_text())
    todo = {name: st for name, st in sel.items() if st.get("reiterate") and st.get("file")}
    for name, st in todo.items():
        note = (st.get("note") or "").strip()
        extra = f" Change: {note.rstrip('.')}." if note else ""
        if m := re.fullmatch(r"chars/(\w+?)_(\d+)_[a-z]+\.png", st["file"]):
            char, n = m.groups()
            src, prefix = f"raw/bust_{char}_{n}.png", f"bust_{char}"
            text = (f"Make a fresh variation of this character portrait. {BUST}{extra} "
                    f"{key(char)}. No frame, no background, no text.")
        else:
            src = "raw/" + Path(st["file"]).name
            prefix = name
            text = (f"Make a fresh variation of this slot machine symbol: same subject, same style and colours, "
                    f"crisp high-detail glossy casino slot game art.{extra} Centred, filling most of the frame. "
                    f"{key(name)}. No extra text, no border.")
        first = next_n(prefix)
        outs = [f"raw/{prefix}_{n}.png" for n in range(first, first + 3)]
        print(f"{name}: from {src} → {', '.join(outs)}" + (f"  [{note}]" if note else ""), flush=True)
        if dry:
            continue
        for out in outs:
            run(src, out, text)
            p = Path(out)
            if not p.exists():
                continue
            if prefix.startswith("bust_"):
                bust = cutout(p)
                for hue in HUES:
                    compose(bust, hue).save(f"chars/{p.stem[5:]}_{hue}.png", optimize=True)
            else:
                normalise(cutout(p)).save(f"cut/{p.name}", optimize=True)
        # Re-read before writing: the picker may have saved while FLUX ran.
        sel = json.loads(SEL.read_text())
        row = sel.setdefault(name, {})
        row["reiterate"] = False
        row.setdefault("history", []).append({"from": st["file"], "note": note, "made": [Path(o).stem for o in outs]})
        SEL.write_text(json.dumps(sel, indent=1, sort_keys=True))
    print("DONE" if todo else "Nothing marked Reiterate.", flush=True)

if __name__ == "__main__":
    main("--dry-run" in sys.argv)
