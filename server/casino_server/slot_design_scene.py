"""
The Scene step's skins: the whole look of a slot's screen. A design keeps any number of skins
(design.json scene.skins, by slug) and plays the chosen one (scene.skin). The wizard's mockup and the Godot slot
screen draw the same skin; docs/slots/scenes.md is the format's reference and how Claude designs one.

A skin is:
  name, by, note   what it's called, who made it ("house", "mike" or "claude") and the designer's notes
  base             the family of shapes: "classic" (the four frame styles: Armadillo's look) or "lcars"
  frame, deck      classic only: the frame's style and edge colour, the deck's style and tint ("frame": match it)
  colours          the screen's eleven tones (THEME_DEFAULTS: text, accent, shade, win, spin, ...)
  palette          a family's own tones: hl (the highlight), a b c d (its blocks), warn, glass, and the jackpot
                   tiers (grand major minor mini)
  glass            frosted panels: opacity, sheen, edge (px) and blur (px of the background behind them)
  parts            lcars only: a shape and colours for each part of the screen (PARTS)
  decor            lcars only: free shapes in fixed places (elbows, bars, pills, text, readouts), under or over
                   the parts; never over the reels, meters, controls or the side panels' contents (PROTECTED)
  fonts            display and ui: a font file, or "@lettering" for the Art step's lettering font
  texts            the screen's own words, relabelled (TEXTS)
Colours in palette, parts and decor are a name ("hl", "a", "gold", "cream", ...) or a colour like #8fd3ff.

The Brief (scene.brief) is what Mike asks Claude for: words and reference pictures (scene/brief_<n>.png). A Claude
Code session answers it with a new skin (put_skin, by "claude"); the skin keeps a copy of how Claude made it
("original"), so Reset brings it back after tweaks.

The house's scenes (HOUSE) are offered to every design under New: the Classic and LCARS starters, and finished
skins kept in scene_presets.json. New copies one into the design, as Mike's to change.
"""
import copy
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageFilter

from casino_server import slot_design_art as art
from casino_server.slot_design_steps import (DECK_STYLES, FONT_DEFAULTS, FRAME_STYLES, THEME_DEFAULTS, DesignError,
                                             _font_path, _fonts)

BASES = ("classic", "lcars")
BY = ("house", "mike", "claude")
PALETTE = ("hl", "a", "b", "c", "d", "warn", "glass", "grand", "major", "minor", "mini")
LETTERING = "@lettering"
# Every part's shapes (the first is the default) and the colours it takes.
PARTS = {
    "meter": (("tab", "pill", "glass"), ("fill", "text")),           # the jackpot meters; fill "tier": each its own
    "panel": (("elbow", "glass"), ("top", "bottom", "spine", "fill", "edge", "title")),   # the side panels, pop-ups
    "frame": (("elbow", "glass"), ("top", "bottom", "edge", "fill")),                     # the reel well
    "box": (("pill", "glass"), ("fill", "edge", "label", "value")),  # credit/bet/win, the feature list, the info boxes
    "button": (("pill", "half"), ("fill", "on", "text")),
    "spin": (("pill", "disc"), ("fill", "text")),
    "deck": (("elbow", "bar"), ("fill", "edge", "accent")),
}
DECOR_KINDS = ("elbow", "bar", "pill", "text", "readout")
CORNERS = ("tl", "tr", "bl", "br")
ROUNDS = ("none", "left", "right", "both")
ALIGNS = ("left", "center", "right")
TOKENS = ("{name}", "{stardate}", "{date}", "{time}")
MAX_DECOR = 60
# The screen's own words a skin can relabel, with the house's words.
TEXTS = {"spin": "SPIN", "stop": "STOP", "fire": "FIRE", "sail": "SAIL", "credit": "CREDIT", "bet": "BET", "win": "WIN",
         "info": "INFO", "turbo": "TURBO", "auto": "AUTO", "cashout": "CASH OUT", "features": "RANDOM FEATURES",
         "buy": "BUY BONUS", "tagline": "GOOD LUCK", "collect": "COLLECT", "settings": "SETTINGS"}
SAFE = (4, 4, 1276, 716)
# Where "over" decor may not go: the reels, the meters, the deck's readouts and buttons, the side panels' contents.
PROTECTED = [(265, 128, 1015, 576), (18, 14, 268, 84), (278, 14, 488, 84), (792, 14, 1002, 84), (1012, 14, 1262, 84),
             (20, 628, 714, 710), (730, 640, 1026, 696), (1062, 614, 1162, 714), (1172, 640, 1268, 696),
             (30, 120, 230, 600), (1050, 120, 1250, 600)]

CLASSIC = {"name": "Classic", "by": "house", "base": "classic", "note": "",
           "frame": {"style": "metal", "colour": "#c9a24a"}, "deck": {"style": "frame", "colour": None},
           "colours": dict(THEME_DEFAULTS), "palette": {}, "glass": {}, "parts": {}, "decor": [],
           "fonts": dict(FONT_DEFAULTS), "texts": {}}
# LCARS: navy glass and light-blue light, after the modern LCARS phone mockups. What a new LCARS skin starts from.
LCARS_PALETTE = {"hl": "#9fe3ff", "a": "#4a7cab", "b": "#6aa5cf", "c": "#a6d3dc", "d": "#22446a", "warn": "#f5a623",
                 "glass": "#08131f", "grand": "#f2a33a", "major": "#b98fd6", "minor": "#7fc4c9", "mini": "#6f9fd8"}
LCARS_COLOURS = {"gold": "#9fdcff", "goldHi": "#e6f6ff", "goldLo": "#2c5a85", "edge": "#5f9ec4", "cream": "#e4f2ff",
                 "muted": "#7fa3bf", "ink": "#04101c", "shade": "#030a14", "win": "#ffd27a", "spin": "#5f9ec4",
                 "alert": "#c8453a"}
LCARS = {"name": "LCARS", "by": "house", "base": "lcars", "note": "",
         "frame": {"style": "glass", "colour": "#9fdcff"}, "deck": {"style": "frame", "colour": None},
         "colours": LCARS_COLOURS, "palette": LCARS_PALETTE,
         "glass": {"opacity": 0.55, "sheen": 0.12, "edge": 1.5, "blur": 14},
         "parts": {"meter": {"shape": "tab", "fill": "tier", "text": "goldHi"},
                   "panel": {"shape": "elbow", "top": "a", "bottom": "c", "spine": ["b", "d", "c"], "fill": "glass", "edge": "hl", "title": "hl"},
                   "frame": {"shape": "elbow", "top": "a", "bottom": "c", "edge": "hl", "fill": "glass"},
                   "box": {"shape": "pill", "fill": "glass", "edge": "b", "label": "c", "value": "goldHi"},
                   "button": {"shape": "pill", "fill": "b", "on": "warn", "text": "ink"},
                   "spin": {"shape": "pill", "fill": "hl", "text": "ink"},
                   "deck": {"shape": "elbow", "fill": "d", "edge": "hl", "accent": "a"}},
         "decor": [], "fonts": {"display": LETTERING, "ui": LETTERING}, "texts": {}}
STARTERS = {"classic": CLASSIC, "lcars": LCARS}
# The house's scenes, offered to every design under New: the two starters, then the finished ones
# (scene_presets.json, whole skins made for any slot: TNG, DS9 and ENT LCARS).
HOUSE = {"classic": CLASSIC, "lcars": LCARS,
         **{re.sub(r"[^a-z0-9]+", "-", sk["name"].lower()).strip("-"): sk
            for sk in json.loads((Path(__file__).resolve().parent / "scene_presets.json").read_text())}}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:40] or "scene"


def _free_slug(taken, name: str) -> str:
    """name's slug, or name-2, name-3, ... when that's taken."""
    base, n = _slug(name), 2
    slug = base
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    return slug


# ------------------------------------------------------------------ checking a skin
def _num(v, what: str, lo: float, hi: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
        raise DesignError(f"{what}: a number from {lo:g} to {hi:g}.")
    return v


def _ref(v, names: set, what: str, extra=()) -> str:
    """A colour reference: a name the skin knows, or a colour like #8fd3ff."""
    if isinstance(v, str) and (v in names or v in extra or art.is_colour(v)):
        return v
    raise DesignError(f"{what}: a colour like #8fd3ff or one of the skin's names ({', '.join(sorted(names))}).")


def _overlaps(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def check_decor(items, names: set) -> list:
    if not isinstance(items, list) or len(items) > MAX_DECOR:
        raise DesignError(f"Decor is a list of at most {MAX_DECOR} shapes.")
    out, ids = [], set()
    for i, it in enumerate(items):
        if not isinstance(it, dict) or it.get("kind") not in DECOR_KINDS:
            raise DesignError(f"Decor {i + 1}: a kind ({', '.join(DECOR_KINDS)}).")
        k, what = it["kind"], f"Decor {it.get('id') or i + 1} ({it['kind']})"
        x = {"id": str(it.get("id") or f"{k}{i + 1}")[:24], "kind": k, "layer": it.get("layer", "under"),
             "show": it.get("show", True) is not False, "alpha": _num(it.get("alpha", 1), f"{what} alpha", 0, 1)}
        if x["id"] in ids:
            raise DesignError(f"{what}: another shape already has the id {x['id']!r}.")
        ids.add(x["id"])
        if x["layer"] not in ("under", "over"):
            raise DesignError(f"{what}: layer is under or over.")
        for f in ("x", "y", "w", "h"):
            x[f] = _num(it.get(f), f"{what} {f}", -2000, 2000)
        if x["w"] <= 0 or x["h"] <= 0:
            raise DesignError(f"{what}: w and h above 0.")
        box = (x["x"], x["y"], x["x"] + x["w"], x["y"] + x["h"])
        if box[0] < SAFE[0] or box[1] < SAFE[1] or box[2] > SAFE[2] or box[3] > SAFE[3]:
            raise DesignError(f"{what}: stay inside the screen's safe area, {SAFE[0]},{SAFE[1]} to {SAFE[2]},{SAFE[3]}.")
        if x["layer"] == "over" and any(_overlaps(box, p) for p in PROTECTED):
            raise DesignError(f"{what}: over the reels, meters, controls or side panels' contents. Put it under, or move it.")
        x["colour"] = _ref(it.get("colour", "hl"), names, f"{what} colour")
        if k == "elbow":
            x["corner"] = it.get("corner", "tl")
            if x["corner"] not in CORNERS:
                raise DesignError(f"{what}: corner is one of {', '.join(CORNERS)}.")
            x["arm"] = _num(it.get("arm", min(x["w"], 40)), f"{what} arm", 1, x["w"])
            x["bar"] = _num(it.get("bar", min(x["h"], 16)), f"{what} bar", 1, x["h"])
            x["r"] = _num(it.get("r", min(x["w"], x["h"], 60)), f"{what} r", 0, min(x["w"], x["h"]))
        if k in ("bar", "pill"):
            x["round"] = it.get("round", "both" if k == "pill" else "none")
            if x["round"] not in ROUNDS:
                raise DesignError(f"{what}: round is one of {', '.join(ROUNDS)}.")
        if k in ("pill", "text"):
            x["text"] = str(it.get("text", ""))[:60]
            x["font"] = it.get("font", "display")
            if x["font"] not in ("display", "ui"):
                raise DesignError(f"{what}: font is display or ui.")
            x["size"] = _num(it.get("size", round(x["h"] * (0.6 if k == "pill" else 0.85))), f"{what} size", 6, 200)
            x["align"] = it.get("align", "right" if k == "pill" else "left")
            if x["align"] not in ALIGNS:
                raise DesignError(f"{what}: align is left, center or right.")
            if k == "pill":
                x["text_colour"] = _ref(it.get("text_colour", "ink"), names, f"{what} text colour")
        if k == "readout":
            cells = it.get("cells", [2, 5, 2])
            if not isinstance(cells, list) or not 1 <= len(cells) <= 10 or not all(isinstance(c, int) and 1 <= c <= 8 for c in cells):
                raise DesignError(f"{what}: cells is a list of 1 to 10 digit counts (1 to 8 each).")
            x["cells"] = cells
            cols = it.get("colours", [x["colour"]])
            if not isinstance(cols, list) or not 1 <= len(cols) <= 10:
                raise DesignError(f"{what}: colours is a list of 1 to 10 colours.")
            x["colours"] = [_ref(c, names, f"{what} colours") for c in cols]
            x["text_colour"] = _ref(it.get("text_colour", "ink"), names, f"{what} text colour")
            x["tick"] = _num(it.get("tick", 2), f"{what} tick", 0, 60)
            x["seed"] = int(_num(it.get("seed", i + 1), f"{what} seed", 0, 1e9))
        out.append(x)
    return out


def check_skin(sk: dict, fonts: list[str]) -> dict:
    """A whole skin, checked and filled in from its family's starter: what's saved and drawn."""
    if not isinstance(sk, dict):
        raise DesignError("A skin is an object (docs/slots/scenes.md).")
    base_id = sk.get("base", "classic")
    if base_id not in BASES:
        raise DesignError(f"A skin's base is one of {', '.join(BASES)}.")
    unknown = set(sk) - set(CLASSIC) - {"original", "at"}
    if unknown:
        raise DesignError(f"A skin has no {', '.join(sorted(unknown))}.")
    start = STARTERS[base_id]
    out = {"name": str(sk.get("name") or start["name"]).strip()[:40] or start["name"], "by": sk.get("by", "mike"),
           "base": base_id, "note": str(sk.get("note", ""))[:2000]}
    if out["by"] not in BY:
        raise DesignError(f"A skin is by {', '.join(BY)}.")
    cols = {**start["colours"], **(sk.get("colours") or {})}
    if set(cols) - set(THEME_DEFAULTS) or not all(art.is_colour(c) for c in cols.values()):
        raise DesignError("A skin's colours are " + ", ".join(THEME_DEFAULTS) + ", each like #f4c94f.")
    out["colours"] = cols
    pal = {**start["palette"], **(sk.get("palette") or {})}
    if set(pal) - set(PALETTE) or not all(art.is_colour(c) for c in pal.values()):
        raise DesignError("A skin's palette is " + ", ".join(PALETTE) + ", each like #9fdcff.")
    out["palette"] = pal
    names = set(cols) | set(pal)
    fr = {**start["frame"], **(sk.get("frame") or {})}
    if fr.get("style") not in FRAME_STYLES or not art.is_colour(fr.get("colour")):
        raise DesignError(f"A frame is a style ({', '.join(FRAME_STYLES)}) and a colour like #c9a24a.")
    dk = {**start["deck"], **(sk.get("deck") or {})}
    if dk.get("style") not in DECK_STYLES or not (dk.get("colour") is None or art.is_colour(dk["colour"])):
        raise DesignError(f"A deck is a style ({', '.join(DECK_STYLES)}) and a colour like #c9a24a, or none.")
    out["frame"], out["deck"] = {"style": fr["style"], "colour": fr["colour"]}, {"style": dk["style"], "colour": dk.get("colour")}
    gl = {**start["glass"], **(sk.get("glass") or {})}
    lim = {"opacity": 1, "sheen": 1, "edge": 6, "blur": 40}
    if set(gl) - set(lim):
        raise DesignError("Glass is opacity, sheen, edge and blur.")
    out["glass"] = {k: _num(v, f"Glass {k}", 0, lim[k]) for k, v in gl.items()}
    parts = {}
    given = sk.get("parts") or {}
    if set(given) - set(PARTS):
        raise DesignError("A skin's parts are " + ", ".join(PARTS) + ".")
    for p, (shapes, keys) in PARTS.items():
        if base_id == "classic" and not given.get(p):
            continue
        v = {**start["parts"].get(p, {}), **(given.get(p) or {})}
        v.setdefault("shape", shapes[0])
        if v["shape"] not in shapes:
            raise DesignError(f"The {p}'s shape is one of {', '.join(shapes)}.")
        if set(v) - set(keys) - {"shape"}:
            raise DesignError(f"The {p} takes {', '.join(keys)}.")
        for k, c in v.items():
            if k == "shape":
                continue
            if k == "spine":
                if not isinstance(c, list) or not 1 <= len(c) <= 4:
                    raise DesignError("The panel's spine is a list of 1 to 4 colours.")
                v[k] = [_ref(x, names, "The panel's spine") for x in c]
            else:
                v[k] = _ref(c, names, f"The {p}'s {k}", ("tier",) if (p, k) == ("meter", "fill") else ())
        parts[p] = v
    out["parts"] = parts
    out["decor"] = check_decor(sk.get("decor", start["decor"]), names)
    fo = {**start["fonts"], **(sk.get("fonts") or {})}
    if set(fo) - set(FONT_DEFAULTS):
        raise DesignError("A skin's fonts are display and ui.")
    for role, f in fo.items():
        if f != LETTERING and f not in fonts:
            raise DesignError(f"There's no font {f!r}: add it on the Scene step.")
    out["fonts"] = fo
    tx = sk.get("texts") or {}
    if set(tx) - set(TEXTS):
        raise DesignError("A skin relabels " + ", ".join(TEXTS) + ".")
    out["texts"] = {k: str(v).strip()[:24] for k, v in tx.items() if str(v).strip()}
    if isinstance(sk.get("original"), dict):
        out["original"] = sk["original"]
    if sk.get("at"):
        out["at"] = str(sk["at"])[:32]
    return out


# ------------------------------------------------------------------ a design's skins
def migrate(d: dict) -> None:
    """Older designs kept the frame, deck, colours and fonts loose (Scene's frame/deck, Sprites' colours/fonts): they
    become the design's Classic skin, chosen."""
    sc = d.setdefault("scene", {})
    if "skins" in sc:
        return
    sp = d.get("sprites", {})
    classic = copy.deepcopy(CLASSIC)
    classic["frame"] = sc.pop("frame", None) or classic["frame"]
    classic["deck"] = sc.pop("deck", None) or classic["deck"]
    classic["colours"] = {**THEME_DEFAULTS, **sp.pop("colours", {})}
    classic["fonts"] = {**FONT_DEFAULTS, **sp.pop("fonts", {})}
    sc["skins"] = {"classic": classic}
    sc["skin"] = "classic"


def chosen(d) -> tuple[str, dict]:
    sc = d.data["scene"]
    slug = sc.get("skin") if sc.get("skin") in sc["skins"] else next(iter(sc["skins"]))
    return slug, sc["skins"][slug]


def lettering_font(d) -> str:
    """The Art step's lettering font, as set there; unset, the chosen skin's own display font or the house's."""
    let = d.data.get("lettering", {}).get("special_font")
    if let:
        return let
    _, sk = chosen(d)
    f = sk["fonts"].get("display")
    return f if f and f != LETTERING else FONT_DEFAULTS["display"]


def look(d) -> dict:
    """What the screen draws now: the chosen skin with its fonts resolved to files (and the eleven colours and two
    fonts the Sprites step, the build and the client's theme read)."""
    slug, sk = chosen(d)
    let = lettering_font(d)
    fonts = {role: (let if f == LETTERING else f) for role, f in sk["fonts"].items()}
    out = {k: v for k, v in sk.items() if k not in ("original", "at")}
    return {"slug": slug, "skin": {**out, "fonts": fonts}, "colours": sk["colours"], "fonts": fonts}


def scene_view(d) -> dict:
    sc = d.data.get("scene", {})
    folder = d.folder / "scene"
    listed = lambda pattern: sorted((f"scene/{p.name}" for p in folder.glob(pattern)),
                                    key=lambda p: int(Path(p).stem.split("_")[-1])) if folder.is_dir() else []
    binned = set(sc.get("binned", []))
    bgs, logos, refs = listed("bg_*.png"), listed("logo_*.png"), listed("brief_*.png")
    lk = look(d)
    skins = [{"slug": k, "name": v["name"], "by": v["by"], "base": v["base"], "at": v.get("at"),
              "has_original": "original" in v} for k, v in sc["skins"].items() if k not in sc.get("binned_skins", [])]
    brief = {"text": "", "refs": [], "status": None, **sc.get("brief", {})}
    brief["refs"] = [p for p in brief["refs"] if p in refs]
    return {"background": sc.get("background"), "logo": sc.get("logo", {}),
            "frame": lk["skin"]["frame"], "deck": lk["skin"]["deck"],
            "backgrounds": [p for p in bgs if p not in binned], "logos": [p for p in logos if p not in binned],
            "bin": {"backgrounds": [p for p in bgs if p in binned], "logos": [p for p in logos if p in binned],
                    "skins": [{"slug": k, "name": sc["skins"][k]["name"]} for k in sc.get("binned_skins", []) if k in sc["skins"]]},
            "fonts": _fonts(d), "frame_styles": list(FRAME_STYLES), "deck_styles": list(DECK_STYLES),
            "skin": lk["slug"], "skins": skins, "look": lk, "edit": {k: v for k, v in sc["skins"][lk["slug"]].items() if k != "original"},
            "brief": brief, "lettering_font": lettering_font(d),
            "house": [{"id": k, "name": v["name"], "base": v["base"]} for k, v in HOUSE.items()],
            "schema": {"bases": list(BASES), "palette": list(PALETTE), "parts": {p: {"shapes": list(s), "colours": list(k)} for p, (s, k) in PARTS.items()},
                       "decor": list(DECOR_KINDS), "texts": TEXTS, "colours": list(THEME_DEFAULTS), "protected": PROTECTED, "safe": SAFE}}


def bake_glass(src: Path, out: Path, blur: float) -> None:
    """The background, blurred: what the glass panels show through them (the client can't blur at draw time)."""
    im = Image.open(src).convert("RGB").resize((640, 360), Image.LANCZOS)
    im.filter(ImageFilter.GaussianBlur(max(1.0, blur / 2))).save(out, optimize=True)


class SceneMixin:
    """The Scene step's skins and Brief (DesignBoard mixes this in, like StepsMixin)."""

    def _skin(self, d, slug: str) -> dict:
        sk = d.data["scene"]["skins"].get(slug)
        if not sk:
            raise DesignError(f"There's no scene {slug!r}.")
        return sk

    def put_skin(self, did: str, slug: str | None, skin: dict) -> str:
        """Save a whole skin (Claude's designs come this way): a new slug, or over one that's there. Claude's keep a
        copy as made, for Reset."""
        import datetime
        with self.lock:
            d = self.design(did)
            sk = check_skin(skin, _fonts(d))
            sc = d.data["scene"]
            slug = _slug(slug or sk["name"])
            sk["at"] = datetime.datetime.now().isoformat(timespec="seconds")
            if sk["by"] == "claude":
                sk["original"] = {k: v for k, v in sk.items() if k not in ("original", "at")}
                if sc.get("brief", {}).get("status") == "waiting":
                    sc["brief"]["status"] = "answered"
                    sc["brief"]["answer"] = slug
            sc["skins"][slug] = sk
            if slug in sc.get("binned_skins", []):
                sc["binned_skins"].remove(slug)
            d.save()
            return slug

    def update_skin(self, did: str, slug: str, ch: dict) -> None:
        """Tweak a skin: each given key replaces the skin's (colours, palette, glass, fonts, texts and each part merge
        into theirs; decor is the whole list)."""
        if not isinstance(ch, dict) or not ch:
            raise DesignError("Say what to change.")
        with self.lock:
            d = self.design(did)
            sk = copy.deepcopy(self._skin(d, slug))
            for k, v in ch.items():
                if k in ("colours", "palette", "glass", "fonts", "texts", "frame", "deck") and isinstance(v, dict):
                    sk[k] = {**sk.get(k, {}), **v}
                    if k == "texts":
                        sk[k] = {t: w for t, w in sk[k].items() if w}
                elif k == "parts" and isinstance(v, dict):
                    sk["parts"] = {**sk.get("parts", {}), **{p: {**sk.get("parts", {}).get(p, {}), **(pv or {})} for p, pv in v.items()}}
                elif k in ("name", "note", "decor", "base"):
                    sk[k] = v
                    if k == "base":   # a new family starts from its starter's parts and palette
                        st = STARTERS[v] if v in STARTERS else None
                        if st is None:
                            raise DesignError(f"A skin's base is one of {', '.join(BASES)}.")
                        sk["parts"], sk["palette"], sk["glass"] = copy.deepcopy(st["parts"]), {**st["palette"], **sk.get("palette", {})}, {**st["glass"], **sk.get("glass", {})}
                else:
                    raise DesignError(f"Can't change a skin's {k!r}.")
            d.data["scene"]["skins"][slug] = check_skin(sk, _fonts(d))
            d.save()

    def skin_action(self, did: str, slug: str, action: str, body: dict) -> str | None:
        with self.lock:
            d = self.design(did)
            sc = d.data["scene"]
            sk = self._skin(d, slug)
            binned = sc.setdefault("binned_skins", [])
            if action == "choose":
                if slug in binned:
                    raise DesignError("That scene is in the Bin: restore it first.")
                sc["skin"] = slug
            elif action == "duplicate":
                name = str(body.get("name") or f"{sk['name']} copy").strip()[:40]
                new = _free_slug(sc["skins"], name)
                sc["skins"][new] = {**{k: v for k, v in copy.deepcopy(sk).items() if k not in ("original", "at")},
                                    "name": name, "by": "mike"}
                sc["skin"] = new
                slug = new
            elif action == "rename":
                name = str(body.get("name") or "").strip()[:40]
                if not name:
                    raise DesignError("Give the scene a name.")
                sk["name"] = name
            elif action == "new":   # a fresh skin from one of the house's (a starter or a finished scene)
                house = body.get("house") or body.get("base")
                if house not in HOUSE:
                    raise DesignError(f"A new scene starts from one of {', '.join(HOUSE)}.")
                st = copy.deepcopy(HOUSE[house])
                st["by"] = "mike"
                if house == "classic":
                    st["colours"], st["fonts"] = dict(sk["colours"]), dict(sk["fonts"])
                new = _free_slug(sc["skins"], st["name"])
                if new != _slug(st["name"]):
                    st["name"] = f"{st['name']} {new.rsplit('-', 1)[1]}"
                sc["skins"][new] = check_skin(st, _fonts(d))
                sc["skin"] = new
                slug = new
            elif action == "bin":
                if len([k for k in sc["skins"] if k not in binned]) <= 1:
                    raise DesignError("That's the only scene: keep one.")
                if slug not in binned:
                    binned.append(slug)
                if sc["skin"] == slug:
                    sc["skin"] = next(k for k in sc["skins"] if k not in binned)
            elif action == "restore":
                if slug not in binned:
                    raise DesignError("That scene isn't in the Bin.")
                binned.remove(slug)
            elif action == "reset":
                if "original" not in sk:
                    raise DesignError("Only Claude's scenes have a version to go back to.")
                sc["skins"][slug] = check_skin({**copy.deepcopy(sk["original"]), "original": sk["original"], "at": sk.get("at")}, _fonts(d))
            else:
                raise DesignError(f"No scene action {action!r}.")
            d.save()
            return slug

    def update_brief(self, did: str, body: dict) -> None:
        """The Brief for Claude: words, which reference pictures go with it, and asking (status "waiting")."""
        import datetime
        with self.lock:
            d = self.design(did)
            sc = d.data["scene"]
            br = sc.setdefault("brief", {"text": "", "refs": [], "status": None})
            if "text" in body:
                br["text"] = str(body["text"] or "")[:4000]
            if "refs" in body:
                refs = body["refs"] or []
                if not isinstance(refs, list) or not all(isinstance(p, str) and p.startswith("scene/brief_") and d.path(p) for p in refs):
                    raise DesignError("Pick the Brief's own reference pictures.")
                br["refs"] = refs
            if body.get("ask"):
                if not br["text"].strip():
                    raise DesignError("Write what you'd like first.")
                br["status"], br["asked"] = "waiting", datetime.datetime.now().isoformat(timespec="seconds")
                br.pop("answer", None)
            if body.get("withdraw"):
                br["status"] = None
            d.save()

    def add_brief_ref(self, did: str, filename: str, data: bytes) -> str:
        with self.lock:
            d = self.design(did)
            im = self._read_image(data).convert("RGB")
            im.thumbnail((1600, 1600), Image.LANCZOS)
            out = self._next_scene(d, "brief")
            im.save(d.folder / out, optimize=True)
            br = d.data["scene"].setdefault("brief", {"text": "", "refs": [], "status": None})
            br["refs"] = br.get("refs", []) + [out]
            d.save()
            return out
