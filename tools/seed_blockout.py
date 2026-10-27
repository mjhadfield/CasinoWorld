#!/usr/bin/env python3
"""Seed a casino from one of the floor blockouts (docs/floor_blockouts/): A The Loop, B The Promenade, C The Boulevard.

    server/.venv/bin/python tools/seed_blockout.py a|b|c [--server URL]

Through the admin API of a running server (default: this checkout's dev instance), so it goes the same way on the
dev instance and the live one: a new casino (`loop`, `promenade` or `boulevard`) starting from Demo's live Modern
lobby (POST /api/casinos), Demo's two lifts beside it, the lobby's top door opened into a 192-wide archway (the
blueprint's lobby_change), and every plan_<x>.json room placed. It's published (the casino reopens with its
tables), named, and left hidden with no punters, for Mike to finish on the Floor plan tab: the slots (all
Armadillo), the staff looks, the limits, the floors and walls. It stops if that casino exists already or the plan
has problems.
"""
import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLUEPRINTS = ROOT / "docs/floor_blockouts/blueprints"
LIFTS = ("lift", "lift_copy")
# Each blockout: (the name POST /api/casinos makes its id from, its id, its full name, its blurb).
VARIATIONS = {
    "a": ("Loop", "loop", "The Loop", "One big open floor, a racetrack aisle round the pits, and slots all the way round."),
    "b": ("Promenade", "promenade", "The Promenade", "Grand rooms one after another, each a door further in."),
    "c": ("Boulevard", "boulevard", "The Boulevard", "A street of bars and shops, and a big floor beyond."),
}


def dev_url() -> str:
    import subprocess
    port = subprocess.run([str(ROOT / "tools/dev.sh"), "port"], capture_output=True, text=True, check=True).stdout.strip()
    return f"http://127.0.0.1:{port}"


def call(base: str, method: str, path: str, body=None) -> dict:
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=ssl._create_unverified_context(), timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"seed_blockout: {method} {path}: {e.code} {e.read().decode()[:300]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("variation", choices=sorted(VARIATIONS), help="a (The Loop), b (The Promenade) or c (The Boulevard)")
    ap.add_argument("--server", help="the server's http URL (default: this checkout's dev instance)")
    args = ap.parse_args()
    base = (args.server or dev_url()).rstrip("/")
    short, want, name, blurb = VARIATIONS[args.variation]
    if any(c["id"] == want for c in call(base, "GET", "/api/casinos")["casinos"]):
        sys.exit(f"seed_blockout: there's a {want} casino already.")
    demo = call(base, "GET", "/api/plan?casino=demo")["draft"]
    lifts = [r for r in demo["rooms"] if r["id"] in LIFTS]
    if len(lifts) != len(LIFTS):
        sys.exit(f"seed_blockout: Demo has no {' and '.join(LIFTS)} rooms to copy.")
    cid = call(base, "POST", "/api/casinos", {"name": short, "start": "lobby"})["id"]
    if cid != want:
        sys.exit(f"seed_blockout: the new casino came out as {cid!r}; delete it and look.")
    view = call(base, "GET", f"/api/plan?casino={cid}")
    lobby = next(r for r in view["draft"]["rooms"] if r["id"] == "modern_lobby")
    top = [d for d in lobby["doors"] if d["side"] == "top"]
    if len(top) != 1:
        sys.exit("seed_blockout: the Modern lobby hasn't one top door to open up.")
    top[0].update(kind="archway", width=192)
    rooms = [lobby] + lifts
    for r in json.loads((BLUEPRINTS / f"plan_{args.variation}.json").read_text())["rooms"]:
        rooms.append({**r, "placed": True})
    saved = call(base, "PUT", f"/api/plan/draft?casino={cid}",
                 {"rooms": rooms, "spawn": "modern_lobby/spawn", "base_rev": view["draft"]["rev"]})
    problems = [p for p in saved["problems"] if p["placed"]]
    if problems:
        for p in problems[:20]:
            print("  " + p["message"])
        sys.exit(f"seed_blockout: {len(problems)} problems; the draft is saved, nothing's published.")
    print(call(base, "POST", f"/api/plan/publish?casino={cid}")["message"])
    call(base, "PUT", f"/api/casinos/{cid}", {"name": name, "open": False, "population": 0, "blurb": blurb})
    c = next(c for c in call(base, "GET", "/api/casinos")["casinos"] if c["id"] == cid)
    print(f"{name}: {c['tables']} tables, {c['cabinets']} slot cabinets, hidden. Walk round it at /?casino={cid}")


if __name__ == "__main__":
    main()
