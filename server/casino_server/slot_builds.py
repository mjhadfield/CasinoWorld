"""
Slots built with the Slot design wizard (its Build step), joining the casino when the server starts.

Each built slot is a folder under server/slot_builds/<id>/ (CASINO_SLOT_BUILDS_DIR moves it, for tests and the
dev instance):
  variant.json   the variant (slots/variant.py from_json), its theme (its cabinet's look among it) and its sounds
  art/<id>.png   every picture the game draws for it: the tiers (W, H1.., BS, FS), the feature and bonus art,
                 the logo and the background (bg)
  fonts/         its display and interface fonts
  IDEAS.md       feature or bonus ideas the design described that still need building in code

install() runs in the app's lifespan, before the casino and the sound board start: it registers the variants
(slots/variants VARIANTS) and gives each its sound set (sounds.py). A build puts no cabinets on the floor: the
admin page's Floor tab does that (slot_banks.py). Everything install adds is removed first, so it can run again
(tests do, with their own folder).
"""
import datetime
import json
import os
import subprocess
from pathlib import Path

from casino_server import sounds
from casino_server.slots.variant import from_json
from casino_server.slots.variants import VARIANTS

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "slot_builds"
REPO = Path(__file__).resolve().parents[2]

_built = {"variants": set(), "sets": set()}
BUILT: dict = {}   # variant id -> {"dir", "theme"}


def install(root: Path = DEFAULT_DIR) -> list[str]:
    """Load every built slot under root (see the module docstring). Returns their ids."""
    for vid in _built["variants"]:
        VARIANTS.pop(vid, None)
    for s in _built["sets"]:
        sounds.FACTORY.pop(s, None)
    _built.update(variants=set(), sets=set())
    BUILT.clear()
    for path in sorted(root.glob("*/variant.json")) if root.is_dir() else []:
        try:
            v = from_json(path)
        except (ValueError, KeyError, OSError) as e:
            print(f"slot build {path.parent.name} not loaded: {e}")
            continue
        if v.id in VARIANTS:
            print(f"slot build {v.id} not loaded: that id is taken")
            continue
        VARIANTS[v.id] = v
        _built["variants"].add(v.id)
        if v.extras.get("sounds"):
            sounds.FACTORY[f"slots.{v.id}"] = {k: dict(e) for k, e in v.extras["sounds"].items()}
            _built["sets"].add(f"slots.{v.id}")
        BUILT[v.id] = {"dir": path.parent, "theme": v.theme}
    sounds.refresh_sets()
    return sorted(BUILT)


def on_disk(root: Path) -> dict:
    """Every build folder's slot, loaded or not (one built since the server started loads when it restarts):
    id -> {"name", "cabinet"}."""
    out = {}
    for path in sorted(root.glob("*/variant.json")) if root.is_dir() else []:
        try:
            v = json.loads(path.read_text())
            out[v["id"]] = {"name": v.get("name", v["id"]), "cabinet": v.get("theme", {}).get("cabinet", {})}
        except (ValueError, KeyError, OSError):
            continue
    return out


def is_live() -> bool:
    """The live server (not a test or a dev instance, which keep their data and builds elsewhere)."""
    return not os.environ.get("CASINO_DATA_DIR") and not os.environ.get("CASINO_SLOT_BUILDS_DIR")


def restart_live(why: str) -> None:
    """Restart the live server, from its own unit (a request can't restart its server). Raises OSError or
    subprocess.SubprocessError if it couldn't be started."""
    subprocess.run(["systemd-run", "--user", "--collect", "--quiet",
                    f"--unit=casino-{why}-{int(datetime.datetime.now().timestamp())}",
                    str(REPO / "tools" / "dev.sh"), "restart"], check=True, timeout=20, capture_output=True)


def art_path(vid: str, rel: str) -> Path | None:
    """A built slot's picture or font, by its path in the build folder (art/<id>.png, fonts/<file>)."""
    b = BUILT.get(vid)
    if not b or not isinstance(rel, str) or "\\" in rel or rel.startswith("/") or rel.split("/")[0] not in ("art", "fonts"):
        return None
    path = (b["dir"] / rel).resolve()
    if not path.is_relative_to(b["dir"].resolve()) or not path.is_file():
        return None
    return path
