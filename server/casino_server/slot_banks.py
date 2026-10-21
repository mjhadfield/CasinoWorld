"""
The slot banks on the floor: groups of cabinets, each cabinet any slot (Armadillo Goes West or one built with the
Slot design wizard) facing any way, made and placed on the admin page's Floor tab.

<data dir>/slot_banks.json holds them (no file: no slots on the floor):
  {"serial": 3, "banks": [{"id": "b1", "name": "Bank 1", "x": 1650, "y": 960, "next": 4,
     "cabinets": [{"id": "b1_1", "dx": -51, "dy": -13, "facing": "up", "variant": "startrek"}, ...]}]}
A bank's x, y is its centre on the floor and each cabinet's dx, dy its base centre from there. A cabinet's id is its
table id: given once (the bank's id and its `next`) and kept through moves and re-slotting.

install() runs in the app's lifespan, after slot_builds.install (so every built variant is known) and before the
casino starts: each cabinet whose slot is loaded becomes a one-seat table in floor.TABLES. Saving on the page
changes the file only; the floor changes when the server restarts (the Apply button, slot_builds.restart_live).

The checks (check()) use floor_map.json -- the room, each table's footprint and the floor points, measured from
the client's scene by tools/floor_map.gd -- and the cabinet's own shape (slot_cabinet.gd): its base, its tall art,
its stool and where its player stands to sit down. The page draws the same shapes from rules().
"""
import copy
import json
import subprocess
from pathlib import Path

from casino_server import floor, slot_builds, sounds
from casino_server.slots.variants import VARIANTS

FLOOR_MAP = json.loads((Path(__file__).resolve().parent / "floor_map.json").read_text())
FACINGS = ("down", "up", "left", "right")
# A cabinet's shapes from its base centre, as (x, y, w, h), by facing (slot_cabinet.gd: Body/Shape, the drawn
# cabinet, STOOL_AT with the stool's size, STAND_AT).
BODY = {"down": (-16, -13, 32, 14), "up": (-16, -13, 32, 14), "left": (-11, -13, 22, 14), "right": (-11, -13, 22, 14)}
ART = {"down": (-16, -64, 32, 64), "up": (-16, -64, 32, 64), "left": (-12, -64, 24, 64), "right": (-12, -64, 24, 64)}
STOOL = {"down": (-10, 11, 20, 12), "up": (-10, -21, 20, 12), "left": (-29, -2, 20, 12), "right": (9, -2, 20, 12)}
STAND = {"down": (0, 36), "up": (0, -34), "left": (-38, 6), "right": (38, 6)}
POINT_CLEAR = 16   # how far a cabinet keeps from a floor point

_added: set = set()
LOADED: dict = {"banks": [], "skipped": []}   # what install() put on the floor (the page compares the file with it)


class BankError(ValueError):
    """Banks the floor can't take (shown to the page as-is)."""


def path(data_dir: Path) -> Path:
    return data_dir / "slot_banks.json"


def load(data_dir: Path) -> dict:
    try:
        data = json.loads(path(data_dir).read_text())
    except FileNotFoundError:
        return {"serial": 0, "banks": []}
    except (ValueError, OSError) as e:
        print(f"slot_banks.json not read ({e}): no slot banks on the floor")
        return {"serial": 0, "banks": []}
    return {"serial": int(data.get("serial", 0)), "banks": data.get("banks", [])}


def variant_names(builds_dir: Path | None = None) -> dict:
    """Every slot a cabinet can be: the loaded ones and any built since the server started -> its name."""
    out = {vid: v.name for vid, v in VARIANTS.items()}
    if builds_dir:
        out.update({vid: b["name"] for vid, b in slot_builds.on_disk(builds_dir).items() if vid not in out})
    return out


def install(data_dir: Path) -> list[str]:
    """Put the banks' cabinets on the floor (see the module docstring). Returns their table ids."""
    for tid in _added:
        floor.TABLES.pop(tid, None)
    _added.clear()
    data = load(data_dir)
    skipped = []
    for bank in data["banks"]:
        for c in bank.get("cabinets", []):
            v = VARIANTS.get(c.get("variant"))
            if v is None or c.get("id") in floor.TABLES:
                skipped.append(c.get("id"))
                print(f"slot cabinet {c.get('id')} not on the floor: " + ("its id is taken" if v else f"no slot {c.get('variant')!r}"))
                continue
            floor.TABLES[c["id"]] = {"game": "slots", "variant": v.id, "name": v.name, "seats": 1}
            _added.add(c["id"])
    LOADED.update(banks=copy.deepcopy(data["banks"]), skipped=skipped)
    sounds.refresh_sets()
    return sorted(_added)


def cabinets() -> list[dict]:
    """The cabinets the client puts on the floor (welcome): where each stands, which way it faces, its look."""
    out = []
    for bank in LOADED["banks"]:
        for c in bank.get("cabinets", []):
            if c["id"] in _added:
                look = slot_builds.BUILT.get(c["variant"], {}).get("theme", {}).get("cabinet", {})
                out.append({"id": c["id"], "variant": c["variant"], "name": floor.TABLES[c["id"]]["name"],
                            "x": bank["x"] + c["dx"], "y": bank["y"] + c["dy"], "facing": c["facing"], "cabinet": look})
    return out


# ------------------------------------------------------------------ the shapes and the checks
def _at(r, x, y):
    return (r[0] + x, r[1] + y, r[2], r[3])


def _overlap(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _inside(p, r) -> bool:
    return r[0] <= p[0] <= r[0] + r[2] and r[1] <= p[1] <= r[1] + r[3]


def _grow(r, by):
    return (r[0] - by, r[1] - by, r[2] + 2 * by, r[3] + 2 * by)


def shapes(bank: dict, c: dict) -> dict:
    x, y, f = bank["x"] + c["dx"], bank["y"] + c["dy"], c["facing"]
    return {"body": _at(BODY[f], x, y), "art": _at(ART[f], x, y), "stool": _at(STOOL[f], x, y),
            "stand": (x + STAND[f][0], y + STAND[f][1])}


def check(banks: list) -> list[dict]:
    """Every problem with these banks on the floor: [{"cabinet": id, "message"}] (the first per cabinet)."""
    walk = FLOOR_MAP["walkable"]
    every = [(b, c, shapes(b, c)) for b in banks for c in b["cabinets"]]
    problems = []
    for b, c, s in every:
        name = f"{b['name']}: a cabinet at {round(b['x'] + c['dx'])}, {round(b['y'] + c['dy'])}"
        bad = None
        if not all(_inside(p, walk) for r in (s["body"], s["stool"]) for p in ((r[0], r[1]), (r[0] + r[2], r[1] + r[3]))) \
                or not _inside(s["stand"], walk):
            bad = "is off the floor"
        for t in FLOOR_MAP["tables"] if not bad else ():
            if any(_overlap(s[k], t["rect"]) for k in ("body", "art", "stool")) or _inside(s["stand"], t["rect"]):
                bad = f"is in {t['name']}'s way"
                break
        for pname, p in FLOOR_MAP["points"].items() if not bad else ():
            if any(_inside(p, _grow(s[k], POINT_CLEAR)) for k in ("body", "stool")):
                bad = "stands on " + ("the entrance" if pname == "entrance" else "an aisle NPCs walk to")
                break
        for b2, c2, s2 in every if not bad else ():
            if c2 is c:
                continue
            if _overlap(s["body"], s2["body"]) or _overlap(s["stool"], s2["body"]) or _overlap(s["stool"], s2["stool"]):
                bad = "overlaps another cabinet" + ("" if b2 is b else f" ({b2['name']})")
                break
            if _inside(s["stand"], s2["body"]):
                bad = "can't be reached: another cabinet stands where its player would"
                break
        if bad:
            problems.append({"cabinet": c["id"], "message": f"{name} {bad}."})
    return problems


def rules() -> dict:
    """What the page draws and checks with: the floor map and a cabinet's shapes."""
    return {"floor": FLOOR_MAP, "body": BODY, "art": ART, "stool": STOOL, "stand": STAND, "point_clear": POINT_CLEAR}


# ------------------------------------------------------------------ the page
class SlotBankBoard:
    def __init__(self, data_dir: Path, builds_dir: Path):
        self.data_dir, self.builds_dir = data_dir, builds_dir

    def view(self) -> dict:
        data = load(self.data_dir)
        names = variant_names(self.builds_dir)
        disk = slot_builds.on_disk(self.builds_dir)
        slots = [{"id": vid, "name": name, "loaded": vid in VARIANTS,
                  "cabinet": slot_builds.BUILT[vid]["theme"].get("cabinet", {}) if vid in slot_builds.BUILT
                  else disk.get(vid, {}).get("cabinet", {}),
                  "logo": f"/slot-art/{vid}/" + ("built/logo.png" if vid in slot_builds.BUILT else "vector/logo.png") if vid in VARIANTS else None}
                 for vid, name in names.items()]
        return {"banks": data["banks"], "slots": slots, "rules": rules(), "problems": check(data["banks"]),
                "pending": self.changes(data["banks"]), "skipped": LOADED["skipped"], "live": slot_builds.is_live()}

    @staticmethod
    def changes(banks: list) -> int:
        """How many cabinets differ between these banks and what's on the floor."""
        def flat(bs):
            return {c["id"]: (b["x"] + c["dx"], b["y"] + c["dy"], c["facing"], c["variant"]) for b in bs for c in b.get("cabinets", [])}
        now, then = flat(banks), flat(LOADED["banks"])
        return sum(1 for k in now.keys() | then.keys() if now.get(k) != then.get(k))

    def save(self, raw) -> dict:
        """Check and keep the page's banks (new banks and cabinets come without ids: they're given them here)."""
        if not isinstance(raw, dict) or not isinstance(raw.get("banks"), list):
            raise BankError("Expected {banks: [...]}.")
        data = load(self.data_dir)
        old = {b["id"]: b for b in data["banks"]}
        names = variant_names(self.builds_dir)
        serial, banks, seen = data["serial"], [], set()
        for rb in raw["banks"]:
            if not isinstance(rb, dict) or not isinstance(rb.get("cabinets"), list):
                raise BankError("Each bank needs its cabinets.")
            bid = rb.get("id")
            if bid in old and bid not in seen:
                bank = {"id": bid, "next": old[bid].get("next", 1)}
            elif bid is None:
                serial += 1
                while f"b{serial}" in old:
                    serial += 1
                bank = {"id": f"b{serial}", "next": 1}
            else:
                raise BankError(f"There's no bank {bid!r}.")
            seen.add(bank["id"])
            try:
                bank.update(name=str(rb.get("name") or f"Bank {bank['id'][1:]}").strip()[:40] or bank["id"],
                            x=round(float(rb["x"])), y=round(float(rb["y"])))
            except (KeyError, TypeError, ValueError):
                raise BankError("A bank needs its place on the floor (x, y).")
            mine = {c["id"] for c in old.get(bank["id"], {}).get("cabinets", [])}
            cabs = []
            for rc in rb["cabinets"]:
                try:
                    c = {"dx": round(float(rc["dx"])), "dy": round(float(rc["dy"])), "facing": rc["facing"], "variant": rc["variant"]}
                except (KeyError, TypeError, ValueError):
                    raise BankError("A cabinet needs its place in the bank, its facing and its slot.")
                if c["facing"] not in FACINGS:
                    raise BankError(f"A cabinet can face {', '.join(FACINGS)}.")
                if c["variant"] not in names:
                    raise BankError(f"There's no slot {c['variant']!r}.")
                cid = rc.get("id")
                if cid is None:
                    cid = f"{bank['id']}_{bank['next']}"
                    bank["next"] += 1
                elif cid not in mine or cid in seen:
                    raise BankError(f"There's no cabinet {cid!r} in {bank['name']}.")
                seen.add(cid)
                cabs.append({"id": cid, **c})
            bank["cabinets"] = cabs
            banks.append(bank)
        problems = check(banks)
        if problems:
            raise BankError(problems[0]["message"] + (f" (and {len(problems) - 1} more)" if len(problems) > 1 else ""))
        path(self.data_dir).write_text(json.dumps({"serial": serial, "banks": banks}, indent=1))
        return self.view()

    def apply(self) -> str:
        if not slot_builds.is_live():
            raise BankError("This is a test or dev instance: restart it (tools/dev.sh server) to put the banks on its floor.")
        try:
            slot_builds.restart_live("banks")
        except (OSError, subprocess.SubprocessError) as e:
            raise BankError(f"Couldn't start the restart: {e}")
        return "Restarting the casino in a moment: games reconnect by themselves, with the new banks."
