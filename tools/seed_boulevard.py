#!/usr/bin/env python3
"""Seed The Boulevard: a new hidden casino built from floor blockout C (docs/floor_blockouts/).

    server/.venv/bin/python tools/seed_boulevard.py [--server URL]

Through the admin API of a running server (default: this checkout's dev instance), so it goes the same way on the
dev instance and the live one: a new casino `boulevard` starting from Demo's live Modern lobby (POST /api/casinos),
Demo's two lifts beside it, the lobby's top door opened into a 192-wide archway (the blueprint's lobby_change), and
every plan_c.json room placed. It's published (the casino reopens with its tables), named "The Boulevard", and
left hidden with no punters, for Mike to finish on the Floor plan tab: the slots (all Armadillo), the staff looks,
the limits, the floors and walls. It stops if `boulevard` exists already or the plan has problems.
"""
import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLUEPRINT = ROOT / "docs/floor_blockouts/blueprints/plan_c.json"
LIFTS = ("lift", "lift_copy")


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
        sys.exit(f"seed_boulevard: {method} {path}: {e.code} {e.read().decode()[:300]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", help="the server's http URL (default: this checkout's dev instance)")
    base = (ap.parse_args().server or dev_url()).rstrip("/")
    if any(c["id"] == "boulevard" for c in call(base, "GET", "/api/casinos")["casinos"]):
        sys.exit("seed_boulevard: there's a boulevard casino already.")
    demo = call(base, "GET", "/api/plan?casino=demo")["draft"]
    lifts = [r for r in demo["rooms"] if r["id"] in LIFTS]
    if len(lifts) != len(LIFTS):
        sys.exit(f"seed_boulevard: Demo has no {' and '.join(LIFTS)} rooms to copy.")
    cid = call(base, "POST", "/api/casinos", {"name": "Boulevard", "start": "lobby"})["id"]
    if cid != "boulevard":
        sys.exit(f"seed_boulevard: the new casino came out as {cid!r}; delete it and look.")
    view = call(base, "GET", "/api/plan?casino=boulevard")
    lobby = next(r for r in view["draft"]["rooms"] if r["id"] == "modern_lobby")
    top = [d for d in lobby["doors"] if d["side"] == "top"]
    if len(top) != 1:
        sys.exit("seed_boulevard: the Modern lobby hasn't one top door to open up.")
    top[0].update(kind="archway", width=192)
    rooms = [lobby] + lifts
    for r in json.loads(BLUEPRINT.read_text())["rooms"]:
        rooms.append({**r, "placed": True})
    saved = call(base, "PUT", "/api/plan/draft?casino=boulevard",
                 {"rooms": rooms, "spawn": "modern_lobby/spawn", "base_rev": view["draft"]["rev"]})
    problems = [p for p in saved["problems"] if p["placed"]]
    if problems:
        for p in problems[:20]:
            print("  " + p["message"])
        sys.exit(f"seed_boulevard: {len(problems)} problems; the draft is saved, nothing's published.")
    print(call(base, "POST", "/api/plan/publish?casino=boulevard")["message"])
    call(base, "PUT", "/api/casinos/boulevard", {"name": "The Boulevard", "open": False, "population": 0,
                                                  "blurb": "A street of bars and shops, and a big floor beyond."})
    c = next(c for c in call(base, "GET", "/api/casinos")["casinos"] if c["id"] == "boulevard")
    print(f"The Boulevard: {c['tables']} tables, {c['cabinets']} slot cabinets, hidden. Walk round it at /?casino=boulevard")


if __name__ == "__main__":
    main()
