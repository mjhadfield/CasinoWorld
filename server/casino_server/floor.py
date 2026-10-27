"""
A casino floor as the server sees it: the tables, the named points NPCs walk between, where each seat's player
stands, how far it is between places, and which tables can be seen from each room. All of it comes from a live floor plan (plan.install makes a Floor at
startup and on a publish; each Casino has its own); the client builds the same floor from the plan the welcome sends.
"""

import json
from pathlib import Path

# Every table game there is (its name), on the floor or not: from the plan's catalogue (tools/plan_catalogue.gd).
GAMES = {g: c["name"] for g, c in json.loads((Path(__file__).resolve().parent / "plan_catalogue.json").read_text())["games"].items()}

SLOTS_FOR_HUMANS = 2   # NPCs leave at least this many slot cabinets free

# A player is sent the tables near them (tables_near): within this far either way (x, y) of where they are. The camera
# shows about 420×285 either way walking (1280×720 stretched to the window, at zoom 2), so a table comes in some 4s'
# walk (105 px/s) before it's on screen. One already sent stays until it's KEEP further out, so walking along the
# edge doesn't send it again and again.
VIEW = (900, 700)
KEEP = 200


class Floor:
    def __init__(self, plan: dict | None = None, tables: dict | None = None, points: dict | None = None,
                 seats: dict | None = None, spawn: str = "", routes=None, sound_sets: dict | None = None,
                 rooms: dict | None = None, near: dict | None = None, at: dict | None = None):
        self.plan = plan or {"rev": 0, "rooms": [], "spawn": ""}   # the live plan it was made from
        self.tables = tables or {}   # table id -> {"game", "name", "seats"} (slot cabinets: "variant" too, one seat each)
        self.points = points or {}   # "room/name" -> {"x", "y", "kind": spawn|arrival|wander, "weight", "linger", "room"}
        self.seats = seats or {}     # table id -> [(x, y) where each seat's player stands to sit down]
        self.spawn = spawn           # the point players appear at
        self.routes = routes         # plan.Routes: walking distances through the doorways
        self.sound_sets = sound_sets or {}   # table id -> the sound set it plays from (sounds.table_sets)
        self.rooms = rooms or {}     # room id -> (x, y, w, h), the placed rooms
        self.near = near or {}       # room id -> the tables in the rooms a player there can see (plan.near_tables)
        self.at = at or {}           # table id -> where it stands

    def room_at(self, x: float, y: float) -> str | None:
        for room_id, (rx, ry, rw, rh) in self.rooms.items():
            if rx <= x < rx + rw and ry <= y < ry + rh:
                return room_id
        return None

    def tables_near(self, room: str | None, at: tuple | None = None, sent: frozenset = frozenset()) -> frozenset:
        """The tables someone in `room` at `at` is sent (already `sent` some): those in the rooms they can see and
        near them (VIEW, KEEP). Every table if the floor has no rooms or `room` isn't one of them."""
        near = self.near.get(room)
        if near is None:
            near = frozenset(self.tables)
        if at is None:
            return near
        out = set()
        for table_id in near:
            p = self.at.get(table_id)
            extra = KEEP if table_id in sent else 0
            if p is None or (abs(p[0] - at[0]) <= VIEW[0] + extra and abs(p[1] - at[1]) <= VIEW[1] + extra):
                out.add(table_id)
        return frozenset(out)

    def arrivals(self) -> list[str]:
        """Where NPCs come in (and go out)."""
        return [k for k, p in self.points.items() if p["kind"] == "arrival"]

    def wander_points(self) -> list[str]:
        return [k for k, p in self.points.items() if p["kind"] == "wander"]

    def position(self, target: str) -> tuple | None:
        """A walk target's place on the floor: "point:<room>/<name>" or "seat:<table>:<seat>"."""
        if target.startswith("point:"):
            p = self.points.get(target[6:])
            return (p["x"], p["y"]) if p else None
        if target.startswith("seat:"):
            _, table, seat = target.rsplit(":", 2) if target.count(":") >= 2 else (None, None, None)
            stands = self.seats.get(table or "")
            try:
                return tuple(stands[int(seat)]) if stands else None
            except (IndexError, ValueError):
                return None
        return None

    def distance(self, a: tuple | None, b: tuple | None) -> float | None:
        if a is None or b is None or self.routes is None:
            return None
        return self.routes.distance(a, b)

    def cabinets(self, variant: str) -> int:
        """How many of a slot's cabinets are on this floor."""
        return sum(1 for cfg in self.tables.values() if cfg.get("variant") == variant)
