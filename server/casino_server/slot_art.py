"""
Slot art the admin page can change (its Slots > Art tab), the way the Sounds tab changes sounds.

Each variant's assets (symbols, trail items, the trail armadillo and the pistol cylinder) can
come from:
  vector/<id>.png    the hand-drawn set, signed off and the default (tools/build_slot_art.py)
  flux1|flux2/<id>.png   the two FLUX.2-klein candidates
  uploads/<file>.png     anything uploaded on the page (fitted into 512x512)

The library is server/slot_art/<variant>/ (uploads go to <data>/slot_art/uploads/<variant>/);
the picks are <data>/slot_art.json. The game asks for /api/slots/art/manifest when it connects
and again on a `slot_art_changed` broadcast, and falls back to its built-in vector set.
"""
import io
import json
import re
from pathlib import Path

LIBRARY_DIR = Path(__file__).resolve().parent.parent / "slot_art"
SIZE = 512
MAX_UPLOAD = 8 * 1024 * 1024
SOURCES = ("vector", "flux1", "flux2")

# What can be changed, per variant, in page order: asset id -> name.
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


class ArtError(ValueError):
    """A request the art settings can't take (shown to the page as-is)."""


class SlotArtBoard:
    def __init__(self, data_dir: Path, library_dir: Path = LIBRARY_DIR):
        self.library_dir = library_dir
        self.uploads_dir = data_dir / "slot_art" / "uploads"
        self.path = data_dir / "slot_art.json"
        self.version, self.picks = 0, {}
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text())
                self.version = int(saved.get("version", 0))
                self.picks = {v: {a: s for a, s in p.items() if a in ASSETS.get(v, {})}
                              for v, p in saved.get("picks", {}).items() if v in ASSETS}
            except (ValueError, OSError):
                pass

    # ------------------------------------------------------------- reading
    def choice(self, variant: str, asset: str) -> str:
        chosen = self.picks.get(variant, {}).get(asset)
        if chosen and self.file_path(variant, chosen):
            return chosen
        return f"vector/{asset}.png"

    def manifest(self) -> dict:
        """What the game loads: each changed asset's image URL (unchanged ones use the built-in set)."""
        out = {}
        for variant, assets in ASSETS.items():
            out[variant] = {}
            for asset in assets:
                source = self.choice(variant, asset)
                if source.startswith("vector/"):
                    continue
                path = self.file_path(variant, source)
                if path:
                    out[variant][asset] = f"/slot-art/{variant}/{source}?v={int(path.stat().st_mtime)}"
        return {"version": self.version, "variants": out}

    def overview(self) -> dict:
        """Everything the admin page shows: each asset's pick and its candidates, and the uploads."""
        variants = []
        for variant, assets in ASSETS.items():
            rows = []
            for asset, name in assets.items():
                candidates = [f"{s}/{asset}.png" for s in SOURCES if self.file_path(variant, f"{s}/{asset}.png")]
                rows.append({"asset": asset, "name": name, "choice": self.choice(variant, asset),
                             "is_default": asset not in self.picks.get(variant, {}), "candidates": candidates})
            uploads = sorted(f"uploads/{p.name}" for p in (self.uploads_dir / variant).glob("*.png")) \
                if (self.uploads_dir / variant).exists() else []
            variants.append({"variant": variant, "assets": rows, "uploads": uploads})
        return {"version": self.version, "variants": variants}

    def file_path(self, variant: str, source: str) -> Path | None:
        """The image a source names, or None -- never anything outside the library."""
        if variant not in ASSETS or not isinstance(source, str) or "\\" in source or source.startswith("/"):
            return None
        if source.startswith("uploads/"):
            root, rel = self.uploads_dir / variant, source[len("uploads/"):]
        else:
            root, rel = self.library_dir / variant, source
        path = (root / rel).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or path.suffix.lower() != ".png":
            return None
        return path

    # ------------------------------------------------------------- changing
    def set_choice(self, variant: str, asset: str, source: str) -> str:
        if asset not in ASSETS.get(variant, {}):
            raise ArtError(f"There's no {asset!r} on {variant!r}.")
        if not self.file_path(variant, source):
            raise ArtError(f"Not in the library: {source}")
        self.picks.setdefault(variant, {})[asset] = source
        self._save()
        return self.choice(variant, asset)

    def reset(self, variant: str, asset: str | None = None):
        if variant not in ASSETS:
            raise ArtError(f"There's no slot called {variant!r}.")
        if asset is None:
            self.picks.pop(variant, None)
        else:
            self.picks.get(variant, {}).pop(asset, None)
        self._save()

    def upload(self, variant: str, filename: str, data: bytes) -> str:
        """Add an image to the variant's uploads, fitted into 512x512 on a clear background."""
        from PIL import Image, UnidentifiedImageError
        if variant not in ASSETS:
            raise ArtError(f"There's no slot called {variant!r}.")
        if not data:
            raise ArtError("That file is empty.")
        if len(data) > MAX_UPLOAD:
            raise ArtError("That file is over 8 MB.")
        try:
            im = Image.open(io.BytesIO(data)).convert("RGBA")
        except (UnidentifiedImageError, OSError):
            raise ArtError("That isn't an image the server can read (use PNG, JPEG or WebP).")
        im.thumbnail((SIZE, SIZE), Image.LANCZOS)
        out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        out.paste(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2), im)
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(filename).stem).strip(".-")[:60] or "art"
        folder = self.uploads_dir / variant
        folder.mkdir(parents=True, exist_ok=True)
        out.save(folder / f"{stem}.png")
        return f"uploads/{stem}.png"

    def delete_upload(self, variant: str, source: str):
        path = self.file_path(variant, source) if source.startswith("uploads/") else None
        if path is None:
            raise ArtError("Only uploaded art can be deleted.")
        path.unlink()
        for asset, chosen in list(self.picks.get(variant, {}).items()):
            if chosen == source:
                del self.picks[variant][asset]
        self._save()

    def _save(self):
        self.version += 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"version": self.version, "picks": self.picks}, indent=1))
