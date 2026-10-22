"""
The slot art the game loads in place of its built-in set.

Armadillo's assets (symbols, trail items, the trail armadillo and the pistol cylinder) come from:
  vector/<id>.png    the hand-drawn set, signed off and the default (tools/build_slot_art.py)
  flux1|flux2/<id>.png   the two FLUX.2-klein candidates

The library is server/slot_art/<variant>/; the picks are <data>/slot_art.json, made on the old
admin page's Slots > Art tab and now fixed (Armadillo will become a Slot design project). The game
asks for /api/slots/art/manifest when it connects and falls back to its built-in vector set.

Slots built with the Slot design wizard (slot_builds.py) have no built-in set: their pictures are
built/<id>.png (from their build folder's art/), the manifest lists every one of them, and their
display and interface fonts (manifest "fonts") come from the build folder too.
"""
import json
from pathlib import Path

from casino_server import slot_builds
from casino_server.slots.variants import VARIANTS

LIBRARY_DIR = Path(__file__).resolve().parent.parent / "slot_art"

# Each variant's assets: asset id -> name.
ASSETS = {
    "armadillo": {
        "W": "Wild (sheriff's star)", "H1": "Armadillo", "H2": "Snake", "M1": "Hat", "M2": "Horseshoe",
        "M3": "Whiskey", "M4": "Boots", "L1": "Spade", "L2": "Club", "L3": "Diamond", "L4": "Heart",
        "BS": "Bonus wagon", "FS": "Free-spin pistols", "barrel": "Instant Win barrel", "armadillo": "Trail armadillo",
        "cylinder": "Pistol cylinder", "t_coin": "Trail: coins", "t_double": "Trail: double",
        "t_forward": "Trail: forward / back", "t_heart": "Trail: heart", "t_lightning": "Trail: lightning roll",
        "t_crate": "Trail: award all coins", "t_upgrade": "Trail: spin upgrade", "t_gold": "Trail: prizepot",
        "t_snake": "Trail: snake", "logo": "Logo (lettering)",
    },
}


def _assets() -> dict:
    """Every variant's assets: Armadillo's, and each built slot's (from its variant.json)."""
    return {**ASSETS, **{vid: VARIANTS[vid].extras.get("assets", {}) for vid in slot_builds.BUILT if vid in VARIANTS}}


def _default(variant: str) -> str:
    return "built" if variant in slot_builds.BUILT else "vector"


class SlotArtBoard:
    def __init__(self, data_dir: Path, library_dir: Path = LIBRARY_DIR):
        self.library_dir = library_dir
        self.path = data_dir / "slot_art.json"
        self.version, self.picks = 0, {}
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text())
                self.version = int(saved.get("version", 0))
                self.picks = {v: {a: s for a, s in p.items() if a in _assets().get(v, {})}
                              for v, p in saved.get("picks", {}).items() if v in _assets()}
            except (ValueError, OSError):
                pass

    def choice(self, variant: str, asset: str) -> str:
        chosen = self.picks.get(variant, {}).get(asset)
        if chosen and self.file_path(variant, chosen):
            return chosen
        return f"{_default(variant)}/{asset}.png"

    def manifest(self) -> dict:
        """What the game loads: each changed asset's image URL (unchanged ones use the built-in set)."""
        out, fonts = {}, {}
        for variant, assets in _assets().items():
            out[variant] = {}
            for asset in assets:
                source = self.choice(variant, asset)
                if source.startswith("vector/"):
                    continue   # the game has these built in
                path = self.file_path(variant, source)
                if path:
                    out[variant][asset] = f"/slot-art/{variant}/{source}?v={int(path.stat().st_mtime)}"
            if variant in slot_builds.BUILT:
                for role, name in VARIANTS[variant].theme.get("fonts", {}).items():
                    path = slot_builds.art_path(variant, f"fonts/{name}")
                    if path:
                        fonts.setdefault(variant, {})[role] = f"/slot-art/{variant}/fonts/{name}?v={int(path.stat().st_mtime)}"
        return {"version": self.version, "variants": out, "fonts": fonts}

    def file_path(self, variant: str, source: str) -> Path | None:
        """The image a source names (or a built slot's font), or None -- never anything outside the library."""
        if variant not in _assets() or not isinstance(source, str) or "\\" in source or source.startswith("/"):
            return None
        if source.startswith("built/"):
            return slot_builds.art_path(variant, "art/" + source[len("built/"):])
        if source.startswith("fonts/"):
            return slot_builds.art_path(variant, source)
        root = self.library_dir / variant
        path = (root / source).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or path.suffix.lower() != ".png":
            return None
        return path
