"""Shared helpers: build CasinoWorld plan rooms in game pixels and check them with the server's own plan.problems.
Read-only against the live data (only the asset library and the live lobby are read)."""
import copy
import json
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[3] / "server"
sys.path.insert(0, str(SERVER))
from casino_server import plan, plan_assets  # noqa: E402

plan_assets.AssetLibrary(SERVER / "data")
LIVE = json.loads((SERVER / "data/casinos/demo/plan/live.json").read_text())
SLOT = "armadillo"


def existing(rid):
    r = copy.deepcopy(next(r for r in LIVE["rooms"] if r["id"] == rid))
    r["placed"] = True
    return r


def lobby(top_width=192):
    """The live Modern lobby, its top door opened into an archway."""
    r = existing("modern_lobby")
    for d in r["doors"]:
        if d["side"] == "top":
            d.update(kind="archway", width=top_width)
    r["_kind"] = "entry"
    r["_existing"] = True
    return r


def lifts():
    out = []
    for rid in ("lift", "lift_copy"):
        r = existing(rid)
        r["_kind"] = "service"
        r["_existing"] = True
        r["npc_only"] = True
        out.append(r)
    return out


def room(rid, name, x, y, w, h, kind, doors=(), items=(), patches=(), points=(), zones=(), npc_only=False,
         floor="carpet", note="", thin=False):
    r = {"id": rid, "name": name, "placed": True, "x": x, "y": y, "w": w, "h": h,
         "floor": {"texture": floor, "tint": "#ffffff"}, "patches": list(patches),
         "walls": {"style": "crimson", "sign": name.upper()[:24], "sign_at": w / 2},
         "doors": [{"side": s, "at": at, "width": wd, "kind": k} for s, at, wd, k in doors],
         "items": list(items), "paths": {"points": [], "zones": list(zones)}, "_kind": kind, "_note": note}
    for n, p in enumerate(points):
        px, py, pk = (p + ("wander",))[:3]
        r["paths"]["points"].append({"name": f"{pk}_{n}", "x": px, "y": py, "kind": pk, "weight": 1, "linger": 20})
    if npc_only:
        r["npc_only"] = True
    if thin:
        r["walls"]["back"] = "thin"
    return r


def T(game, x, y, rot=0, label=None):
    return {"asset": f"table:{game}", "x": x, "y": y, "rot": rot, "props": {"label": label} if label else {}}


def B(size, x, y, facing="down"):
    return {"asset": f"bank:{size}", "x": x, "y": y, "facing": facing, "props": {"slots": [SLOT]}}


def A(asset, x, y, facing="down"):
    return {"asset": asset if asset in plan.PIECES else "a:" + asset, "x": x, "y": y, "facing": facing, "props": {}}


def NPC(x, y, name, look="dealer"):
    return {"asset": "npc", "x": x, "y": y, "props": {"look": look, "name": name}}


def patch(x, y, w, h, colour, shape="rect", radius=0, border="none"):
    return {"x": x, "y": y, "w": w, "h": h, "texture": "plain", "tint": colour, "shape": shape, "radius": radius,
            "pattern": {"kind": "none", "colour": "#000000", "size": 16, "opacity": 30},
            "border": {"style": border, "colour": "#c9a24a", "width": 4}}


def pit(cx, yt, top, bottom, sp=344, label=""):
    """Card tables back to back round a dealers' aisle: `top` faces up (players north), `bottom` faces down.
    yt is the top row's centre; the pit runs yt-62 (top players) to yt+438 (bottom players)."""
    items = []
    for row, games, y, rot in ((0, top, yt, 180), (1, bottom, yt + 376, 0)):
        n = len(games)
        for i, g in enumerate(games):
            if g:
                items.append(T(g, cx + (i - (n - 1) / 2) * sp, y, rot))
    items.append(A("podium", cx, yt + 192))
    return items


def bar_run(cx, y, stools=10, back=True):
    """A Vegas bar: back bar on the wall (y = wall top), counter below at y, stools in front."""
    items = []
    if back:
        items.append(A("vegas_back_bar", cx, 70))
    items.append(A("vegas_bar_counter", cx, y))
    for i in range(stools):
        items.append(A("vegas_bar_stool", cx - 126 + i * 252 / max(1, stools - 1), y + 40))
    return items


def dining(x0, y0, cols, rows, dx=112, dy=104):
    """Restaurant tables: a round table with an armchair either side."""
    items = []
    for c in range(cols):
        for r in range(rows):
            x, y = x0 + c * dx, y0 + r * dy
            items += [A("round_table", x, y), A("armchair", x - 46, y + 4, "right"), A("armchair", x + 46, y + 4, "left")]
    return items


def check(rooms, spawn="modern_lobby/spawn"):
    raw = {"rooms": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rooms], "spawn": spawn}
    cleaned = plan.clean(raw, {"rooms": [], "next": {}})
    probs = plan.problems(cleaned, SERVER / "slot_builds")
    # carry my notes across (clean keeps order)
    for src, dst in zip(rooms, cleaned["rooms"]):
        for k, v in src.items():
            if k.startswith("_"):
                dst[k] = v
    return cleaned, probs


def export(name, cleaned, probs, meta):
    """Everything the drawing needs, in plan coordinates."""
    placed = [r for r in cleaned["rooms"] if r["placed"]]
    ops, _ = plan.openings(placed)
    routes = plan.Routes(placed, ops)
    out_rooms = []
    stats = {"tables": 0, "seats": 0, "cabinets": 0, "games": {}}
    for r in placed:
        doors = []
        for o in ops.get(r["id"], []):
            doors.append({"rect": plan.gap(r, o), "kind": o["kind"], "to": o["to"], "side": o["side"],
                          "own": o["owner"] == r["id"]})
        items = []
        for it in plan.flat_items(r):
            s = plan.shapes(r, it)
            if s is None:
                continue
            kind = plan.asset_kind(it["asset"])
            d = {"kind": kind, "asset": it["asset"], "body": s["body"], "rect": s["rect"], "stands": s["stands"],
                 "mount": s["mount"], "rot": it.get("rot", 0), "facing": it.get("facing")}
            if kind == "table":
                g = it["asset"][6:]
                d["game"] = g
                d["label"] = it["props"].get("label")
                if "sign" in s:
                    d["sign"] = s["sign"]["body"]
                stats["tables"] += 1
                stats["seats"] += len(s["stands"])
                stats["games"][g] = stats["games"].get(g, 0) + 1
            elif kind == "slot":
                stats["cabinets"] += 1
                stats["seats"] += 1
            elif it["asset"] == "npc":
                d["name"] = it["props"].get("name")
            items.append(d)
        interior = plan.interior(r)
        out_rooms.append({"id": r["id"], "name": r["name"], "x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"],
                          "top": plan.wall_top(r), "interior": interior, "kind": r.get("_kind", "floor"),
                          "note": r.get("_note", ""), "existing": r.get("_existing", False),
                          "npc_only": r.get("npc_only", False),
                          "patches": [{**p, "x": p["x"] + r["x"], "y": p["y"] + r["y"]} for p in r["patches"]],
                          "doors": doors, "items": items,
                          "points": [(r["x"] + p["x"], r["y"] + p["y"], p["kind"]) for p in r["paths"]["points"]]})
    spawn_room, spawn_pt = cleaned["spawn"].split("/")
    sr = next(r for r in placed if r["id"] == spawn_room)
    sp = next(p for p in sr["paths"]["points"] if p["name"] == spawn_pt)
    start = (sr["x"] + sp["x"], sr["y"] + sp["y"])
    walks = {}
    for target, rid in meta.get("walks", {}).items():
        r = next(r for r in placed if r["id"] == rid)
        c = (r["x"] + r["w"] / 2, r["y"] + plan.wall_top(r) + (r["h"] - plan.wall_top(r)) / 2)
        walks[target] = round(routes.distance(start, c) / 105.0)
    return {"name": name, "rooms": out_rooms, "problems": probs, "stats": stats, "walks": walks,
            "spawn": start, **{k: v for k, v in meta.items() if k != "walks"}}
