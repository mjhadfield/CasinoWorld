"""
A casino floor as the server sees it: the tables, the named points NPCs walk between, where each seat's player
stands and how far it is between places. All of it comes from a live floor plan (plan.install makes a Floor at
startup and on a publish; each Casino has its own); the client builds the same floor from the plan the welcome sends.
"""

import json
from pathlib import Path

# Every table game there is (its name), on the floor or not: from the plan's catalogue (tools/plan_catalogue.gd).
GAMES = {g: c["name"] for g, c in json.loads((Path(__file__).resolve().parent / "plan_catalogue.json").read_text())["games"].items()}

SLOTS_FOR_HUMANS = 2   # NPCs leave at least this many slot cabinets free


class Floor:
    def __init__(self, plan: dict | None = None, tables: dict | None = None, points: dict | None = None,
                 seats: dict | None = None, spawn: str = "", routes=None, sound_sets: dict | None = None):
        self.plan = plan or {"rev": 0, "rooms": [], "spawn": ""}   # the live plan it was made from
        self.tables = tables or {}   # table id -> {"game", "name", "seats"} (slot cabinets: "variant" too, one seat each)
        self.points = points or {}   # "room/name" -> {"x", "y", "kind": spawn|arrival|wander, "weight", "linger", "room"}
        self.seats = seats or {}     # table id -> [(x, y) where each seat's player stands to sit down]
        self.spawn = spawn           # the point players appear at
        self.routes = routes         # plan.Routes: walking distances through the doorways
        self.sound_sets = sound_sets or {}   # table id -> the sound set it plays from (sounds.table_sets)

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
