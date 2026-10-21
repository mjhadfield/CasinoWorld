"""
The casino floor as the server sees it: the tables, the named points NPCs walk between, where each seat's player
stands and how far it is between places. All of it comes from the live floor plan (plan.install fills it in at
startup and on a publish); the client builds the same floor from the plan the welcome sends.
"""

import json
from pathlib import Path

# Every table game there is (its name), on the floor or not: from the plan's catalogue (tools/plan_catalogue.gd).
GAMES = {g: c["name"] for g, c in json.loads((Path(__file__).resolve().parent / "plan_catalogue.json").read_text())["games"].items()}

TABLES: dict = {}    # table id -> {"game", "name", "seats"} (slot cabinets: "variant" too, one seat each)
SLOTS_FOR_HUMANS = 2   # NPCs leave at least this many slot cabinets free

POINTS: dict = {}    # "room/name" -> {"x", "y", "kind": spawn|arrival|wander, "weight", "linger", "room"}
SEATS: dict = {}     # table id -> [(x, y) where each seat's player stands to sit down]
SPAWN = ""           # the point players appear at
ROUTES = None        # plan.Routes: walking distances through the doorways


def arrivals() -> list[str]:
    """Where NPCs come in (and go out)."""
    return [k for k, p in POINTS.items() if p["kind"] == "arrival"]


def wander_points() -> list[str]:
    return [k for k, p in POINTS.items() if p["kind"] == "wander"]


def position(target: str) -> tuple | None:
    """A walk target's place on the floor: "point:<room>/<name>" or "seat:<table>:<seat>"."""
    if target.startswith("point:"):
        p = POINTS.get(target[6:])
        return (p["x"], p["y"]) if p else None
    if target.startswith("seat:"):
        _, table, seat = target.rsplit(":", 2) if target.count(":") >= 2 else (None, None, None)
        stands = SEATS.get(table or "")
        try:
            return tuple(stands[int(seat)]) if stands else None
        except (IndexError, ValueError):
            return None
    return None


def distance(a: tuple | None, b: tuple | None) -> float | None:
    if a is None or b is None or ROUTES is None:
        return None
    return ROUTES.distance(a, b)
