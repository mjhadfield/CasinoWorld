"""
The Slot design wizard's later steps (slot_design.py has the designs, Concept and Art). DesignBoard mixes these in,
so every method runs under the board's lock and saves through its Design.

  Value ladder   the chosen symbols ordered into the tiers (W, BS, FS, H1.., M1.., L1..) and the upgrade chain
  Scene          the background (FLUX or uploaded), the logo lettering (rendered here: FLUX can't spell) and the
                 reel frame's style
  Features       which of the library's random features the slot uses, their rates and value tables
  Bonus games    the Trail bonus's recipe and names, the free games, Buy Bonus
  Art slots      the pictures the game draws outside the reels (shared by Features and Bonus games): a board
                 image, or "sym:<id>" to follow a symbol's chosen take
  Specs          a new feature or bonus type, described for building (Build lists them as code tasks)
"""
import io
from pathlib import Path

from PIL import Image, ImageFont

from casino_server import slot_design_art as art
from casino_server.slots import base
from casino_server.slots.variants.armadillo import VARIANT as ARMADILLO

FONTS_DIR = Path(__file__).resolve().parents[2] / "client" / "assets" / "fonts"
FRAME_STYLES = ("metal", "wood", "neon", "glass")
MAX_FONT = 8 * 1024 * 1024


TABLES = ("wild_counts", "wild_reel_counts", "colossal_sizes", "multipliers", "repeats", "instants")
# The pictures drawn outside the reels: id (as the game knows it) -> what it's for, and the step that sets it.
ART_SLOTS = {
    "armadillo": ("The mascot: flies down Wild Reels and walks the bonus trail", "features"),
    "barrel": ("The Instant Win prize", "features"),
    "cylinder": ("The bonus launcher (shows 1 to 6 shots)", "bonuses"),
    "t_coin": ("Trail space: coins", "bonuses"), "t_gold": ("Trail: the prizepot at the end", "bonuses"),
    "t_snake": ("Trail space: the hazard (costs a heart or ends the bonus)", "bonuses"),
    "t_heart": ("Trail space: a heart (saves you from one hazard)", "bonuses"),
    "t_forward": ("Trail space: forward / back", "bonuses"), "t_lightning": ("Trail space: lightning roll", "bonuses"),
    "t_crate": ("Trail space: collect coins nearby", "bonuses"), "t_upgrade": ("Trail space: moves doubled", "bonuses"),
    "t_double": ("Trail space: all coins doubled", "bonuses"),
}
TRAIL_SPACES = ("snake", "heart", "forward", "back", "lightning", "crate")


def _pairs(v, what: str, lo: float = 0.0) -> list:
    """A value table: [[value, weight], ...], every value above lo and every weight above 0."""
    if not isinstance(v, list) or not 1 <= len(v) <= 16:
        raise DesignError(f"{what}: give 1 to 16 value:weight pairs.")
    out = []
    for pair in v:
        try:
            value, weight = float(pair[0]), float(pair[1])
        except (TypeError, ValueError, IndexError):
            raise DesignError(f"{what}: each entry is value:weight, like 2:30.")
        if value <= lo or weight <= 0:
            raise DesignError(f"{what}: values above {lo:g} and weights above 0.")
        out.append([int(value) if value.is_integer() else value, int(weight) if weight.is_integer() else weight])
    return out


def _rate(v, what: str) -> float:
    if not isinstance(v, (int, float)) or not 0 <= v <= 1:
        raise DesignError(f"{what}: a chance from 0 to 1.")
    return round(float(v), 4)


def features_view(d) -> dict:
    f = d.data.get("features", {})
    A = ARMADILLO
    return {"library": list(base.FEATURES), "enabled": f.get("enabled", list(base.FEATURES)),
            "rates": {**A.rates, **f.get("rates", {})}, "free_rates": {**A.free_rates, **f.get("free_rates", {})},
            "tables": {t: f.get("tables", {}).get(t, [list(p) for p in getattr(A, t)]) for t in TABLES},
            "specs": [x for x in d.data.get("specs", []) if x["kind"] == "feature"]}


def bonuses_view(d) -> dict:
    b = d.data.get("bonuses", {})
    t = {**{k: v for k, v in ARMADILLO.trail.items()}, **b.get("trail", {})}
    t["coins"] = [list(p) for p in t["coins"]]
    t["crate_radius"] = [list(p) for p in t["crate_radius"]]
    t.setdefault("name", "TRAIL BONUS")
    t.setdefault("launcher", "THE LAUNCHER")
    t.setdefault("hint", "fire to move along the trail")
    return {"trail": t, "free": {"games": ARMADILLO.free_games, "name": "COMBO FREE GAMES", **b.get("free", {})},
            "buy": {"enabled": True, "cost": ARMADILLO.buy_cost, **b.get("buy", {})},
            "specs": [x for x in d.data.get("specs", []) if x["kind"] == "bonus"]}


def art_view(d) -> dict:
    """Each art slot: what it's for, the step that sets it, what's chosen ("sym:<id>" or a path) and the file it
    comes to now (None until chosen; the mockup then shows Armadillo's)."""
    slots = d.data.get("art_slots", {})
    out = {}
    for key, (label, step) in ART_SLOTS.items():
        v = slots.get(key)
        f = None
        if isinstance(v, str) and v.startswith("sym:"):
            s = next((x for x in d.data["symbols"] if x["id"] == v[4:]), None)
            f = d.chosen_file(s) if s else None
        elif v:
            f = v if d.path(v) else None
        out[key] = {"label": label, "step": step, "value": v, "file": f}
    return out


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
    # ------------------------------------------------------------- Features
    def update_features(self, did: str, ch: dict) -> None:
        with self.lock:
            d = self.design(did)
            f = d.data.setdefault("features", {})
            if "enabled" in ch:
                on = ch["enabled"]
                if not isinstance(on, list) or any(x not in base.FEATURES for x in on):
                    raise DesignError("Features come from the library: " + ", ".join(base.FEATURES) + ".")
                f["enabled"] = [x for x in base.FEATURES if x in on]   # library order: it's the draw order
            for key in ("rates", "free_rates"):
                if key in ch:
                    if not isinstance(ch[key], dict):
                        raise DesignError("Rates are {feature: chance}.")
                    f[key] = {**f.get(key, {}), **{k: _rate(v, k) for k, v in ch[key].items() if k in base.FEATURES}}
            if "tables" in ch:
                lows = {"multipliers": 1, "repeats": 1}
                f["tables"] = {**f.get("tables", {}), **{t: _pairs(v, t.replace("_", " "), lows.get(t, 0))
                                                         for t, v in ch["tables"].items() if t in TABLES}}
            view = features_view(d)
            if not view["enabled"]:
                raise DesignError("Keep at least one feature: the free games promise one every spin.")
            if not any(view["free_rates"][x] > 0 for x in view["enabled"] if x != "repeat"):
                raise DesignError("At least one feature (other than Repeat Win) needs a free-game chance above 0.")
            d.save()

    # ------------------------------------------------------------- Bonus games
    def update_bonuses(self, did: str, ch: dict) -> None:
        with self.lock:
            d = self.design(did)
            b = d.data.setdefault("bonuses", {})
            if "trail" in ch:
                t, cur = ch["trail"], dict(b.get("trail", {}))
                for k in ("name", "launcher", "hint"):
                    if k in t:
                        cur[k] = str(t[k] or "").strip()[:40] or bonuses_view(d)["trail"][k]
                if "length" in t:
                    if not isinstance(t["length"], int) or not 40 <= t["length"] <= 200:
                        raise DesignError("The trail is 40 to 200 spaces long.")
                    cur["length"] = t["length"]
                if "prizepot" in t:
                    if not isinstance(t["prizepot"], int) or not 100 <= t["prizepot"] <= 10000:
                        raise DesignError("The prizepot is 100 to 10,000 times the bet.")
                    cur["prizepot"] = t["prizepot"]
                for k in ("upgrade_chance", "double_chance"):
                    if k in t:
                        cur[k] = _rate(t[k], k.replace("_", " "))
                if "counts" in t:
                    c = t["counts"]
                    if not isinstance(c, dict) or set(c) - set(TRAIL_SPACES) or any(not isinstance(v, int) or not 0 <= v <= 40 for v in c.values()):
                        raise DesignError("Trail spaces: whole numbers from 0 to 40 of " + ", ".join(TRAIL_SPACES) + ".")
                    cur["counts"] = {**bonuses_view(d)["trail"]["counts"], **c}
                for k in ("coins", "crate_radius"):
                    if k in t:
                        cur[k] = _pairs(t[k], k.replace("_", " "))
                length = cur.get("length", bonuses_view(d)["trail"]["length"])
                if sum({**bonuses_view(d)["trail"]["counts"], **cur.get("counts", {})}.values()) > length // 2:
                    raise DesignError("Special spaces can fill at most half the trail; the rest are coins.")
                b["trail"] = cur
            if "free" in ch:
                fr = ch["free"]
                cur = dict(b.get("free", {}))
                if "games" in fr:
                    if not isinstance(fr["games"], int) or not 1 <= fr["games"] <= 20:
                        raise DesignError("Free games: 1 to 20.")
                    cur["games"] = fr["games"]
                if "name" in fr:
                    cur["name"] = str(fr["name"] or "").strip()[:40] or "COMBO FREE GAMES"
                b["free"] = cur
            if "buy" in ch:
                by = ch["buy"]
                cur = dict(b.get("buy", {}))
                if "enabled" in by:
                    cur["enabled"] = bool(by["enabled"])
                if "cost" in by:
                    if not isinstance(by["cost"], int) or not 10 <= by["cost"] <= 500:
                        raise DesignError("Buy Bonus costs 10 to 500 times the bet.")
                    cur["cost"] = by["cost"]
                b["buy"] = cur
            d.save()

    # ------------------------------------------------------------- art slots and specs
    def set_art_slot(self, did: str, key: str, value) -> None:
        if key not in ART_SLOTS:
            raise DesignError(f"There's no art slot {key!r}.")
        with self.lock:
            d = self.design(did)
            if value and str(value).startswith("sym:"):
                d.symbol(str(value)[4:])
            elif value and not d.path(value):
                raise DesignError(f"Not on the board: {value}")
            slots = d.data.setdefault("art_slots", {})
            if value:
                slots[key] = value
            else:
                slots.pop(key, None)
            d.save()

    def add_spec(self, did: str, body: dict) -> dict:
        kind = body.get("kind")
        if kind not in ("feature", "bonus"):
            raise DesignError("A spec is for a feature or a bonus.")
        name, desc = str(body.get("name") or "").strip()[:60], str(body.get("description") or "").strip()[:2000]
        if not name or not desc:
            raise DesignError("Give the new idea a name and describe how it plays.")
        with self.lock:
            d = self.design(did)
            specs = d.data.setdefault("specs", [])
            spec = {"id": max((x["id"] for x in specs), default=0) + 1, "kind": kind, "name": name, "description": desc,
                    "timing": str(body.get("timing") or "")[:40], "art": str(body.get("art") or "").strip()[:600],
                    "status": "spec"}
            specs.append(spec)
            d.save()
            return spec

    def remove_spec(self, did: str, spec_id: int) -> None:
        with self.lock:
            d = self.design(did)
            specs = d.data.get("specs", [])
            if not any(x["id"] == spec_id for x in specs):
                raise DesignError("There's no such spec.")
            d.data["specs"] = [x for x in specs if x["id"] != spec_id]
            d.save()

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
