#!/usr/bin/env python3
"""Lets the web export run inside a plain-HTTP page's frame, Citadel's Casino page (run by `tools/dev.sh export`).

    tools/patch_web_frame.py build/web

A frame is only a secure context when every page above it is one too. Citadel is served over plain HTTP, so the
game at https://…:8661 isn't a secure context inside its Casino page, although it is in a tab of its own. Two things
stop it there:

- Godot's loader (index.html) refuses to start without a secure context ("Secure Context - Check web server
  configuration"). The patch drops only that entry from the missing-features list; anything else still stops it.
- AudioWorklet only exists in secure contexts. The mixer already falls back to a ScriptProcessor without it, but
  sample playback (every sound effect) loads and attaches a position-reporting worklet unconditionally and throws.
  Without AudioWorklet the patch skips that worklet, so sounds play and only their playback position isn't
  reported (the client never asks for it).

In a secure context (the game's own tab) nothing changes: the filtered entry never appears and AudioWorklet exists.
It fails loudly when the files don't look as expected (a new Godot), so check what changed and update the patterns
rather than shipping an unpatched export. Running it twice changes nothing. Checked 2026-11-17 on Godot 4.7.2 in a
frame on a plain-HTTP LAN page: the game connected, loaded and played its sounds, no errors.
"""
import sys
from pathlib import Path

MARKER = "/*casino:framed*/"

CHECK = "const missing = Engine.getMissingFeatures({\n\t\tthreads: GODOT_THREADS_ENABLED,\n\t});"
CHECK_FRAMED = (MARKER + "const missing = Engine.getMissingFeatures({\n\t\tthreads: GODOT_THREADS_ENABLED,\n\t})"
                ".filter((m) => !m.startsWith('Secure Context'));")

ADD_MODULE = "GodotAudio.audioPositionWorkletPromise=ctx.audioWorklet.addModule(path);"
ADD_MODULE_FRAMED = (MARKER + "GodotAudio.audioPositionWorkletPromise="
                     "ctx.audioWorklet?ctx.audioWorklet.addModule(path):null;")
CONNECT = ("async connectPositionWorklet(start){await GodotAudio.audioPositionWorkletPromise;"
           "if(this.isCanceled){return}")
CONNECT_FRAMED = CONNECT + "if(!GodotAudio.ctx.audioWorklet){if(start){this.start()}return}"


def swap(text: str, old: str, new: str, what: str) -> str:
    if text.count(old) != 1:
        sys.exit(f"patch_web_frame: expected one {what}, found {text.count(old)}: check the new export and update the patch")
    return text.replace(old, new)


def patch_html(html: str) -> str:
    if MARKER in html:
        return html
    return swap(html, CHECK, CHECK_FRAMED, "getMissingFeatures call in index.html")


def patch_js(js: str) -> str:
    if MARKER in js:
        return js
    js = swap(js, ADD_MODULE, ADD_MODULE_FRAMED, "position worklet addModule in index.js")
    return swap(js, CONNECT, CONNECT_FRAMED, "connectPositionWorklet in index.js")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip().splitlines()[2].strip())
    web = Path(sys.argv[1])
    for name, fn in (("index.html", patch_html), ("index.js", patch_js)):
        path = web / name
        text = path.read_text()
        patched = fn(text)
        if patched != text:
            path.write_text(patched)
            print(f"patch_web_frame: {path} runs in a plain-HTTP page's frame")


if __name__ == "__main__":
    main()
