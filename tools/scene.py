#!/usr/bin/env python3
"""Designing a slot's scene (the Slot design wizard's Scene step) in a Claude Code session: docs/slots/scenes.md.

    tools/scene.py brief DESIGN              what Mike asked for, and what to design from (the live board)
    tools/scene.py fresh DESIGN              copy the live design into the dev instance (stop the dev server first)
    tools/scene.py shot DESIGN [SKIN.json]   the dev mockup with that skin (saved there as "draft" and chosen)
                   [--bonus trail|free|battle|voyage|expedition] [--out NAME]
    tools/scene.py put DESIGN SKIN.json      check a skin on the dev instance, then save it on the live board, by
                   [--slug SLUG] [--choose]  Claude (Mike picks it, unless --choose)

The dev instance (tools/dev.sh server) has its own copy of the designs, so drafts and shots never touch the live
board. Only `put` writes to the live board, through its API (the live server keeps each design in memory: never edit
its design.json). Shots land in .dev/shots/.
"""
import argparse
import json
import os
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / "server/.venv"
LIVE = "https://127.0.0.1:8661"
SHOTS = ROOT / ".dev/shots"


def dev_url() -> str:
    port = subprocess.run([str(ROOT / "tools/dev.sh"), "port"], capture_output=True, text=True, check=True).stdout.strip()
    return f"http://127.0.0.1:{port}"


def call(base: str, method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"} if data else {})
    ctx = ssl._create_unverified_context() if base.startswith("https") else None   # the live server's own certificate
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"scene.py: {method} {path}: {e.code} {e.read().decode(errors='replace')[:400]}")
    except urllib.error.URLError as e:
        sys.exit(f"scene.py: can't reach {base} ({e.reason}). Is the server running? (dev: tools/dev.sh server)")


def brief(args) -> None:
    d = call(LIVE, "GET", f"/api/slot-design/{args.design}")
    sc, folder = d["scene"], ROOT / "server/slot_designs" / args.design
    br = sc["brief"]
    print(f"# {d['name']}: the scene brief ({br.get('status') or 'not asked'}{', since ' + br['asked'] if br.get('asked') else ''})\n")
    print(br["text"] or "(no words)")
    for p in br["refs"]:
        print(f"  reference: {folder / p}")
    c = d["concept"]
    print(f"\nConcept: {c.get('brief') or '—'}\nStyle: {c.get('style') or '—'}")
    print(f"Lettering font: {sc['lettering_font']}  ({folder / 'fonts' / sc['lettering_font']} if it's the design's own)")
    print(f"Background: {folder / sc['background'] if sc['background'] else 'none'}")
    print(f"Logo: {folder / sc['logo']['file'] if sc['logo'].get('file') else 'none'}  lines {sc['logo'].get('lines')}")
    print(f"\nScenes: " + ", ".join(f"{s['slug']} ({s['base']}, {s['by']})" + (" [chosen]" if s["slug"] == sc["skin"] else "") for s in sc["skins"]))
    print("\nThe chosen skin:")
    print(json.dumps(sc["edit"], indent=1))
    print("\nThe symbols (chosen art):")
    lad = d["ladder"]
    for t in lad["tiers"]:
        s = next((x for x in d["symbols"] if x["id"] == lad["slots"].get(t)), None)
        if s:
            print(f"  {t:3} {s['name']}: {folder / s['file'] if s.get('file') else 'no art yet'}")


def fresh(args) -> None:
    src, dst = ROOT / "server/slot_designs" / args.design, ROOT / ".dev/slot_designs" / args.design
    if not src.is_dir():
        sys.exit(f"scene.py: no design {args.design!r}")
    try:
        call(dev_url(), "GET", "/api/slot-design")
        sys.exit("scene.py: stop the dev server first (it keeps designs in memory and would save over the copy)")
    except SystemExit as e:
        if "stop the dev server" in str(e):
            raise
    shutil.rmtree(dst, ignore_errors=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    # the copy doesn't draw pictures: the live board's queued jobs stay the live board's
    data = json.loads((dst / "design.json").read_text())
    data["jobs"] = [j for j in data.get("jobs", []) if j["status"] in ("done", "failed")]
    (dst / "design.json").write_text(json.dumps(data, indent=1))
    print(f"copied to {dst}; start the dev server (tools/dev.sh server)")


def _venv() -> None:
    try:
        import playwright  # noqa: F401
    except ImportError:
        if Path(sys.prefix) != VENV and (VENV / "bin/python").exists():
            os.execv(VENV / "bin/python", [str(VENV / "bin/python"), *sys.argv])
        sys.exit("scene.py: needs Playwright (see tools/shot.py)")


def shot(args) -> None:
    _venv()
    from playwright.sync_api import sync_playwright
    base = dev_url()
    if args.skin:
        skin = json.loads(Path(args.skin).read_text())
        call(base, "PUT", f"/api/slot-design/{args.design}/scene/skins/draft", {**skin, "by": "claude"})
        call(base, "POST", f"/api/slot-design/{args.design}/scene/skins/draft/choose")
    SHOTS.mkdir(parents=True, exist_ok=True)
    out = SHOTS / f"{args.out or 'scene_' + args.design}.png"
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1500, "height": 1100})
        errors = []
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        step = "mockup" if args.bonus else "scene"
        pg.goto(f"{base}/maintenance#design/{args.design}/{step}")
        pg.wait_for_selector("canvas.wz-canvas", timeout=20000)
        pg.wait_for_timeout(2500)
        if args.bonus:   # the Mockup step's rig: that bonus on the next spin
            sel = "select[aria-label='Bonus on the next spin']"
            have = pg.eval_on_selector_all(sel + " option", "os => os.map(o => o.value).filter(Boolean)")
            if args.bonus not in have:
                b.close()
                sys.exit(f"scene.py: {args.design} doesn't play {args.bonus} (it has: {', '.join(have)})")
            pg.select_option(sel, args.bonus)
            pg.click("text=Spin it")
            pg.wait_for_timeout(9000)
        pg.query_selector("canvas.wz-canvas").screenshot(path=str(out))
        b.close()
    for e in errors:
        print("page:", e)
    print(f"saved {out}")


def put(args) -> None:
    skin = {**json.loads(Path(args.skin).read_text()), "by": "claude"}
    slug = args.slug or skin.get("name", "scene")
    try:   # the dev server checks it first, when it's up, so a bad skin never reaches the live board
        dev = dev_url()
        call(dev, "PUT", f"/api/slot-design/{args.design}/scene/skins/draft", skin)
    except SystemExit as e:
        if "can't reach" not in str(e):
            raise
    got = call(LIVE, "PUT", f"/api/slot-design/{args.design}/scene/skins/{slug}", skin)["slug"]
    if args.choose:
        call(LIVE, "POST", f"/api/slot-design/{args.design}/scene/skins/{got}/choose")
    print(f"saved on the live board as {got!r}" + (" and chosen" if args.choose else ": Mike picks it on the Scene step"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("brief"); s.add_argument("design"); s.set_defaults(fn=brief)
    s = sub.add_parser("fresh"); s.add_argument("design"); s.set_defaults(fn=fresh)
    s = sub.add_parser("shot"); s.add_argument("design"); s.add_argument("skin", nargs="?")
    s.add_argument("--bonus", choices=["trail", "free", "battle", "voyage", "expedition"]); s.add_argument("--out"); s.set_defaults(fn=shot)
    s = sub.add_parser("put"); s.add_argument("design"); s.add_argument("skin"); s.add_argument("--slug"); s.add_argument("--choose", action="store_true")
    s.set_defaults(fn=put)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
