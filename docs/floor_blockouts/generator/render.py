"""Draw each plan as an SVG in plan pixels and write the page."""
import html
import importlib
import json
import sys
from pathlib import Path

from common import check, export

HERE = Path(__file__).parent
SHORT = {"blackjack": "BJ", "three_card_poker": "3CP", "ultimate_texas_holdem": "UTH", "mississippi_stud": "MS",
         "let_it_ride": "LIR", "pai_gow_fortune": "PG", "pai_gow_face_up": "PGF", "baccarat": "BAC",
         "high_card_flush": "HCF", "roulette": "R", "craps": "C", "master_table": "M"}
NAMES = {"blackjack": "Blackjack", "three_card_poker": "Three Card Poker", "ultimate_texas_holdem": "Ultimate Texas",
         "mississippi_stud": "Mississippi Stud", "let_it_ride": "Let It Ride", "pai_gow_fortune": "Pai Gow",
         "pai_gow_face_up": "Pai Gow Face Up", "baccarat": "Baccarat", "high_card_flush": "High Card Flush",
         "roulette": "Roulette", "craps": "Craps", "master_table": "Master table"}
FAMILY = {"roulette": "wheel", "craps": "dice", "master_table": "master", "baccarat": "bac"}
PATCH_ROLE = {"#d9c69a": "aisle", "#6e1f2c": "pitcarpet", "#2a3550": "hlcarpet", "#3a5a3a": "garden",
              "#8a6a3a": "boards"}
KIND_LABEL = {"floor": "Gaming floor", "high": "High limit", "food": "Food & drink", "feature": "Feature",
              "entry": "Entrance", "service": "NPCs only", "circ": "Circulation"}


def f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def rect(r, cls, extra=""):
    return f'<rect class="{cls}" x="{f(r[0])}" y="{f(r[1])}" width="{f(r[2])}" height="{f(r[3])}"{extra}/>'


def svg(data):
    rooms = data["rooms"]
    x0 = min(r["x"] for r in rooms) - 96
    y0 = min(r["y"] for r in rooms) - 96
    x1 = max(r["x"] + r["w"] for r in rooms) + 96
    y1 = max(r["y"] + r["h"] for r in rooms) + 260
    w, h = x1 - x0, y1 - y0
    out = [f'<svg class="plan" viewBox="{f(x0)} {f(y0)} {f(w)} {f(h)}" role="img" '
           f'aria-label="{html.escape(data["title"])} floor plan" xmlns="http://www.w3.org/2000/svg">',
           '<defs><pattern id="hatch-{0}" width="24" height="24" patternUnits="userSpaceOnUse" '
           'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="24" class="hatchline"/></pattern></defs>'
           .format(data["key"])]
    # grid
    g = []
    gx = (int(x0) // 256) * 256
    while gx < x1:
        g.append(f'<line x1="{gx}" y1="{f(y0)}" x2="{gx}" y2="{f(y1 - 200)}"/>')
        gx += 256
    gy = (int(y0) // 256) * 256
    while gy < y1 - 200:
        g.append(f'<line x1="{f(x0)}" y1="{gy}" x2="{f(x1)}" y2="{gy}"/>')
        gy += 256
    out.append('<g class="grid">' + "".join(g) + "</g>")
    for r in rooms:
        k = r["kind"]
        parts = [f'<g class="room k-{k}{" existing" if r["existing"] else ""}" data-room="{r["id"]}" tabindex="0">',
                 f'<title>{html.escape(r["name"])} · {f(r["w"])} × {f(r["h"])}</title>',
                 rect((r["x"], r["y"], r["w"], r["h"]), "wall"),
                 rect(r["interior"], "fl")]
        if r["npc_only"]:
            parts.append(rect(r["interior"], "", f' fill="url(#hatch-{data["key"]})"'))
        for p in r["patches"]:
            role = PATCH_ROLE.get(p["tint"].lower(), "aisle")
            rx = p["radius"] if p["shape"] == "rounded" else (min(p["w"], p["h"]) / 2 if p["shape"] == "oval" else 0)
            parts.append(rect((p["x"], p["y"], p["w"], p["h"]), f"patch {role}", f' rx="{f(rx)}"'))
        # back wall band (3/4 view)
        parts.append(rect((r["x"], r["y"], r["w"], r["top"]), "band"))
        for d in r["doors"]:
            gr = d["rect"]
            if d["side"] in ("top", "bottom"):
                cut = (gr[0], gr[1] - 1, gr[2], gr[3] + 2)
            else:
                cut = (gr[0] - 1, gr[1], gr[2] + 2, gr[3])
            parts.append(rect(cut, "fl gap"))
            if d["kind"] == "door" and d["own"]:
                if d["side"] in ("top", "bottom"):
                    yy = gr[1] + gr[3] / 2
                    parts.append(f'<line class="leaf" x1="{f(gr[0] + 4)}" y1="{f(yy)}" x2="{f(gr[0] + gr[2] - 4)}" y2="{f(yy)}"/>')
                else:
                    xx = gr[0] + gr[2] / 2
                    parts.append(f'<line class="leaf" x1="{f(xx)}" y1="{f(gr[1] + 4)}" x2="{f(xx)}" y2="{f(gr[1] + gr[3] - 4)}"/>')
        flat = [i for i in r["items"] if i["mount"] == "flat"]
        wall = [i for i in r["items"] if i["mount"] == "wall"]
        solid = [i for i in r["items"] if i["mount"] == "floor"]
        for i in flat:
            parts.append(rect(i["rect"], "flat", ' rx="24"'))
        for i in wall:
            parts.append(rect(i["rect"], "wallitem"))
        for i in solid:
            if i["kind"] == "table":
                fam = FAMILY.get(i["game"], "card")
                b = i["body"]
                parts.append(rect(b, f"felt f-{fam}", ' rx="34"'))
                if "sign" in i:
                    parts.append(rect(i["sign"], "sign"))
                for sx, sy in i["stands"]:
                    parts.append(f'<circle class="seat" cx="{f(sx)}" cy="{f(sy)}" r="9"/>')
                parts.append(f'<text class="tl" x="{f(b[0] + b[2] / 2)}" y="{f(b[1] + b[3] / 2 + 16)}">'
                             f'{SHORT.get(i["game"], "?")}</text>')
            elif i["kind"] == "slot":
                b = i["body"]
                parts.append(rect((b[0], b[1] - 12, b[2], b[3] + 14), "cab", ' rx="4"'))
            elif i["asset"] == "npc":
                b = i["body"]
                parts.append(f'<circle class="npc" cx="{f(b[0] + b[2] / 2)}" cy="{f(b[1] + b[3] / 2)}" r="11"/>')
            else:
                b = i["body"]
                cls = "furn bar" if "bar_counter" in i["asset"] or "cashier" in i["asset"] else "furn"
                parts.append(rect(b, cls, ' rx="4"'))
        # label
        name = html.escape(r["name"])
        dims = "" if r["npc_only"] else f'{f(r["w"])} × {f(r["h"])}{" · live now" if r["existing"] else ""}'
        if r["top"] >= 40:   # on the back wall, like the game's wall signs, in the first stretch of wall it fits
            cuts = [(d["rect"][0], d["rect"][0] + d["rect"][2]) for d in r["doors"] if d["side"] == "top"]
            cuts += [(i["rect"][0], i["rect"][0] + i["rect"][2]) for i in wall]
            segs, at = [], r["x"] + 8
            for a, b in sorted(cuts):
                if a > at:
                    segs.append((at, a))
                at = max(at, b)
            if r["x"] + r["w"] - 8 > at:
                segs.append((at, r["x"] + r["w"] - 8))

            def width(fs, with_dims):
                return fs * 0.62 * len(r["name"]) + (fs * 0.7 + fs * 0.62 * 0.62 * len(dims) if with_dims else 0) + 24
            pick = None
            for fs, with_dims in ((40, bool(dims)), (40, False), (32, False), (24, False), (18, False)):
                pick = next(((s, fs, with_dims) for s in segs if s[1] - s[0] >= width(fs, with_dims)), None)
                if pick:
                    break
            if not pick:
                s = max(segs, key=lambda s: s[1] - s[0])
                pick = (s, max(10, (s[1] - s[0] - 16) / (0.62 * len(r["name"]))), False)
            (sa, _), fs, with_dims = pick
            parts.append(f'<text class="rl" x="{f(sa + 12)}" y="{f(r["y"] + r["top"] / 2 + fs * 0.36)}" font-size="{f(fs)}">{name}'
                         + (f'<tspan class="rd" dx="{f(fs * 0.7)}" font-size="{f(fs * 0.62)}">{dims}</tspan>' if with_dims else "")
                         + "</text>")
        else:
            ix, iy = r["interior"][:2]
            parts.append(f'<text class="rl in" x="{f(ix + 18)}" y="{f(iy + 46)}" font-size="40">{name}'
                         f'<tspan class="rd" dx="28" font-size="25">{dims}</tspan></text>')
        parts.append("</g>")
        out += parts
    sx, sy = data["spawn"]
    out.append(f'<g class="spawn"><circle cx="{f(sx)}" cy="{f(sy)}" r="22"/><circle cx="{f(sx)}" cy="{f(sy)}" r="8" class="dot"/></g>')
    # scale bar: 1024 px = about 10 s at walking pace
    bx, by = x0 + 96, y1 - 130
    out.append('<g class="scale">')
    for n in range(4):
        out.append(rect((bx + n * 256, by, 256, 22), "sb" + str(n % 2)))
    for n in (0, 512, 1024):
        out.append(f'<text x="{f(bx + n)}" y="{f(by + 72)}" class="st">{n}</text>')
    out.append(f'<text x="{f(bx + 1080)}" y="{f(by + 22)}" class="st st2">game px · 1024 px ≈ 10 s walk · grid 256</text>')
    out.append("</g></svg>")
    return "\n".join(out)


def schedule(data):
    rows = []
    names = {r["id"]: r["name"] for r in data["rooms"]}
    for r in data["rooms"]:
        joins = []
        seen = set()
        for d in r["doors"]:
            if d["to"] and d["to"] not in seen:
                seen.add(d["to"])
                joins.append(f'{"archway" if d["kind"] == "archway" else "door"} to {html.escape(names[d["to"]])}')
        games = {}
        cabs = 0
        for i in r["items"]:
            if i["kind"] == "table":
                games[i["game"]] = games.get(i["game"], 0) + 1
            elif i["kind"] == "slot":
                cabs += 1
        bits = [f'{n} {NAMES[g]}' for g, n in games.items()]
        if cabs:
            bits.append(f"{cabs} slots")
        rows.append({"id": r["id"], "name": r["name"], "kind": r["kind"], "size": f'{f(r["w"])} × {f(r["h"])}',
                     "joins": ", ".join(joins), "has": ", ".join(bits), "note": r["note"], "existing": r["existing"],
                     "npc_only": r["npc_only"]})
    return rows


def build(mods):
    plans = []
    for key in mods:
        m = importlib.import_module(key)
        cleaned, probs = check(m.ROOMS, getattr(m, "SPAWN", "modern_lobby/spawn"))
        data = export(key, cleaned, probs, m.META)
        data["key"] = key
        data["svg"] = svg(data)
        data["schedule"] = schedule(data)
        print(key, len(probs), "problems", data["stats"], data["walks"])
        for p in probs:
            print("   ", p["room"], "|", p["message"])
        plans.append(data)
        write_blueprint(key, cleaned)
    return plans


def write_blueprint(key, cleaned):
    """The plan's new rooms as unplaced blueprints: room ids prefixed by the variation (a_, b_, c_) so all three
    can sit in one draft, and item and door ids dropped so the server gives fresh ones (an old id that matched a
    live table would otherwise be taken for that table). The live lobby and lifts are left out."""
    letter = key[-1]
    rooms = []
    for r in cleaned["rooms"]:
        if r.get("_existing"):
            continue
        r = {k: v for k, v in r.items() if not k.startswith("_")}
        r["id"] = f"{letter}_{r['id']}"
        r["placed"] = False
        r["doors"] = [{k: v for k, v in d.items() if k != "id"} for d in r["doors"]]
        r["items"] = [{k: v for k, v in i.items() if k != "id"} for i in r["items"]]
        rooms.append(r)
    out = HERE.parent / "blueprints" / f"{key}.json"
    out.write_text(json.dumps({"variation": key, "lobby_change": "modern_lobby's top door becomes an archway 192 wide",
                               "rooms": rooms}, indent=1))


if __name__ == "__main__":
    build(sys.argv[1:] or ["plan_a", "plan_b", "plan_c"])
