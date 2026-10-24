"""
The floor plan: the casino's rooms, side by side on one plan, and everything placed in them -- the tables, the slot
cabinets, the furniture and decor, and the paths NPCs take. Designed on the admin page's Floor plan tab as blueprints
(a draft), tried out in the game's preview, then published to the live floor.

<data dir>/plan/ holds it:
  draft.json      what the Floor plan tab edits
  live.json       what the casino runs (published from the draft)
  history/*.json  the last HISTORY publishes, to roll back to
No folder: the first run seeds both with the lobby (live) and the classic floor and pit as unplaced blueprints.

A plan: {"rev", "next": {prefix: serial}, "spawn": "room/point", "rooms": [room]}. A room:
  {"id", "name", "placed",           # unplaced: a blueprint in the library, not on the floor
   "map_name",                       # (only when set) what players see it called, on the minimap; name is the builder's
   "npc_only": true,                 # (only when set) NPCs walk in and out, players can't: a lift, a back room
   "map_hidden": true,               # (only when set) left off the minimap: not drawn, no door tab names it
   "x", "y", "w", "h",               # its place on the plan and its size, walls included (pixels)
   "floor": {"texture", "tint"},     # tint multiplies the texture: #ffffff is none ("plain" is just the tint)
   "patches": [{"x", "y", "w", "h", "texture", "tint", "shape": rect|rounded|oval, "radius",
                "pattern": {"kind": none|stripes|diagonal|checks|diamonds|dots|grid, "colour", "size", "opacity"},
                "border": {"style": none|line|double|inlay, "colour", "width"}}],
   "walls": {"style", "sign", "sign_at", "back": "thin"},   # (back only when thin)
   "doors": [{"id", "side": top|bottom|left|right, "at", "width", "kind": door|archway}],
   "items": [{"id", "asset", "x", "y", "rot", "facing", "props"}],
   "paths": {"points": [{"name", "x", "y", "kind": spawn|arrival|wander, "weight", "linger"}],
             "zones": [{"x", "y", "w", "h", "kind": npc_block|block}]}}
Everything in a room is placed from its top-left corner, so moving a room moves what's in it. The back (top) wall is a
WALL_TOP-high band drawn in 3/4 view, or with walls.back "thin" just a border as wide as the side walls (WALL_SIDE);
the front wall is WALL_BOTTOM. A room's floor inside its walls is at least MIN_WIDTH - 2 * WALL_SIDE across and
MIN_FLOOR deep. A door sits in
one room's wall; where another room's wall runs along the same line, the opening goes through both and joins them
(an archway shows both rooms; a door looks closed until you're through it). A door with nobody beyond stays shut.
An NPCs-only room is a rabbit hole: the client keeps players out of its doorways and never shows it, so NPCs given
an arrival point in it step out of its door and leave back through it. Players can't spawn in one.

An item's asset is "table:<game>" (its id is its table id: tcp_3, bj_6...), "slot" (a cabinet: props.variant; its id
slot_<n>), a built-in piece ("podium", "npc": a figure standing there, props.look and props.name) or a piece of
furniture from the asset library ("a:<id>", plan_assets.py). Ids are given by the server and never reused. Tables
turn by `rot` (the catalogue says which turns each game takes); everything else faces one of FACINGS. A table with a
results sign (Roulette, Craps) has props.sign, the end it stands past as the players see it (SIGN_SIDES; unset, the
usual end: sign_side()); the sign has its own shapes beside the table's (shapes()["sign"]).

install() puts the live plan's placed rooms on the floor (floor.py): their tables and cabinets join floor.TABLES, and
their points, seats and doors give the NPCs somewhere to go. Publishing changes the floor at once when only places
changed; adding or removing tables or cabinets restarts the casino (as the old Floor tab's Apply did).

The shapes come from plan_catalogue.json, measured from the client's scenes by tools/plan_catalogue.gd.
"""
import copy
import heapq
import json
import math
import re
import subprocess
import time
from pathlib import Path

from casino_server import floor, slot_builds, sounds
from casino_server.slots.variants import VARIANTS
from casino_server.tables import master

CATALOGUE = json.loads((Path(__file__).resolve().parent / "plan_catalogue.json").read_text())
CLASSIC = json.loads((Path(__file__).resolve().parent / "plan_classic.json").read_text())

WALL_TOP, WALL_SIDE, WALL_BOTTOM = 70, 8, 10
MIN_WIDTH, MIN_FLOOR, MAX_SIZE = 48, 48, (8000, 8000)   # (the smallest: one figure standing, with a side door to it)
SIDES = ("top", "bottom", "left", "right")
FACINGS = ("down", "up", "left", "right")
SIGN_SIDES = ("right", "left")   # which end of a table its results sign stands past, as its players see it
DOOR_KINDS = ("door", "archway")
DOOR_WIDTH = (40, 600)
POINT_KINDS = ("spawn", "arrival", "wander")
ZONE_KINDS = ("npc_block", "block")
# Floor patches: an outline, a pattern laid over the floor in a second colour, and a border inside the edge.
PATCH_SHAPES = {"rect": "Rectangle", "rounded": "Rounded", "oval": "Oval"}
PATCH_PATTERNS = {"none": "None", "stripes": "Stripes", "diagonal": "Diagonal stripes", "checks": "Checks",
                  "diamonds": "Diamonds", "dots": "Dots", "grid": "Grid"}
PATCH_BORDERS = {"none": "None", "line": "Line", "double": "Double line", "inlay": "Inlay"}
HISTORY = 20
AGENT = 9            # how far a walker keeps from anything (the client's nav agent radius)
CELL = 8             # the reachability grid
SLACK = 2            # px two things may touch by before they're in each other's way
NPC_SPEED = 85.0     # px a second an NPC walks (the client paths them there in the time given)
DETOUR = 1.25        # paths go round things: a walk is this much longer than the straight line
ID_RE = re.compile(r"^[a-z0-9_]{1,32}$")
COLOUR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

PREFIX = {"three_card_poker": "tcp", "blackjack": "bj", "pai_gow_fortune": "pgf", "pai_gow_face_up": "pgu",
          "mississippi_stud": "ms", "ultimate_texas_holdem": "uth", "let_it_ride": "lir", "high_card_flush": "hcf",
          "baccarat": "bac", "roulette": "rou", "craps": "crp", "master_table": "mt"}
SLOT_PREFIX = "slot"
ITEM_PREFIX = "i"

# The walls' looks (the client and the page draw them from these): paper and its stripe, the wainscot below,
# the brass trim, the dark edge (side and front walls) and the sign. "none" draws no walls at all, just the floor
# to the room's edges (a lift): only the look, as the walls still keep people to the floor inside them.
WALL_STYLES = {
    "crimson": {"name": "Crimson", "paper": "#4a0f1d", "stripe": "#561526", "wainscot": "#2b0a10", "trim": "#c9a24a", "edge": "#1a0508"},
    "emerald": {"name": "Emerald", "paper": "#0f3a2a", "stripe": "#144734", "wainscot": "#0a2219", "trim": "#c9a24a", "edge": "#06140e"},
    "navy": {"name": "Navy", "paper": "#142243", "stripe": "#1b2c54", "wainscot": "#0b1428", "trim": "#c9a24a", "edge": "#070c18"},
    "ivory": {"name": "Ivory", "paper": "#d9cdb4", "stripe": "#cfc1a3", "wainscot": "#6b4a2e", "trim": "#b08a3e", "edge": "#3a2716"},
    "walnut": {"name": "Walnut panels", "paper": "#5a3a22", "stripe": "#4c3020", "wainscot": "#2e1d12", "trim": "#c9a24a", "edge": "#1e130b"},
    "charcoal": {"name": "Charcoal", "paper": "#26262b", "stripe": "#2e2e34", "wainscot": "#151518", "trim": "#d4af37", "edge": "#0c0c0e"},
    "onyx": {"name": "Onyx & gold", "paper": "#1e1e23", "stripe": "#25252b", "wainscot": "#111114", "trim": "#d4af5a", "edge": "#09090b"},
    "travertine": {"name": "Travertine", "paper": "#c8baa2", "stripe": "#c0b199", "wainscot": "#3b352e", "trim": "#b8955a", "edge": "#27231e"},
    "none": {"name": "None (just the floor)"},
}
# Floors (the asset library adds more): "carpet" is the casino's own, "plain" just its tint.
FLOORS = {"carpet": {"name": "Casino carpet"}, "plain": {"name": "Plain"}}

# Built-in pieces besides the tables and cabinets: their footprint (all they cover, drawn) and body (what blocks
# walking), from their base point, as (x, y, w, h).
PIECES = {
    "podium": {"name": "Pit podium", "category": "Casino", "rect": [-17, -31, 34, 33], "body": [-15, -9, 30, 10]},
    "npc": {"name": "Standing figure", "category": "People", "rect": [-12, -48, 24, 52], "body": [-8, -5, 16, 8]},
}

# Furniture from the asset library (plan_assets.py fills it): id -> {"name", "category", "mount", "rect", "body", ...}
ASSETS: dict = {}

_LIVE: dict = {}       # what install() put on the floor


class PlanError(ValueError):
    """A plan the server can't take (shown to the page as-is)."""


# ------------------------------------------------------------------ files
def plan_dir(data_dir: Path) -> Path:
    return data_dir / "plan"


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except (ValueError, OSError) as e:
        print(f"{path.name} not read ({e})")
        return None


def _write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


def lobby() -> dict:
    """The first room: a small lobby, walled in, with a door top centre (where the casino will be built)."""
    return {"id": "lobby", "name": "Lobby", "placed": True, "x": 0, "y": 0, "w": 1024, "h": 640,
            "floor": {"texture": "carpet", "tint": "#ffffff"}, "patches": [],
            "walls": {"style": "crimson", "sign": "", "sign_at": 512},
            "doors": [{"id": "d1", "side": "top", "at": 512, "width": 64, "kind": "door"}],
            "items": [],
            "paths": {"points": [{"name": "spawn", "x": 512, "y": 540, "kind": "spawn", "weight": 1, "linger": 0},
                                 {"name": "arrival", "x": 512, "y": 600, "kind": "arrival", "weight": 1, "linger": 0}],
                      "zones": []}}


def first_plan() -> dict:
    """What a casino with no plan yet starts with: the lobby on the floor, the classic floor and pit in the library."""
    rooms = [lobby()] + copy.deepcopy(CLASSIC["rooms"])
    for r in rooms[1:]:
        r["placed"] = False
    plan = {"rev": 1, "next": {}, "spawn": "lobby/spawn", "rooms": rooms}
    plan["next"] = _serials(plan)
    return plan


def load_live(data_dir: Path) -> dict:
    """The published plan (seeding the first one if there's none)."""
    d = plan_dir(data_dir)
    live = _read(d / "live.json")
    if live is None:
        live = first_plan()
        _write(d / "live.json", live)
        if not (d / "draft.json").exists():
            _write(d / "draft.json", live)
    return live


def load_draft(data_dir: Path) -> dict:
    draft = _read(plan_dir(data_dir) / "draft.json")
    return draft if draft is not None else copy.deepcopy(load_live(data_dir))


# ------------------------------------------------------------------ geometry
def _overlap(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _inside(p, r) -> bool:
    return r[0] <= p[0] <= r[0] + r[2] and r[1] <= p[1] <= r[1] + r[3]


def _contains(outer, r) -> bool:
    return outer[0] <= r[0] and outer[1] <= r[1] and r[0] + r[2] <= outer[0] + outer[2] and r[1] + r[3] <= outer[1] + outer[3]


def _grow(r, by):
    return (r[0] - by, r[1] - by, r[2] + 2 * by, r[3] + 2 * by)


def _at(r, x, y):
    return (r[0] + x, r[1] + y, r[2], r[3])


def wall_top(room: dict) -> int:
    """How deep a room's back wall is: the full 3/4-view wall, or a thin border like the sides."""
    return WALL_SIDE if room["walls"].get("back") == "thin" else WALL_TOP


def interior(room: dict) -> tuple:
    """The floor inside a room's walls, on the plan."""
    top = wall_top(room)
    return (room["x"] + WALL_SIDE, room["y"] + top, room["w"] - 2 * WALL_SIDE, room["h"] - top - WALL_BOTTOM)


def outline(room: dict) -> tuple:
    return (room["x"], room["y"], room["w"], room["h"])


def asset_kind(asset: str) -> str:
    if asset.startswith("table:"):
        return "table"
    if asset == "slot":
        return "slot"
    if asset in PIECES:
        return "piece"
    return "furniture"


def piece(asset: str) -> dict | None:
    """A built-in piece's or a library asset's shapes ({"rect", "body", "mount"}), or None."""
    if asset in PIECES:
        return {"mount": "floor", **PIECES[asset]}
    if asset.startswith("a:"):
        return ASSETS.get(asset[2:])
    return None


def master_stands(room: dict, item: dict) -> dict:
    """A Master Table's seat points as six seats and as five (Let It Ride, High Card Flush): {"6": [...], "5": [...]}."""
    x, y = room["x"] + item["x"], room["y"] + item["y"]
    game = CATALOGUE["games"][master.GAME_KEY]
    at = game["at"].get(str(item.get("rot", 0))) or game["at"]["0"]
    return {"6": [(x + p[0], y + p[1]) for p in at["stands"]], "5": [(x + p[0], y + p[1]) for p in at["stands5"]]}


def shapes(room: dict, item: dict) -> dict | None:
    """An item's shapes on the plan: rect (all it covers), body (what blocks walking), the points its players stand
    on to sit down, and whether it stands on the floor (rugs lie flat, pictures hang on the wall). None: an asset
    that isn't known (any more)."""
    x, y = room["x"] + item["x"], room["y"] + item["y"]
    kind = asset_kind(item["asset"])
    if kind == "table":
        game = CATALOGUE["games"].get(item["asset"][6:])
        if game is None:
            return None
        at = game["at"].get(str(item.get("rot", 0))) or game["at"]["0"]
        out = {"kind": kind, "rect": _at(at["rect"], x, y), "body": _at(at["body"], x, y), "mount": "floor",
               "stands": [(x + p[0], y + p[1]) for p in at["stands"]]}
        if "sign" in at:   # its results sign, past the end props.sign says: drawn over what's beyond, standing on its base
            sign = at["sign"][sign_side(item)]
            out["sign"] = {"rect": _at(sign["rect"], x, y), "body": _at(sign["body"], x, y)}
        return out
    if kind == "slot":
        at = CATALOGUE["cabinet"][item.get("facing", "down")]
        f = item.get("facing", "down")
        stool = {"down": (-10, 11, 20, 12), "up": (-10, -21, 20, 12), "left": (-29, -2, 20, 12), "right": (9, -2, 20, 12)}[f]
        return {"kind": kind, "rect": _at(at["rect"], x, y), "body": _at(at["body"], x, y), "stool": _at(stool, x, y),
                "mount": "floor", "stands": [(x + p[0], y + p[1]) for p in at["stands"]]}
    p = piece(item["asset"])
    if p is None:
        return None
    turned = (p.get("by_facing") or {}).get(item.get("facing", "down")) or {}   # (a library asset turned sideways)
    rect = turned.get("rect") or p["rect"]
    body = turned.get("body") or p.get("body") or rect
    return {"kind": kind, "rect": _at(rect, x, y), "body": _at(body, x, y), "mount": p.get("mount", "floor"), "stands": []}


def sign_side(item: dict) -> str:
    """Which end of a table its results sign stands past, as its players see it: props.sign, or the usual end for
    the way it's turned (the right, or the left on a quarter turn clockwise, where the right is nearest us)."""
    side = item.get("props", {}).get("sign")
    if side in SIGN_SIDES:
        return side
    game = CATALOGUE["games"].get(item["asset"][6:], {})
    return (game.get("at", {}).get(str(item.get("rot", 0))) or {}).get("sign_default", "right")


def _covers(s: dict) -> list:
    """All a thing covers: its rect, and its sign's."""
    return [s["rect"], s["sign"]["rect"]] if "sign" in s else [s["rect"]]


def _bodies(s: dict) -> list:
    """What it stands on: its body, and its sign's base."""
    return [s["body"], s["sign"]["body"]] if "sign" in s else [s["body"]]


def _solid(s: dict) -> bool:
    return s["mount"] == "floor"


def _clash(a: dict, b: dict) -> bool:
    """Two things on the floor in each other's way (with SLACK to spare). Cabinets may stand back to back and side
    by side, their tall art overlapping, so only their bases and stools count between them. Two tables mustn't share
    any of what they cover (their chairs, the dealers). Anything else is in the way only where it stands: its base
    on another's base, or on a table's or cabinet's seats -- a figure may stand behind a desk."""
    def hit(r1, r2):
        return _overlap(_grow(r1, -SLACK), r2)
    if a["kind"] == "slot" and b["kind"] == "slot":
        return hit(a["body"], b["body"]) or hit(a["stool"], b["body"]) or hit(a["body"], b["stool"]) or hit(a["stool"], b["stool"])
    if a["kind"] in ("table", "slot") and b["kind"] in ("table", "slot"):
        return any(hit(r1, r2) for r1 in _covers(a) for r2 in _covers(b))
    seats = [s for s in (a, b) if s["kind"] in ("table", "slot")]
    if seats:
        other = b if seats[0] is a else a
        return hit(seats[0]["rect"], other["body"]) or any(hit(r, other["body"]) for r in _bodies(seats[0])[1:])
    return hit(a["body"], b["body"])


# ------------------------------------------------------------------ the doors between rooms
def _edge(room: dict, side: str) -> tuple:
    """A wall's line on the plan: (axis, fixed coordinate, start, end) -- axis "h" runs along x."""
    x, y, w, h = room["x"], room["y"], room["w"], room["h"]
    return {"top": ("h", y, x, x + w), "bottom": ("h", y + h, x, x + w),
            "left": ("v", x, y, y + h), "right": ("v", x + w, y, y + h)}[side]


OPPOSITE = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}


def _door_span(room: dict, door: dict) -> tuple:
    axis, fixed, start, _ = _edge(room, door["side"])
    return axis, fixed, start + door["at"] - door["width"] / 2, start + door["at"] + door["width"] / 2


def openings(rooms: list) -> tuple[dict, list]:
    """Every room's doorways, the ones it owns and its neighbours' through its walls: {room id: [{"side", "at",
    "width", "kind", "to", "door", "owner"}]} (at: the middle, along the wall from its start), and the problems."""
    out = {r["id"]: [] for r in rooms}
    problems = []
    for room in rooms:
        for door in room["doors"]:
            axis, fixed, a, b = _door_span(room, door)
            mine = {"side": door["side"], "at": door["at"], "width": door["width"], "kind": door["kind"],
                    "to": None, "door": door["id"], "owner": room["id"]}
            for other in rooms:
                if other is room:
                    continue
                oaxis, ofixed, ostart, oend = _edge(other, OPPOSITE[door["side"]])
                if oaxis != axis or ofixed != fixed or b <= ostart or a >= oend:
                    continue
                if a < ostart or b > oend:
                    problems.append({"room": room["id"], "item": door["id"],
                                     "message": f"{room['name']}: a door half opens onto {other['name']}."})
                    continue
                theirs = next((d for d in other["doors"] if d["side"] == OPPOSITE[door["side"]]
                               and _overlap((_door_span(other, d)[2], 0, d["width"], 1), (a, 0, b - a, 1))), None)
                if theirs is not None:
                    if theirs["kind"] != door["kind"] or theirs["width"] != door["width"] \
                            or abs(_door_span(other, theirs)[2] - a) > 0.5:
                        problems.append({"room": room["id"], "item": door["id"],
                                         "message": f"{room['name']} and {other['name']} have different doors in the same place."})
                    elif room["id"] > other["id"]:
                        mine = None   # the same doorway, kept once (by the room listed first)
                        break
                mine["to"] = other["id"]
                theirs_view = dict(mine, side=OPPOSITE[door["side"]], at=(a + b) / 2 - ostart, to=room["id"])
                out[other["id"]].append(theirs_view)
                break
            if mine is not None:
                out[room["id"]].append(mine)
    return out, problems


def gap(room: dict, o: dict) -> tuple:
    """A doorway's opening on the plan, through this room's wall (the client cuts its wall bodies here)."""
    axis, fixed, start, _ = _edge(room, o["side"])
    lo = start + o["at"] - o["width"] / 2
    depth = {"top": wall_top(room), "bottom": WALL_BOTTOM, "left": WALL_SIDE, "right": WALL_SIDE}[o["side"]]
    if o["side"] == "top":
        return (lo, fixed, o["width"], depth)
    if o["side"] == "bottom":
        return (lo, fixed - depth, o["width"], depth)
    if o["side"] == "left":
        return (fixed, lo, depth, o["width"])
    return (fixed - depth, lo, depth, o["width"])


# ------------------------------------------------------------------ ids
def _serials(plan: dict) -> dict:
    """The next number for each kind of id: past every id in the plan and every one given before."""
    nxt = dict(plan.get("next") or {})
    for room in plan["rooms"]:
        for item in room["items"]:
            m = re.match(r"^([a-z]+)_?(\d+)$", item["id"])
            if m:
                nxt[m.group(1)] = max(nxt.get(m.group(1), 1), int(m.group(2)) + 1)
        for door in room["doors"]:
            m = re.match(r"^d(\d+)$", door["id"])
            if m:
                nxt["d"] = max(nxt.get("d", 1), int(m.group(1)) + 1)
    return nxt


def _new_id(nxt: dict, prefix: str) -> str:
    n = nxt.get(prefix, 1)
    nxt[prefix] = n + 1
    return f"{prefix}{n}" if prefix in (ITEM_PREFIX, "d") else f"{prefix}_{n}"


def _slug(name: str, taken: set) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:24] or "room"
    rid, n = base, 2
    while rid in taken:
        rid, n = f"{base}_{n}", n + 1
    return rid


# ------------------------------------------------------------------ cleaning what the page sends
def variant_names(builds_dir: Path | None = None) -> dict:
    """Every slot a cabinet can be: the loaded ones and any built since the server started -> its name."""
    out = {vid: v.name for vid, v in VARIANTS.items()}
    if builds_dir:
        out.update({vid: b["name"] for vid, b in slot_builds.on_disk(builds_dir).items() if vid not in out})
    return out


def _num(v, what: str, lo=-1e6, hi=1e6) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise PlanError(f"{what} isn't a number.")
    if not math.isfinite(f) or not lo <= f <= hi:
        raise PlanError(f"{what} is out of range.")
    f = round(f * 2) / 2
    return int(f) if f == int(f) else f


def _str(v, n: int) -> str:
    return " ".join(str(v or "").split())[:n]


def _colour(v, default="#ffffff") -> str:
    return v if isinstance(v, str) and COLOUR_RE.match(v) else default


def _patch(p: dict, w: float, h: float) -> dict:
    """One floor patch, checked; its look (shape, pattern, border) falls back to plain rather than failing."""
    pat = p.get("pattern") if isinstance(p.get("pattern"), dict) else {}
    bor = p.get("border") if isinstance(p.get("border"), dict) else {}
    return {"x": _num(p.get("x"), "A patch's place", 0, w), "y": _num(p.get("y"), "A patch's place", 0, h),
            "w": _num(p.get("w"), "A patch's size", 8, w), "h": _num(p.get("h"), "A patch's size", 8, h),
            "texture": str(p.get("texture") or "plain"), "tint": _colour(p.get("tint")),
            "shape": p.get("shape") if p.get("shape") in PATCH_SHAPES else "rect",
            "radius": _num(p.get("radius", 24), "A patch's corner", 0, 400),
            "pattern": {"kind": pat.get("kind") if pat.get("kind") in PATCH_PATTERNS else "none",
                        "colour": _colour(pat.get("colour"), "#000000"),
                        "size": _num(pat.get("size", 32), "A patch's pattern size", 8, 512),
                        "opacity": _num(pat.get("opacity", 30), "A patch's pattern opacity", 0, 100)},
            "border": {"style": bor.get("style") if bor.get("style") in PATCH_BORDERS else "none",
                       "colour": _colour(bor.get("colour"), "#c9a24a"),
                       "width": _num(bor.get("width", 6), "A patch's border width", 1, 64)}}


def clean(raw, old: dict) -> dict:
    """The page's plan, checked for shape and given ids (new rooms, doors and items come without them; ids already
    given stay with their thing). Raises PlanError for anything malformed; problems with where things are come from
    problems() instead, so a half-finished blueprint can still be saved."""
    if not isinstance(raw, dict) or not isinstance(raw.get("rooms"), list):
        raise PlanError("Expected {rooms: [...]}.")
    nxt = _serials(old)
    known_items = {i["id"]: i for r in old["rooms"] for i in r["items"]}
    rooms, room_ids, item_ids = [], set(), set()
    for rr in raw["rooms"]:
        if not isinstance(rr, dict):
            raise PlanError("Each room must be an object.")
        name = _str(rr.get("name"), 40) or "Room"
        rid = rr.get("id")
        if rid is None:
            rid = _slug(name, room_ids | {r["id"] for r in old["rooms"]})
        elif not isinstance(rid, str) or not ID_RE.match(rid) or rid in room_ids:
            raise PlanError(f"A room's id {rid!r} isn't usable.")
        room_ids.add(rid)
        fl = rr.get("floor") if isinstance(rr.get("floor"), dict) else {}
        walls = rr.get("walls") if isinstance(rr.get("walls"), dict) else {}
        top = WALL_SIDE if walls.get("back") == "thin" else WALL_TOP
        w = _num(rr.get("w"), f"{name}'s width", MIN_WIDTH, MAX_SIZE[0])
        h = _num(rr.get("h"), f"{name}'s height", top + WALL_BOTTOM + MIN_FLOOR, MAX_SIZE[1])
        room = {"id": rid, "name": name, "placed": bool(rr.get("placed")),
                "x": _num(rr.get("x", 0), f"{name}'s place"), "y": _num(rr.get("y", 0), f"{name}'s place"), "w": w, "h": h,
                "floor": {"texture": str(fl.get("texture") or "carpet"), "tint": _colour(fl.get("tint"))},
                "patches": [], "walls": {"style": walls.get("style") if walls.get("style") in WALL_STYLES else "crimson",
                                         "sign": _str(walls.get("sign"), 24),
                                         "sign_at": min(max(_num(walls.get("sign_at", w / 2), f"{name}'s sign"), 0), w)},
                "doors": [], "items": [], "paths": {"points": [], "zones": []}}
        if _str(rr.get("map_name"), 40):   # (these four left out otherwise, so older plans compare the same)
            room["map_name"] = _str(rr.get("map_name"), 40)
        if rr.get("npc_only"):
            room["npc_only"] = True
        if rr.get("map_hidden"):
            room["map_hidden"] = True
        if top != WALL_TOP:
            room["walls"]["back"] = "thin"
        for p in rr.get("patches") or []:
            if not isinstance(p, dict):
                raise PlanError(f"{name}: a floor patch must be an object.")
            room["patches"].append(_patch(p, w, h))
        door_ids = set()
        for d in rr.get("doors") or []:
            if not isinstance(d, dict) or d.get("side") not in SIDES or d.get("kind") not in DOOR_KINDS:
                raise PlanError(f"{name}: a door needs a side ({', '.join(SIDES)}) and a kind (door or archway).")
            length = w if d["side"] in ("top", "bottom") else h
            did = d.get("id")
            if did is None or not isinstance(did, str) or did in door_ids:
                did = _new_id(nxt, "d")
            door_ids.add(did)
            room["doors"].append({"id": did, "side": d["side"], "at": _num(d.get("at"), f"{name}: a door's place", 0, length),
                                  "width": _num(d.get("width"), f"{name}: a door's width", *DOOR_WIDTH), "kind": d["kind"]})
        for it in rr.get("items") or []:
            room["items"].append(_clean_item(it, name, w, h, nxt, known_items, item_ids))
        paths = rr.get("paths") if isinstance(rr.get("paths"), dict) else {}
        names = set()
        for p in paths.get("points") or []:
            if not isinstance(p, dict) or p.get("kind") not in POINT_KINDS:
                raise PlanError(f"{name}: a point needs a kind ({', '.join(POINT_KINDS)}).")
            pname = re.sub(r"[^a-z0-9_]+", "_", str(p.get("name") or "").lower()).strip("_")[:24] or p["kind"]
            base, n = pname, 2
            while pname in names:
                pname, n = f"{base}_{n}", n + 1
            names.add(pname)
            room["paths"]["points"].append({"name": pname, "x": _num(p.get("x"), "A point's place", 0, w),
                                            "y": _num(p.get("y"), "A point's place", 0, h), "kind": p["kind"],
                                            "weight": _num(p.get("weight", 1), "A point's weight", 0, 100),
                                            "linger": _num(p.get("linger", 0), "A point's linger", 0, 600)})
        for z in paths.get("zones") or []:
            if not isinstance(z, dict) or z.get("kind") not in ZONE_KINDS:
                raise PlanError(f"{name}: a zone needs a kind ({', '.join(ZONE_KINDS)}).")
            room["paths"]["zones"].append({"x": _num(z.get("x"), "A zone's place", 0, w), "y": _num(z.get("y"), "A zone's place", 0, h),
                                           "w": _num(z.get("w"), "A zone's size", 2, w), "h": _num(z.get("h"), "A zone's size", 2, h),
                                           "kind": z["kind"]})
        rooms.append(room)
    spawn = raw.get("spawn") if isinstance(raw.get("spawn"), str) else old.get("spawn", "")
    return {"rev": old.get("rev", 0), "next": nxt, "spawn": spawn, "rooms": rooms}


def _clean_item(it, room_name: str, w: float, h: float, nxt: dict, known: dict, taken: set) -> dict:
    if not isinstance(it, dict) or not isinstance(it.get("asset"), str) or len(it["asset"]) > 64:
        raise PlanError(f"{room_name}: each thing placed needs its asset.")
    asset = it["asset"]
    kind = asset_kind(asset)
    item = {"asset": asset, "x": _num(it.get("x"), f"{room_name}: a thing's place", -200, w + 200),
            "y": _num(it.get("y"), f"{room_name}: a thing's place", -200, h + 200), "props": {}}
    props = it.get("props") if isinstance(it.get("props"), dict) else {}
    if kind == "table":
        game = asset[6:]
        if game not in PREFIX:
            raise PlanError(f"There's no table game {game!r}.")
        rots = CATALOGUE["games"][game]["rotations"]
        rot = int(_num(it.get("rot", 0), "A table's turn", 0, 359))
        item["rot"] = rot if rot in rots else rots[0]
        item["props"]["label"] = _str(props.get("label"), 32) or CATALOGUE["games"][game]["name"]
        if "sign" in CATALOGUE["games"][game]["at"]["0"] and props.get("sign") in SIGN_SIDES:
            item["props"]["sign"] = props["sign"]
        if game == master.GAME_KEY:   # how it changes game: its animation, and how fast
            item["props"]["anim"] = props.get("anim") if props.get("anim") in master.ANIMS else master.DEFAULT_ANIM
            speed = props.get("speed")
            item["props"]["speed"] = float(speed) if isinstance(speed, (int, float)) and float(speed) in master.SPEEDS else master.DEFAULT_SPEED
        prefix = PREFIX[game]
    else:
        item["facing"] = it.get("facing") if it.get("facing") in FACINGS else "down"
        if kind == "slot":
            if not isinstance(props.get("variant"), str):
                raise PlanError(f"{room_name}: a slot cabinet needs its slot.")
            item["props"]["variant"] = props["variant"]
            prefix = SLOT_PREFIX
        else:
            if asset == "npc":
                item["props"] = {"look": _str(props.get("look"), 64) or "dealer", "name": _str(props.get("name"), 24)}
            prefix = ITEM_PREFIX
    iid = it.get("id")
    old = known.get(iid) if isinstance(iid, str) else None
    if iid is None or old is None or old["asset"] != asset or iid in taken:
        # New (or a table turned into another game, which is a new table): a fresh id.
        iid = _new_id(nxt, prefix)
    taken.add(iid)
    return {"id": iid, **item}


# ------------------------------------------------------------------ problems
def problems(plan: dict, builds_dir: Path | None = None) -> list[dict]:
    """Everything wrong with where things are: [{"room", "item" (or None), "message", "placed"}]. A blueprint can
    be saved with problems; the floor can't be published with any in its placed rooms."""
    out = []
    variants = variant_names(builds_dir)
    placed = [r for r in plan["rooms"] if r["placed"]]
    for room in plan["rooms"]:
        out += [dict(p, placed=room["placed"]) for p in _room_problems(room, variants)]
    for i, a in enumerate(placed):
        for b in placed[i + 1:]:
            if _overlap(outline(a), outline(b)):
                out.append({"room": a["id"], "item": None, "placed": True, "message": f"{a['name']} overlaps {b['name']} on the plan."})
    ops, door_problems = openings(placed)
    out += [dict(p, placed=True) for p in door_problems]
    spawn = plan.get("spawn", "")
    spawns = {f"{r['id']}/{p['name']}": p for r in placed if not r.get("npc_only")
              for p in r["paths"]["points"] if p["kind"] == "spawn"}
    if spawn not in spawns:
        out.append({"room": None, "item": None, "placed": True,
                    "message": "Players have nowhere to appear: give a placed room a spawn point." if not spawns
                    else "Players can't appear in an NPCs-only room: pick another spawn point."
                    if spawn.split("/", 1)[0] in {r["id"] for r in placed if r.get("npc_only")}
                    else "Pick which spawn point players appear at."})
    if not placed:
        return out
    out += [dict(p, placed=True) for p in _reach_problems(placed, ops, spawns.get(spawn) and spawn)]
    return out


def _room_problems(room: dict, variants: dict) -> list[dict]:
    out = []
    inner = interior(room)
    name = room["name"]
    every = []
    for item in room["items"]:
        s = shapes(room, item)
        label = _label(item)
        if s is None:
            out.append({"room": room["id"], "item": item["id"], "message": f"{name}: {label} isn't in the library any more."})
            continue
        if item["asset"] == "slot" and item["props"].get("variant") not in variants:
            out.append({"room": room["id"], "item": item["id"], "message": f"{name}: there's no slot {item['props'].get('variant')!r} for {item['id']}."})
        if s["mount"] == "wall":
            if not _contains(outline(room), s["rect"]) or s["rect"][1] + s["rect"][3] > room["y"] + wall_top(room) + 4:
                out.append({"room": room["id"], "item": item["id"], "message": f"{name}: {label} belongs on the back wall."})
            continue
        if not all(_contains(inner, b) for b in _bodies(s)) or not all(_contains(outline(room), r) for r in _covers(s)):
            out.append({"room": room["id"], "item": item["id"], "message": f"{name}: {label} is off the floor."})
            continue
        if any(not _inside(p, inner) for p in s["stands"]):
            out.append({"room": room["id"], "item": item["id"], "message": f"{name}: {label}'s players would stand in the wall."})
            continue
        every.append((item, s))
    floor_things = [(i, s) for i, s in every if _solid(s)]
    for n, (item, s) in enumerate(floor_things):
        for other, s2 in floor_things[n + 1:]:
            if _clash(s, s2):
                out.append({"room": room["id"], "item": item["id"], "message": f"{name}: {_label(item)} overlaps {_label(other)}."})
                break
        else:
            for other, s2 in floor_things:
                if other is not item and any(_inside(p, b) for p in s["stands"] for b in _bodies(s2)):
                    out.append({"room": room["id"], "item": item["id"],
                                "message": f"{name}: {_label(other)} stands where {_label(item)}'s players would."})
                    break
    for p in room["paths"]["points"]:
        at = (room["x"] + p["x"], room["y"] + p["y"])
        if not _inside(at, _grow(inner, -AGENT)):
            out.append({"room": room["id"], "item": "point:" + p["name"], "message": f"{name}: the point {p['name']} is in the wall."})
        elif any(_inside(at, _grow(b, AGENT)) for _, s in floor_things for b in _bodies(s)):
            out.append({"room": room["id"], "item": "point:" + p["name"], "message": f"{name}: something stands on the point {p['name']}."})
    for d in room["doors"]:
        lo, hi = d["at"] - d["width"] / 2, d["at"] + d["width"] / 2
        if d["side"] in ("top", "bottom"):
            into_corner = lo < WALL_SIDE or hi > room["w"] - WALL_SIDE
        else:
            into_corner = lo < wall_top(room) or hi > room["h"] - WALL_BOTTOM
        if into_corner:
            out.append({"room": room["id"], "item": d["id"], "message": f"{name}: a door runs into the corner."})
    return out


def _label(item: dict) -> str:
    kind = asset_kind(item["asset"])
    if kind == "table":
        return f"{item['props'].get('label') or item['asset'][6:]} ({item['id']})"
    if kind == "slot":
        return f"the slot cabinet {item['id']}"
    p = piece(item["asset"])
    if item["asset"] == "npc" and item["props"].get("name"):
        return item["props"]["name"]
    return f"the {(p or {}).get('name', item['asset']).lower()}"


def _reach_problems(rooms: list, ops: dict, spawn: str | None) -> list[dict]:
    """Seats and points nobody can walk to: a flood fill over the placed rooms (players from the spawn point, NPCs
    from where they come in -- NPCs also keep out of npc_block zones)."""
    by_id = {r["id"]: r for r in rooms}
    x0 = min(r["x"] for r in rooms)
    y0 = min(r["y"] for r in rooms)
    x1 = max(r["x"] + r["w"] for r in rooms)
    y1 = max(r["y"] + r["h"] for r in rooms)
    cols, rows = int((x1 - x0) // CELL) + 1, int((y1 - y0) // CELL) + 1
    if cols * rows > 4_000_000:
        return []

    def cell(p):
        return int((p[0] - x0) // CELL), int((p[1] - y0) // CELL)

    open_cells = bytearray(cols * rows)

    def mark(r, value, shrink=0):
        r = _grow(r, -shrink)
        cx0, cy0 = max(0, int((r[0] - x0) // CELL)), max(0, int((r[1] - y0) // CELL))
        cx1, cy1 = min(cols - 1, int((r[0] + r[2] - x0) // CELL)), min(rows - 1, int((r[1] + r[3] - y0) // CELL))
        for cy in range(cy0, cy1 + 1):
            for cx in range(cx0, cx1 + 1):
                centre = (x0 + cx * CELL + CELL / 2, y0 + cy * CELL + CELL / 2)
                if _inside(centre, r):
                    open_cells[cy * cols + cx] = value

    for r in rooms:
        mark(interior(r), 1, AGENT - 4)
    for rid, os_ in ops.items():
        for o in os_:
            if o["to"] is not None:   # through the wall, and a little into the room either side
                g = gap(by_id[rid], o)
                mark((g[0] + 4, g[1] - 12, g[2] - 8, g[3] + 24) if o["side"] in ("top", "bottom")
                     else (g[0] - 12, g[1] + 4, g[2] + 24, g[3] - 8), 1)
    things = []
    for r in rooms:
        for item in r["items"]:
            s = shapes(r, item)
            if s is not None and _solid(s):
                for b in _bodies(s):
                    mark(b, 0, -(AGENT - 4))
                things.append((r, item, s))
        for z in r["paths"]["zones"]:
            if z["kind"] == "block":
                mark((r["x"] + z["x"], r["y"] + z["y"], z["w"], z["h"]), 0, -(AGENT - 4))
    def shut(grid, zr):   # every cell the rect touches
        cx0, cy0 = max(0, int((zr[0] - x0) // CELL)), max(0, int((zr[1] - y0) // CELL))
        cx1, cy1 = min(cols - 1, int((zr[0] + zr[2] - x0) // CELL)), min(rows - 1, int((zr[1] + zr[3] - y0) // CELL))
        for cy in range(cy0, cy1 + 1):
            for cx in range(cx0, cx1 + 1):
                grid[cy * cols + cx] = 0

    npc_cells = bytearray(open_cells)
    for r in rooms:
        for z in r["paths"]["zones"]:
            if z["kind"] == "npc_block":
                shut(npc_cells, _grow((r["x"] + z["x"], r["y"] + z["y"], z["w"], z["h"]), AGENT - 4))
        if r.get("npc_only"):   # players stop at its doorways
            shut(open_cells, outline(r))

    def fill(grid, starts):
        seen = bytearray(cols * rows)
        stack = []
        for p in starts:
            c = _nearest_open(grid, cols, rows, *cell(p))
            if c is not None and not seen[c]:
                seen[c] = 1
                stack.append(c)
        while stack:
            c = stack.pop()
            cx, cy = c % cols, c // cols
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if 0 <= nx < cols and 0 <= ny < rows:
                    n = ny * cols + nx
                    if grid[n] and not seen[n]:
                        seen[n] = 1
                        stack.append(n)
        return seen

    def reached(seen, grid, p) -> bool:
        c = _nearest_open(grid, cols, rows, *cell(p))
        return c is not None and bool(seen[c])

    out = []
    points = [(r, p, (r["x"] + p["x"], r["y"] + p["y"])) for r in rooms for p in r["paths"]["points"]]
    if spawn:
        sr, sp = spawn.split("/", 1)
        start = next(((r["x"] + p["x"], r["y"] + p["y"]) for r in rooms if r["id"] == sr for p in r["paths"]["points"] if p["name"] == sp), None)
        players = fill(open_cells, [start]) if start else None
        if players is not None:
            for r, item, s in things:
                if s["stands"] and not any(reached(players, open_cells, p) for p in s["stands"]):
                    out.append({"room": r["id"], "item": item["id"], "message": f"{r['name']}: players can't reach {_label(item)}."})
            for r, p, at in points:
                if p["kind"] != "spawn" and not r.get("npc_only") and not reached(players, open_cells, at):
                    out.append({"room": r["id"], "item": "point:" + p["name"], "message": f"{r['name']}: players can't reach the point {p['name']}."})
    arrivals = [at for r, p, at in points if p["kind"] == "arrival"]
    if arrivals:
        npcs = fill(npc_cells, arrivals)
        for r, item, s in things:
            if s["stands"] and not any(reached(npcs, npc_cells, p) for p in s["stands"]):
                out.append({"room": r["id"], "item": item["id"], "message": f"{r['name']}: NPCs can't reach {_label(item)}."})
        for r, p, at in points:
            if p["kind"] == "wander" and not reached(npcs, npc_cells, at):
                out.append({"room": r["id"], "item": "point:" + p["name"], "message": f"{r['name']}: NPCs can't reach the point {p['name']}."})
    elif any(s["stands"] for _, _, s in things):
        out.append({"room": None, "item": None, "message": "NPCs have nowhere to come in: give a placed room an arrival point."})
    return out


def _nearest_open(grid, cols: int, rows: int, cx: int, cy: int):
    """The open cell at or next to (cx, cy) (a point right by a wall or a table still counts), or None."""
    for r in range(0, 3):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < cols and 0 <= y < rows and grid[y * cols + x]:
                    return y * cols + x
    return None


# ------------------------------------------------------------------ the floor (install) and what clients get
def tables_of(plan: dict, placed_only: bool = True) -> dict:
    """The tables and cabinets in a plan's rooms: table id -> its floor.TABLES entry (plus "room")."""
    out = {}
    for room in plan["rooms"]:
        if placed_only and not room["placed"]:
            continue
        for item in room["items"]:
            kind = asset_kind(item["asset"])
            if kind == "table":
                game = item["asset"][6:]
                if game in CATALOGUE["games"]:
                    out[item["id"]] = {"game": game, "name": item["props"].get("label") or CATALOGUE["games"][game]["name"],
                                       "seats": CATALOGUE["games"][game]["seats"], "room": room["id"]}
                    if game == master.GAME_KEY:   # (and the seat points of both its tables: six seats and five)
                        out[item["id"]].update(anim=item["props"].get("anim", master.DEFAULT_ANIM),
                                               speed=item["props"].get("speed", master.DEFAULT_SPEED),
                                               stands=master_stands(room, item))
            elif kind == "slot":
                v = VARIANTS.get(item["props"].get("variant"))
                if v is not None:
                    out[item["id"]] = {"game": "slots", "variant": v.id, "name": v.name, "seats": 1, "room": room["id"]}
    return out


def install(plan: dict) -> list[str]:
    """Put a plan's placed rooms on the floor (see the module docstring). Returns the table ids."""
    placed = [r for r in plan["rooms"] if r["placed"]]
    tables = tables_of(plan)
    floor.TABLES.clear()
    floor.TABLES.update({tid: {k: v for k, v in cfg.items() if k != "room"} for tid, cfg in tables.items()})
    floor.POINTS.clear()
    floor.SEATS.clear()
    for room in placed:
        for p in room["paths"]["points"]:
            floor.POINTS[f"{room['id']}/{p['name']}"] = {"x": room["x"] + p["x"], "y": room["y"] + p["y"], "kind": p["kind"],
                                                         "weight": p["weight"], "linger": p["linger"], "room": room["id"]}
        for item in room["items"]:
            if item["id"] in tables:
                s = shapes(room, item)
                floor.SEATS[item["id"]] = s["stands"] if s else []
    npc_only = {r["id"] for r in placed if r.get("npc_only")}
    spawns = [k for k, p in floor.POINTS.items() if p["kind"] == "spawn" and p["room"] not in npc_only]
    floor.SPAWN = plan.get("spawn") if plan.get("spawn") in spawns else (spawns[0] if spawns else "")
    ops, _ = openings(placed)
    floor.ROUTES = Routes(placed, ops)
    _LIVE.clear()
    _LIVE.update(plan=copy.deepcopy(plan), tables=sorted(tables))
    sounds.refresh_sets()
    return sorted(tables)


def live() -> dict:
    """The plan install() put on the floor."""
    return _LIVE.get("plan") or {"rev": 0, "rooms": [], "spawn": ""}


def cabinets_on_floor(variant: str) -> int:
    return sum(1 for cfg in floor.TABLES.values() if cfg.get("variant") == variant)


def every_table() -> dict:
    """Every table id in the live and draft plans, placed or in the library (so settings kept by table id --
    a table's style -- outlive a room being taken off the floor): id -> {"game", "name"}."""
    out = tables_of(live(), placed_only=False)
    out.update({k: v for k, v in _DRAFT_TABLES.items() if k not in out})
    return out


_DRAFT_TABLES: dict = {}


def world(plan: dict, rooms: list | None = None, start: tuple | None = None) -> dict:
    """What a client builds the floor from (the welcome's and the `world` broadcast's `world`): the placed rooms, or
    `rooms` (a preview), with their doorways worked out and each cabinet's look."""
    shown = rooms if rooms is not None else [r for r in plan["rooms"] if r["placed"]]
    ops, _ = openings(shown)
    out_rooms = []
    for room in shown:
        items = []
        for item in room["items"]:
            it = copy.deepcopy(item)
            kind = asset_kind(item["asset"])
            if kind == "table":
                game = item["asset"][6:]
                cat = CATALOGUE["games"].get(game)
                if cat is None:
                    continue
                it.update(game=game, name=item["props"].get("label") or cat["name"], seats=cat["seats"])
            elif kind == "slot":
                v = item["props"].get("variant")
                if v not in VARIANTS:
                    continue
                it.update(name=VARIANTS[v].name, cabinet=slot_builds.BUILT.get(v, {}).get("theme", {}).get("cabinet", {}))
            elif piece(item["asset"]) is None:
                continue
            items.append(it)
        out_rooms.append({k: room[k] for k in ("id", "x", "y", "w", "h", "floor", "patches", "walls")}
                         | {"name": room.get("map_name") or room["name"], "npc_only": bool(room.get("npc_only")),
                            "map_hidden": bool(room.get("map_hidden")), "openings": ops.get(room["id"], []), "items": items,
                            "points": room["paths"]["points"], "zones": room["paths"]["zones"]})
    out = {"rev": plan.get("rev", 0), "spawn": plan.get("spawn", ""), "rooms": out_rooms,
           "walls": {"top": WALL_TOP, "side": WALL_SIDE, "bottom": WALL_BOTTOM}, "styles": WALL_STYLES}
    if start is not None:
        out["start"] = {"x": start[0], "y": start[1]}
    return out


def preview_world(draft: dict, room_id: str) -> dict:
    """A preview of the draft: its placed rooms, or just the one blueprint if it isn't placed, starting in that
    room (at its spawn point, else an arrival point, else its middle)."""
    room = next((r for r in draft["rooms"] if r["id"] == room_id), None)
    if room is None:
        raise PlanError(f"There's no room {room_id!r} in the draft.")
    rooms = [r for r in draft["rooms"] if r["placed"]] if room["placed"] else [room]
    pts = sorted(room["paths"]["points"], key=lambda p: POINT_KINDS.index(p["kind"]))
    start = ((room["x"] + pts[0]["x"], room["y"] + pts[0]["y"]) if pts
             else (room["x"] + room["w"] / 2, room["y"] + (room["h"] + wall_top(room)) / 2))
    return world(draft, rooms, start)


# ------------------------------------------------------------------ NPC routes
class Routes:
    """How far an NPC walks between two places on the floor: straight across a room (a little more, for going round
    things), or room to room through the doorways."""

    def __init__(self, rooms: list, ops: dict):
        self.rooms = rooms
        self.doors = []   # (x, y, room a, room b)
        by_id = {r["id"]: r for r in rooms}
        for rid, os_ in ops.items():
            for o in os_:
                if o["to"] is not None and o["owner"] == rid:
                    g = gap(by_id[rid], o)
                    self.doors.append((g[0] + g[2] / 2, g[1] + g[3] / 2, rid, o["to"]))

    def room_at(self, p) -> str | None:
        for r in self.rooms:
            if _inside(p, outline(r)):
                return r["id"]
        return None

    def distance(self, a, b) -> float:
        ra, rb = self.room_at(a), self.room_at(b)
        straight = math.dist(a, b) * DETOUR
        if ra is None or rb is None or ra == rb:
            return straight
        # Dijkstra over the doorways: a node is a doorway, an edge a walk across the room the two share.
        best = {}
        heap = []
        for i, d in enumerate(self.doors):
            if ra in (d[2], d[3]):
                heapq.heappush(heap, (math.dist(a, d[:2]) * DETOUR, i))
        while heap:
            cost, i = heapq.heappop(heap)
            if i in best:
                continue
            best[i] = cost
            d = self.doors[i]
            if rb in (d[2], d[3]):
                return cost + math.dist(d[:2], b) * DETOUR
            for j, e in enumerate(self.doors):
                if j not in best and ({d[2], d[3]} & {e[2], e[3]}):
                    heapq.heappush(heap, (cost + math.dist(d[:2], e[:2]) * DETOUR, j))
        return straight


# ------------------------------------------------------------------ the page
class PlanBoard:
    """The admin page's Floor plan tab: the draft, its problems, publishing, history. `on_draft(plan)` and
    `on_publish(plan)` let the app tell previews and players."""

    def __init__(self, data_dir: Path, builds_dir: Path | None = None):
        self.data_dir, self.builds_dir = data_dir, builds_dir
        self.dir = plan_dir(data_dir)
        self.on_draft = None
        self.on_publish = None
        self._note_draft(load_draft(data_dir))

    def _note_draft(self, draft: dict):
        _DRAFT_TABLES.clear()
        _DRAFT_TABLES.update({k: v for k, v in tables_of(draft, placed_only=False).items()})

    def draft(self) -> dict:
        return load_draft(self.data_dir)

    def view(self) -> dict:
        draft = self.draft()
        live_plan = load_live(self.data_dir)
        probs = problems(draft, self.builds_dir)
        return {"draft": draft, "problems": probs, "live_rev": live_plan.get("rev", 0),
                "pending": self.changes(draft, live_plan), "restart": self.needs_restart(draft, live()),
                "can_publish": not any(p["placed"] for p in probs), "live": slot_builds.is_live()}

    @staticmethod
    def changes(draft: dict, live_plan: dict) -> list[str]:
        """The rooms that differ between the draft and the live floor (by name)."""
        def placed(p):
            return {r["id"]: r for r in p["rooms"] if r["placed"]}
        a, b = placed(draft), placed(live_plan)
        out = [a[k]["name"] if k in a else b[k]["name"] for k in sorted(a.keys() | b.keys()) if _canon(a.get(k)) != _canon(b.get(k))]
        if draft.get("spawn") != live_plan.get("spawn"):
            out.append("where players appear")
        return out

    @staticmethod
    def needs_restart(draft: dict, live_plan: dict) -> bool:
        """Publishing this would add or take away tables or cabinets (or change what they are): the casino restarts."""
        def games(p):   # (a cabinet of a slot built since the server started counts: the restart loads it)
            return {i["id"]: (i["asset"], i["props"].get("variant")) for r in p["rooms"] if r["placed"]
                    for i in r["items"] if asset_kind(i["asset"]) in ("table", "slot")}
        return games(draft) != games(live_plan)

    def save(self, raw, base_rev=None) -> dict:
        old = self.draft()
        if base_rev is not None and base_rev != old.get("rev"):
            raise PlanConflict("The plan was changed in another tab: reload it to see the changes.")
        plan = clean(raw, old)
        plan["rev"] = old.get("rev", 0) + 1
        _write(self.dir / "draft.json", plan)
        self._note_draft(plan)
        if self.on_draft:
            self.on_draft(plan)
        return self.view()

    def publish(self) -> dict:
        draft = self.draft()
        probs = [p for p in problems(draft, self.builds_dir) if p["placed"]]
        if probs:
            raise PlanError(probs[0]["message"] + (f" (and {len(probs) - 1} more)" if len(probs) > 1 else ""))
        restart = self.needs_restart(draft, live())
        old = load_live(self.data_dir)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        _write(self.dir / "history" / f"{stamp}-r{old.get('rev', 0)}.json", old)
        for stale in sorted((self.dir / "history").glob("*.json"))[:-HISTORY]:
            stale.unlink(missing_ok=True)
        _write(self.dir / "live.json", draft)
        message = "Published."
        if restart:
            if slot_builds.is_live():
                try:
                    slot_builds.restart_live("plan")
                except (OSError, subprocess.SubprocessError) as e:
                    raise PlanError(f"Published, but couldn't restart the casino: {e}")
                message = "Published: the casino restarts in a moment (games reconnect by themselves) with the new tables."
            else:
                message = "Published. This is a test or dev instance: restart it to put the new tables on its floor."
        else:
            install(draft)
            if self.on_publish:
                self.on_publish(draft)
            message = "Published: the floor has changed."
        return {"message": message, "restart": restart, **self.view()}

    def discard(self) -> dict:
        live_plan = load_live(self.data_dir)
        old = self.draft()
        draft = copy.deepcopy(live_plan)
        draft["rev"] = old.get("rev", 0) + 1
        draft["next"] = _merge_next(old, draft)
        _write(self.dir / "draft.json", draft)
        self._note_draft(draft)
        if self.on_draft:
            self.on_draft(draft)
        return self.view()

    def history(self) -> list[dict]:
        out = []
        for path in sorted((self.dir / "history").glob("*.json"), reverse=True):
            p = _read(path)
            if p is not None:
                out.append({"id": path.stem, "rooms": [r["name"] for r in p["rooms"] if r["placed"]],
                            "tables": len(tables_of(p))})
        return out

    def rollback(self, hid: str) -> dict:
        """Put an old publish back in the draft (publishing it is up to the page)."""
        if not re.match(r"^[0-9-]+-r\d+$", hid):
            raise PlanError("No such publish.")
        old = _read(self.dir / "history" / f"{hid}.json")
        if old is None:
            raise PlanError("No such publish.")
        draft = self.draft()
        old["rev"] = draft.get("rev", 0) + 1
        old["next"] = _merge_next(draft, old)
        _write(self.dir / "draft.json", old)
        self._note_draft(old)
        if self.on_draft:
            self.on_draft(old)
        return self.view()


def _canon(v) -> str:
    """A room as text to compare by (322 and 322.0 are the same place)."""
    def ints(x):
        if isinstance(x, float) and x == int(x):
            return int(x)
        if isinstance(x, dict):
            return {k: ints(y) for k, y in x.items()}
        if isinstance(x, list):
            return [ints(y) for y in x]
        return x
    return json.dumps(ints(v), sort_keys=True)


def _merge_next(a: dict, b: dict) -> dict:
    """Both plans' id serials, the higher of each (so going back to an older plan never gives an id out again)."""
    na, nb = _serials(a), _serials(b)
    return {k: max(na.get(k, 1), nb.get(k, 1)) for k in na.keys() | nb.keys()}


class PlanConflict(PlanError):
    """Saved over a newer draft (another tab)."""


def catalogue(builds_dir: Path | None = None) -> dict:
    """What the page can place, and how things look: games, the cabinet, pieces, library assets, walls, floors, slots."""
    return {"games": {g: {**c, "prefix": PREFIX[g]} for g, c in CATALOGUE["games"].items()},
            "cabinet": CATALOGUE["cabinet"], "pieces": PIECES, "assets": ASSETS,
            "walls": {"top": WALL_TOP, "side": WALL_SIDE, "bottom": WALL_BOTTOM, "styles": WALL_STYLES},
            "floors": FLOORS, "slots": variant_names(builds_dir), "facings": FACINGS,
            "slot_looks": {vid: b.get("theme", {}).get("cabinet", {}) for vid, b in slot_builds.BUILT.items()},
            "min_width": MIN_WIDTH, "min_floor": MIN_FLOOR, "point_kinds": POINT_KINDS, "zone_kinds": ZONE_KINDS, "door_kinds": DOOR_KINDS,
            "patch_shapes": PATCH_SHAPES, "patch_patterns": PATCH_PATTERNS, "patch_borders": PATCH_BORDERS,
            "categories": ["Seating", "Tables & desks", "Bar & counters", "Plants", "Lighting", "Statues & fountains",
                           "Decor", "Rugs", "Wall decor", "Uploads"]}
