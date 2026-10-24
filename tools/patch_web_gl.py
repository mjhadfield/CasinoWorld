#!/usr/bin/env python3
"""Makes the web export's WebGL layer reuse the ids of deleted GL objects (run by `tools/dev.sh export`).

    tools/patch_web_gl.py build/web/index.js

Emscripten's GL emulation names every buffer, vertex array, texture, ... from one counter that only goes up, and
pads each lookup table with nulls to that counter. Godot's 2D renderer makes a fresh buffer and vertex array for
every polygon, circle and arc a node draws, each time it redraws, so a floor full of animated tables creates tens of
thousands a second. After about 134 million the buffers table outgrows V8's longest array, glGenBuffers throws
`RangeError: Invalid array length` mid-frame and the game freezes, after about 50 minutes at Mike's frame rate.

This hands a deleted object's id back out (as desktop GL does), so the tables stay as big as the most objects alive
at once. It fails loudly when index.js doesn't look as expected (a new Godot or Emscripten), so check what changed
and update the patterns rather than shipping an unpatched export. Running it twice changes nothing.
"""
import re
import sys
from pathlib import Path

MARKER = "/*casino:gl-id-reuse*/"
NEW_ID = "getNewId:table=>{var ret=GL.counter++;for(var i=table.length;i<ret;i++){table[i]=null}return ret}"
# A freed id is only pooled if its slot held an object, so a delete of 0 or of a name already deleted (the vertex
# array delete doesn't check) can't put an id in the pool twice.
NEW_ID_REUSING = (MARKER + "getNewId:table=>{var f=table.freeIds;if(f&&f.length)return f.pop();"
                  "var ret=GL.counter++;for(var i=table.length;i<ret;i++){table[i]=null}return ret},"
                  "freeId:(table,id)=>{if(id&&table[id]){table[id]=null;(table.freeIds||(table.freeIds=[])).push(id)}}")
KINDS = ["buffers", "framebuffers", "programs", "queries", "renderbuffers", "shaders", "syncs", "textures", "vaos"]


def patch(js: str) -> str:
    if MARKER in js:
        return js
    if js.count(NEW_ID) != 1:
        sys.exit("patch_web_gl: GL.getNewId isn't the one this patch knows: check the new index.js and update it")
    js = js.replace(NEW_ID, NEW_ID_REUSING)
    for kind in KINDS:
        free = f"GL.{kind}[id]=null"
        if js.count(free) != 1:
            sys.exit(f"patch_web_gl: expected one '{free}' in index.js, found {js.count(free)}: update the patch")
        js = js.replace(free, f"GL.freeId(GL.{kind},id)")
    left = sorted(set(re.findall(r"GL\.(\w+)\[\w+\]=null", js)) - {"contexts"})
    if left:
        sys.exit(f"patch_web_gl: index.js frees GL ids this patch doesn't pool ({', '.join(left)}): add them to KINDS")
    return js


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip().splitlines()[2].strip())
    path = Path(sys.argv[1])
    js = path.read_text()
    patched = patch(js)
    if patched != js:
        path.write_text(patched)
        print(f"patch_web_gl: {path} reuses GL ids")


if __name__ == "__main__":
    main()
