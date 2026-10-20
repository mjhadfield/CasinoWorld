"""
The Slot design wizard's later steps (slot_design.py has the designs, Concept and Art). DesignBoard mixes these in,
so every method runs under the board's lock and saves through its Design.

  Value ladder   the chosen symbols ordered into the tiers (W, BS, FS, H1.., M1.., L1..) and the upgrade chain
  Scene          the background (FLUX or uploaded), the logo lettering (rendered here: FLUX can't spell) and the
                 reel frame's style
"""
import io
from pathlib import Path

from PIL import Image, ImageFont

from casino_server import slot_design_art as art
from casino_server.slots import base

FONTS_DIR = Path(__file__).resolve().parents[2] / "client" / "assets" / "fonts"
FRAME_STYLES = ("metal", "wood", "neon", "glass")
MAX_FONT = 8 * 1024 * 1024


class DesignError(ValueError):
    """A request the board can't take (shown to the page as-is)."""


def ladder_view(d) -> dict:
    """The Value ladder for the overview: every tier of the tier shape, the symbol in each, the upgrade chain and
    each tier's pays (the house defaults until the Maths step changes them)."""
    shape = d.data["concept"]["tiers"]
    tiers = base.tier_ids(shape)
    lad = d.data.get("ladder", {})
    ids = {s["id"] for s in d.data["symbols"]}
    slots = {t: sid for t, sid in lad.get("slots", {}).items() if t in tiers and sid in ids}
    upgrades = {k: v for k, v in (lad.get("upgrades") or base.default_upgrades(shape)).items() if k in tiers and v in tiers}
    pays = {**base.default_pays(shape), **{k: tuple(v) for k, v in d.data.get("maths", {}).get("pays", {}).items() if k in tiers}}
    return {"tiers": tiers, "slots": slots, "upgrades": upgrades, "default_upgrades": base.default_upgrades(shape),
            "pays": {k: list(v) for k, v in pays.items()}, "complete": len(slots) == len(tiers)}


def _fonts(d) -> list[str]:
    own = sorted(p.name for p in (d.folder / "fonts").glob("*.[ot]tf")) if (d.folder / "fonts").is_dir() else []
    return own + sorted(p.name for p in FONTS_DIR.glob("*.ttf"))


def _font_path(d, name: str) -> Path:
    for folder in (d.folder / "fonts", FONTS_DIR):
        p = folder / name
        if name and "/" not in name and p.is_file():
            return p
    raise DesignError(f"There's no font {name!r}.")


def scene_view(d) -> dict:
    sc = d.data.get("scene", {})
    folder = d.folder / "scene"
    listed = lambda pattern: sorted((f"scene/{p.name}" for p in folder.glob(pattern)),
                                    key=lambda p: int(Path(p).stem.split("_")[-1])) if folder.is_dir() else []
    return {"background": sc.get("background"), "logo": sc.get("logo", {}), "frame": sc.get("frame", {"style": "metal", "colour": "#c9a24a"}),
            "backgrounds": listed("bg_*.png"), "logos": listed("logo_*.png"), "fonts": _fonts(d), "frame_styles": list(FRAME_STYLES)}


class StepsMixin:
    # ------------------------------------------------------------- Value ladder
    def set_ladder(self, did: str, slots: dict, upgrades: dict | None = None) -> dict:
        with self.lock:
            d = self.design(did)
            tiers = base.tier_ids(d.data["concept"]["tiers"])
            ids = {s["id"] for s in d.data["symbols"]}
            if not isinstance(slots, dict):
                raise DesignError("The ladder is {tier: symbol}.")
            clean = {}
            for tier, sid in slots.items():
                if not sid:
                    continue
                if tier not in tiers:
                    raise DesignError(f"There's no tier {tier!r} in this slot's tier shape.")
                if sid not in ids:
                    raise DesignError(f"There's no symbol {sid!r}.")
                if sid in clean.values():
                    raise DesignError(f"{sid} is in two tiers: each symbol takes one.")
                clean[tier] = sid
            lad = d.data.setdefault("ladder", {})
            lad["slots"] = clean
            if upgrades is not None:
                order = {t: i for i, t in enumerate(tiers)}
                for frm, to in upgrades.items():
                    if frm not in order or to not in order or frm in ("W", "BS", "FS") or to in ("W", "BS", "FS"):
                        raise DesignError(f"{frm} → {to} isn't an upgrade between pay tiers.")
                    if order[to] >= order[frm]:
                        raise DesignError(f"{frm} must upgrade to a higher tier than itself, not {to}.")
                lad["upgrades"] = dict(upgrades)
            d.save()
            return ladder_view(d)

    # ------------------------------------------------------------- Scene
    def queue_background(self, did: str, description: str) -> dict:
        description = str(description or "").strip()[:400]
        if not description:
            raise DesignError("Describe the background.")
        with self.lock:
            d = self.design(did)
            job = self._queue(d, None, {"how": "text", "src": None, "text": description, "out": "background",
                                        "action": "background"})
            d.save()
            return job

    def add_background(self, did: str, filename: str, data: bytes = b"", path: str | None = None) -> str:
        """An uploaded background, or an image already on the board, fitted to the 1280×720 screen."""
        with self.lock:
            d = self.design(did)
            if path:
                p = d.path(path)
                if not p:
                    raise DesignError(f"Not on the board: {path}")
                im = Image.open(p).convert("RGB")
            else:
                im = self._read_image(data).convert("RGB")
            out = self._next_scene(d, "bg")
            art.fit_cover(im, (1280, 720)).save(d.folder / out)
            d.data.setdefault("scene", {})["background"] = out
            d.save()
            return out

    def _next_scene(self, d, kind: str) -> str:
        folder = d.folder / "scene"
        folder.mkdir(exist_ok=True)
        ns = [int(p.stem.split("_")[-1]) for p in folder.glob(f"{kind}_*.png") if p.stem.split("_")[-1].isdigit()]
        return f"scene/{kind}_{max(ns, default=0) + 1}.png"

    def render_logo(self, did: str, spec: dict) -> str:
        lines = [str(x).strip()[:30] for x in (spec.get("lines") or []) if str(x).strip()][:3]
        if not lines:
            raise DesignError("Type the logo's words.")
        colours = {k: spec.get(k) or v for k, v in (("top", "#fff1b0"), ("bottom", "#d39a26"), ("outline", "#2b1004"))}
        for c in colours.values():
            if not art.is_colour(c):
                raise DesignError(f"{c!r} isn't a colour like #d39a26.")
        with self.lock:
            d = self.design(did)
            font = _font_path(d, spec.get("font") or "Cinzel-SemiBold.ttf")
            emblem = None
            if spec.get("emblem"):
                p = d.path(spec["emblem"])
                if not p:
                    raise DesignError(f"Not on the board: {spec['emblem']}")
                emblem = Image.open(p).convert("RGBA")
        logo = art.render_logo(lines, font, colours["top"], colours["bottom"], colours["outline"], emblem)
        with self.lock:
            out = self._next_scene(d, "logo")
            logo.save(d.folder / out)
            d.data.setdefault("scene", {})["logo"] = {**colours, "font": font.name, "emblem": spec.get("emblem"),
                                                     "lines": lines, "file": out}
            d.save()
            return out

    def update_scene(self, did: str, ch: dict) -> None:
        with self.lock:
            d = self.design(did)
            sc = d.data.setdefault("scene", {})
            for k, v in ch.items():
                if k == "background":
                    if v and not (v.startswith("scene/bg_") and d.path(v)):
                        raise DesignError("Pick one of this slot's backgrounds.")
                    sc["background"] = v or None
                elif k == "logo_file":
                    if not (isinstance(v, str) and v.startswith("scene/logo_") and d.path(v)):
                        raise DesignError("Pick one of this slot's logos.")
                    sc.setdefault("logo", {})["file"] = v
                elif k == "frame":
                    if not isinstance(v, dict) or v.get("style") not in FRAME_STYLES or not art.is_colour(v.get("colour")):
                        raise DesignError(f"A frame is a style ({', '.join(FRAME_STYLES)}) and a colour like #c9a24a.")
                    sc["frame"] = {"style": v["style"], "colour": v["colour"]}
                else:
                    raise DesignError(f"Can't change {k!r}.")
            d.save()

    def add_font(self, did: str, filename: str, data: bytes) -> str:
        name = Path(filename).name
        if not name.lower().endswith((".ttf", ".otf")):
            raise DesignError("Fonts are .ttf or .otf files.")
        if not data or len(data) > MAX_FONT:
            raise DesignError("That font file is empty or over 8 MB.")
        try:
            ImageFont.truetype(io.BytesIO(data), 40)
        except OSError:
            raise DesignError("That isn't a font the server can read.")
        with self.lock:
            d = self.design(did)
            folder = d.folder / "fonts"
            folder.mkdir(exist_ok=True)
            safe = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in name)
            (folder / safe).write_bytes(data)
            return safe
