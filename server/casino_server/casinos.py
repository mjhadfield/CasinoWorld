"""
The casinos: several, each with its own floor plan, that players choose between after picking a character.

<data dir>/casinos.json is the registry, in order:
    [{"id", "name", "blurb", "open", "order", "population"}]
  open        listed on the chooser (a hidden one is still reachable with ?casino=<id>, and on the admin page)
  population  how many punters its NPC director keeps on its floor
<data dir>/casinos/<id>/plan/ is each one's floor plan (plan.py: draft.json, live.json, history/).

Settings kept by table id are shared across the casinos, so they're kept by qualified id, "<casino>/<table>" (table
ids repeat between plans: each plan has its own serials): the seating and table-style placements and an NPC's
avoid_table. Each casino sends its clients its own slice, unqualified (`own`).

The first start with this layout (migrate) moves a single-casino data dir's plan to "demo" and qualifies those keys.
"""
import json
import re
import shutil
import time
from pathlib import Path

from casino_server import plan, roster

DEMO = "demo"
ID_RE = re.compile(r"^[a-z0-9_]{1,24}$")
MAX_NAME, MAX_BLURB = 40, 120
STYLE_KEYS = ("table_styles", "table_styles_roulette", "table_styles_craps")   # (table_styles.KINDS' keys)


def registry_path(data_dir: Path) -> Path:
    return data_dir / "casinos.json"


def casino_dir(data_dir: Path, cid: str) -> Path:
    """Where a casino keeps its things: its floor plan is plan.plan_dir() of this."""
    return data_dir / "casinos" / cid


def load(data_dir: Path) -> list[dict]:
    try:
        raw = json.loads(registry_path(data_dir).read_text())
    except (FileNotFoundError, ValueError):
        return []
    return sorted((c for c in raw if isinstance(c, dict) and ID_RE.match(str(c.get("id", "")))),
                  key=lambda c: (c.get("order", 0), c["id"]))


def save(data_dir: Path, registry: list[dict]):
    for n, c in enumerate(registry):
        c["order"] = n
    plan._write(registry_path(data_dir), registry)


def entry(cid: str, name: str, blurb: str = "", open_: bool = True, population: int = 6) -> dict:
    return {"id": cid, "name": name, "blurb": blurb, "open": open_, "order": 0, "population": population}


def qualify(cid: str, table_id: str) -> str:
    return f"{cid}/{table_id}"


def own(keyed: dict, cid: str) -> dict:
    """The entries of a dict kept by qualified table id that are this casino's, by their plain table ids."""
    pre = cid + "/"
    return {k[len(pre):]: v for k, v in keyed.items() if k.startswith(pre)}


def every_table(boards: dict) -> dict:
    """Every casino's tables (PlanBoard.every_table) by qualified id: {cid: board} -> {"<cid>/<table>": {...}}."""
    return {qualify(cid, k): v for cid, board in boards.items() for k, v in board.every_table().items()}


def _qualified(keyed: dict, cid: str) -> dict:
    return {(k if "/" in k else qualify(cid, k)): v for k, v in keyed.items()}


def migrate(data_dir: Path, store) -> list[dict]:
    """Bring a data dir to this layout and return the registry (see the module docstring). A single-casino plan
    (<data>/plan) is backed up and becomes Demo's, with the floor's population; with no plan at all, Demo starts
    with plan.first_plan(). Any table-id key not qualified yet is taken to be Demo's (so this is safe every start)."""
    registry = load(data_dir)
    old = plan.plan_dir(data_dir)
    if not registry:
        demo = casino_dir(data_dir, DEMO)
        if old.is_dir() and not plan.plan_dir(demo).exists():
            backup = data_dir / f"plan-single-casino-{time.strftime('%Y%m%d-%H%M%S')}"
            shutil.copytree(old, backup)
            demo.mkdir(parents=True, exist_ok=True)
            old.rename(plan.plan_dir(demo))
            print(f"moved the floor plan to {plan.plan_dir(demo)} (a copy is in {backup.name})")
        plan.load_live(demo)   # (seeds the first plan if there's none)
        registry = [entry(DEMO, "Demo", population=roster.settings(store)["population"])]
        save(data_dir, registry)
    seating = store.get_json("seating", None)
    if seating and any("/" not in k for k in seating.get("tables", {})):
        seating["tables"] = _qualified(seating["tables"], DEMO)
        store.set_json("seating", seating)
    for key in STYLE_KEYS:
        saved = store.get_json(key, None)
        if saved and any("/" not in k for k in saved.get("tables", {})):
            saved["tables"] = _qualified(saved["tables"], DEMO)
            store.set_json(key, saved)
    for rec in store.npcs(archived=None):
        avoid = rec["settings"].get("avoid_table")
        if avoid and "/" not in avoid:
            store.update_npc(rec["id"], {"settings": {**rec["settings"], "avoid_table": qualify(DEMO, avoid)}})
    return registry


class Claims:
    """Which casino each NPC is in, punter or dealer (npc id -> casino id): the casinos share one cast, and nobody is
    in two at once. A punter's claim is taken when they come in and let go when they've walked out; a dealer's for
    their shift."""

    def __init__(self):
        self.by_npc: dict[int, str] = {}

    def elsewhere(self, npc_id: int, cid: str) -> bool:
        owner = self.by_npc.get(npc_id)
        return owner is not None and owner != cid

    def take(self, npc_id: int, cid: str):
        self.by_npc[npc_id] = cid

    def release(self, npc_id: int, cid: str):
        if self.by_npc.get(npc_id) == cid:
            del self.by_npc[npc_id]

    def release_all(self, cid: str):
        for npc_id in [n for n, c in self.by_npc.items() if c == cid]:
            del self.by_npc[npc_id]
