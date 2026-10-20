"""
Slots built with the Slot design wizard (its Build step), joining the casino when the server starts.

Each built slot is a folder under server/slot_builds/<id>/ (CASINO_SLOT_BUILDS_DIR moves it, for tests and the
dev instance):
  variant.json   the variant (slots/variant.py from_json), its theme, its floor spot and its sounds
  art/<id>.png   every picture the game draws for it: the tiers (W, H1.., BS, FS), the feature and bonus art,
                 the logo and the background (bg)
  fonts/         its display and interface fonts
  IDEAS.md       feature or bonus ideas the design described that still need building in code

install() runs in the app's lifespan, before the casino and the sound board start: it registers the variants
(slots/variants VARIANTS), puts their cabinets on the floor (floor.TABLES, a bank shape on a named spot) and gives each its sound set (sounds.py). Everything it adds is removed first, so it can run
again (tests do, with their own folder).
"""
from pathlib import Path

from casino_server import floor, sounds
from casino_server.slots.variant import from_json
from casino_server.slots.variants import VARIANTS

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "slot_builds"

# Where a new bank can go (clear floor, measured from the room's tables), as the centre of the bank.
SPOTS = {
    "above_armadillo": {"label": "Above Armadillo's bank, below the craps table", "centre": (1650, 810)},
    "west_of_armadillo": {"label": "West of Armadillo's bank, by the bottom-right card table", "centre": (1430, 960)},
}
# The bank shapes the Build step offers, as (dx, dy, facing) from the spot's centre; facing is where a screen
# faces, and its player sits on that side. Single, Double and Quad are one row facing the camera (seats on the
# near side); Full is the Armadillo bank's pattern (its centre 1650, 960): four facing up, four down, one at each end.
ROW = [(-51, 0, "down"), (-17, 0, "down"), (17, 0, "down"), (51, 0, "down")]
BANKS = {
    "single": {"label": "Single", "cabinets": [(0, 0, "down")]},
    "double": {"label": "Double", "cabinets": ROW[1:3]},
    "quad": {"label": "Quad", "cabinets": ROW},
    "full": {"label": "Full bank", "cabinets": [(-51, -13, "up"), (-17, -13, "up"), (17, -13, "up"), (51, -13, "up"),
             (-51, 13, "down"), (-17, 13, "down"), (17, 13, "down"), (51, 13, "down"), (-92, 2, "left"), (92, 2, "right")]},
}

_built = {"variants": set(), "tables": set(), "sets": set()}
BUILT: dict = {}   # variant id -> {"dir", "theme", "cabinets": [...]}


def cabinet_spots(spot: str, bank: str) -> list[tuple]:
    cx, cy = SPOTS[spot]["centre"]
    return [(cx + dx, cy + dy, facing) for dx, dy, facing in BANKS[bank]["cabinets"]]


def bank_of(where: dict) -> str | None:
    """A build's bank shape (builds before the shapes gave a cabinet count: the shape of that size)."""
    if where.get("bank") in BANKS:
        return where["bank"]
    return next((k for k, b in BANKS.items() if len(b["cabinets"]) == where.get("count")), None)


def install(root: Path = DEFAULT_DIR) -> list[str]:
    """Load every built slot under root (see the module docstring). Returns their ids."""
    for vid in _built["variants"]:
        VARIANTS.pop(vid, None)
    for tid in _built["tables"]:
        floor.TABLES.pop(tid, None)
    for s in _built["sets"]:
        sounds.FACTORY.pop(s, None)
    _built.update(variants=set(), tables=set(), sets=set())
    BUILT.clear()
    taken = set()
    for path in sorted(root.glob("*/variant.json")) if root.is_dir() else []:
        try:
            v = from_json(path)
        except (ValueError, KeyError, OSError) as e:
            print(f"slot build {path.parent.name} not loaded: {e}")
            continue
        if v.id in VARIANTS:
            print(f"slot build {v.id} not loaded: that id is taken")
            continue
        spot = v.extras.get("floor", {}).get("spot")
        bank = bank_of(v.extras.get("floor", {}))
        cabinets = []
        if spot in SPOTS and spot not in taken and bank:
            taken.add(spot)
            for i, (x, y, facing) in enumerate(cabinet_spots(spot, bank), 1):
                tid = f"{v.id}_{i}"
                floor.TABLES[tid] = {"game": "slots", "variant": v.id, "name": v.name, "seats": 1}
                _built["tables"].add(tid)
                cabinets.append({"id": tid, "variant": v.id, "name": v.name, "x": x, "y": y, "facing": facing})
        VARIANTS[v.id] = v
        _built["variants"].add(v.id)
        if v.extras.get("sounds"):
            sounds.FACTORY[f"slots.{v.id}"] = {k: dict(e) for k, e in v.extras["sounds"].items()}
            _built["sets"].add(f"slots.{v.id}")
        BUILT[v.id] = {"dir": path.parent, "theme": v.theme, "cabinets": cabinets}
    sounds.refresh_sets()
    return sorted(BUILT)


def cabinets() -> list[dict]:
    """The built cabinets the client adds to the floor (welcome), each with its look."""
    return [{**c, "cabinet": b["theme"].get("cabinet", {})} for b in BUILT.values() for c in b["cabinets"]]


def art_path(vid: str, rel: str) -> Path | None:
    """A built slot's picture or font, by its path in the build folder (art/<id>.png, fonts/<file>)."""
    b = BUILT.get(vid)
    if not b or not isinstance(rel, str) or "\\" in rel or rel.startswith("/") or rel.split("/")[0] not in ("art", "fonts"):
        return None
    path = (b["dir"] / rel).resolve()
    if not path.is_relative_to(b["dir"].resolve()) or not path.is_file():
        return None
    return path
