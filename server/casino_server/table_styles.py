"""
Table styles: how a card table looks, as named designs made on the admin page's Tables tab (its designer is
table_styles_web/, the same renderer as the signed-off mockup in docs/table_styles/mockup/).

A style is only looks: the felt, rail, chip tray, printing, betting spots, Jackpot disc, shuffler, shoe, discard
rack, card backs and chips. Where anything sits on the felt never changes. Every card table uses the default
style (House, Mike's design, 2026-10-21) unless `tables` gives it another. Roulette and Craps keep
their own look for now (STYLED_GAMES), so they can't be given one.

Saved in the meta table under "table_styles":
    {"styles": {style_id: {"name": ..., "design": {...}}}, "tables": {table_id: style_id}, "default": style_id}
The four mockup presets (BUILT_IN) are always there and can't be changed or deleted; save a copy to change one.
House is saved the first time it's asked for and can be changed but not deleted.
"""
import copy
import re

from casino_server import floor

KEY = "table_styles"
HOUSE_ID = "house"

# Mike's default table: picked on the mockup, then changed on the test server's Tables tab (2026-10-21).
HOUSE = {
    "felt": {"colour": "#93141f", "texture": "weave", "vignette": 0.95},
    "border": "led", "led": "#ffd28a",
    "rail": {"wood": "rosewood", "armrest": "all", "leather": "#1b1a1a", "bead": "gold"},
    "tray": {"mode": "ledge", "finish": "wood"},
    "shuffler": "black", "shufflerTint": "#cfccc4", "shufflerWood": "match",
    "shoe": "wood", "shoeTint": "#141416", "shoeWood": "match",
    "rack": "wood", "rackTint": "#12305e", "rackWood": "match",
    "spots": "deco",
    "print": {"font": "cinzel", "ink": "#f1e4c4", "accent": "#c9a24a"},
    "back": "lattice", "jackpot": "led", "jackpotRim": "thin", "chips": "clay",
}

# What the built-in presets are written as changes to (Mike's first pick on the mockup), so they stay as they
# were on the mockup whatever House becomes.
_PRESET_BASE = {
    "felt": {"colour": "#93141f", "texture": "velvet", "vignette": 0.55},
    "border": "none", "led": "#9a7bff",
    "rail": {"wood": "mahogany", "armrest": "all", "leather": "#1b1a1a", "bead": "brass"},
    "tray": {"mode": "ledge", "finish": "wood"},
    "shuffler": "black", "shufflerTint": "#3a3e44", "shufflerWood": "match",
    "shoe": "acrylic", "shoeTint": "#141416", "shoeWood": "match",
    "rack": "wood", "rackTint": "#12305e", "rackWood": "match",
    "spots": "double",
    "print": {"font": "cinzel", "ink": "#f1e4c4", "accent": "#c9a24a"},
    "back": "emerald", "jackpot": "gold", "jackpotRim": "thin", "chips": "clay",
}


def _preset(name: str, **changes) -> dict:
    design = copy.deepcopy(_PRESET_BASE)
    for path, value in changes.items():
        *parents, last = path.split("__")
        node = design
        for p in parents:
            node = node[p]
        node[last] = value
    return {"name": name, "design": design}


# The mockup's four starting points (docs/table_styles/mockup/index.html PRESETS).
BUILT_IN = {
    "grand": _preset("Grand Mahogany", felt__texture="weave", border="gilt", led="#ffd28a", rail__armrest="none",
                     shuffler="brass", shoeTint="#6b0f19", rack="clear", rackTint="#1e2328", spots="printed",
                     back="charcoal", jackpotRim="standard"),
    "monte": _preset("Monte Carlo", felt__colour="#0f5b3f", felt__vignette=0.6, border="double", led="#ffd28a",
                     rail__wood="walnut", rail__armrest="player", rail__bead="gold", tray__finish="lid",
                     shuffler="gunmetal", rack="smoked", rackTint="#1e2328", spots="foil",
                     print__font="cormorant", print__ink="#e8d3a0", print__accent="#e0b84e",
                     back="monogram", jackpotRim="standard", chips="ceramic"),
    "deco": _preset("Midnight Deco", felt__colour="#14284a", felt__texture="weave", felt__vignette=0.5, border="deco",
                    led="#ffd28a", rail__wood="rosewood", rail__armrest="none", rail__leather="#1a2234",
                    rail__bead="gold", shuffler="brass", shoe="wood", shoeTint="#6b0f19", rack="wood",
                    rackTint="#1e2328", spots="deco", print__font="josefin", print__ink="#e8d3a0",
                    print__accent="#e0b84e", back="sunburst", jackpotRim="standard"),
    "vegas": _preset("Modern Vegas", felt__colour="#1a3f93", felt__texture="weave", felt__vignette=0.35, border="led",
                     led="#8fd3ff", rail__wood="ebony", rail__bead="chrome", tray__finish="steel",
                     shufflerTint="#1c1e22", rack="smoked", rackTint="#1e2328", spots="double",
                     print__font="montserrat", print__ink="#f4f4f2", print__accent="#8fd3ff",
                     back="stripe", jackpot="led", jackpotRim="standard", chips="ceramic"),
}

WOODS = ("mahogany", "walnut", "wenge", "rosewood", "ebony")
CHOICES = {
    "felt.texture": ("weave", "velvet", "plain"),
    "border": ("none", "pinstripe", "gilt", "double", "deco", "led"),
    "rail.wood": WOODS,
    "rail.armrest": ("none", "player", "all"),
    "rail.bead": ("brass", "gold", "chrome", "none"),
    "tray.mode": ("ledge", "sunk"),
    "tray.finish": ("wood", "steel", "lid"),
    "shuffler": ("gunmetal", "black", "brass"),
    "shufflerWood": ("match",) + WOODS,
    "shoe": ("acrylic", "wood"),
    "shoeWood": ("match",) + WOODS,
    "rack": ("clear", "smoked", "wood"),
    "rackWood": ("match",) + WOODS,
    "spots": ("printed", "double", "foil", "inlaid", "deco"),
    "print.font": ("cinzel", "cormorant", "josefin", "montserrat"),
    "back": ("charcoal", "lattice", "sunburst", "monogram", "stripe", "emerald"),
    "jackpot": ("clear", "gold", "led"),
    "jackpotRim": ("thin", "standard", "heavy"),
    "chips": ("classic", "clay", "ceramic", "stripes", "metal", "house", "vintage"),
}
COLOURS = ("felt.colour", "led", "rail.leather", "print.ink", "print.accent", "shufflerTint", "shoeTint", "rackTint")
RANGES = {"felt.vignette": (0.0, 1.0)}

# Roulette and Craps keep their own look for now.
STYLED_GAMES = ("three_card_poker", "blackjack", "mississippi_stud", "pai_gow_fortune", "pai_gow_face_up",
                "ultimate_texas_holdem", "let_it_ride", "high_card_flush", "baccarat")
# Which of the designer's layouts each game prints.
LAYOUTS = {"three_card_poker": "tcp", "blackjack": "bj", "mississippi_stud": "ms", "pai_gow_fortune": "pgf",
           "pai_gow_face_up": "pgu", "ultimate_texas_holdem": "uth", "let_it_ride": "lir",
           "high_card_flush": "hcf", "baccarat": "bac"}


def styled_tables() -> dict:
    """The tables that take a style: {table_id: {name, game, layout}}."""
    return {tid: {"name": t["name"], "game": t["game"], "layout": LAYOUTS[t["game"]]}
            for tid, t in floor.TABLES.items() if t.get("game") in STYLED_GAMES}


def _get(design: dict, path: str):
    node = design
    for p in path.split("."):
        node = node[p]
    return node


def _set(design: dict, path: str, value) -> None:
    *parents, last = path.split(".")
    node = design
    for p in parents:
        node = node.setdefault(p, {})
    node[last] = value


def clean_design(data: dict) -> dict:
    """A design from the designer, checked, with anything it leaves out taken from House (ValueError says what's wrong)."""
    if not isinstance(data, dict):
        raise ValueError("A design is a set of choices.")
    out = copy.deepcopy(HOUSE)
    for path, allowed in CHOICES.items():
        try:
            value = _get(data, path)
        except (KeyError, TypeError):
            continue
        if value not in allowed:
            raise ValueError(f"{path} is one of {', '.join(allowed)}.")
        _set(out, path, value)
    for path in COLOURS:
        try:
            value = str(_get(data, path)).lower()
        except (KeyError, TypeError):
            continue
        if not re.fullmatch(r"#[0-9a-f]{6}", value):
            raise ValueError(f"{path} is a colour like #93141f.")
        _set(out, path, value)
    for path, (lo, hi) in RANGES.items():
        try:
            value = float(_get(data, path))
        except (KeyError, TypeError):
            continue
        except ValueError:
            raise ValueError(f"{path} is a number.")
        if not lo <= value <= hi:
            raise ValueError(f"{path} is {lo}-{hi}.")
        _set(out, path, round(value, 2))
    return out


def load(store) -> dict:
    """Every style (the built-ins marked `builtin`), which tables have which, and the default."""
    saved = store.get_json(KEY, None)
    if saved is None:
        saved = {"styles": {HOUSE_ID: {"name": "House", "design": copy.deepcopy(HOUSE)}}, "tables": {}, "default": HOUSE_ID}
        store.set_json(KEY, saved)
    styles = {sid: {"name": s["name"], "design": copy.deepcopy(s["design"]), "builtin": True} for sid, s in BUILT_IN.items()}
    for sid, s in (saved.get("styles") or {}).items():
        if sid in BUILT_IN:
            continue
        try:
            design = clean_design(s.get("design") or {})   # (anything added since it was saved comes from House)
        except ValueError:
            design = copy.deepcopy(HOUSE)
        styles[sid] = {"name": str(s.get("name") or sid), "design": design, "builtin": False}
    styles.setdefault(HOUSE_ID, {"name": "House", "design": copy.deepcopy(HOUSE), "builtin": False})
    default = saved.get("default") if saved.get("default") in styles else HOUSE_ID
    known = styled_tables()
    tables = {t: sid for t, sid in (saved.get("tables") or {}).items() if sid in styles and t in known}
    return {"styles": styles, "tables": tables, "default": default}


def _save(store, current: dict) -> dict:
    store.set_json(KEY, {"styles": {sid: {"name": s["name"], "design": s["design"]}
                                    for sid, s in current["styles"].items() if not s["builtin"]},
                         "tables": current["tables"], "default": current["default"]})
    return current


def save_style(store, style_id: str, data: dict) -> dict:
    if not re.fullmatch(r"[a-z0-9_]{1,30}", style_id):
        raise ValueError("A style's id is lower-case letters, digits and _.")
    if style_id in BUILT_IN:
        raise ValueError("The built-in styles stay as they are: save a copy under a new name.")
    current = load(store)
    old = current["styles"].get(style_id)
    name = str(data.get("name", old["name"] if old else "")).strip()
    if not name or len(name) > 40:
        raise ValueError("Give the style a name (up to 40 characters).")
    design = clean_design(data["design"]) if "design" in data else (old["design"] if old else copy.deepcopy(HOUSE))
    current["styles"][style_id] = {"name": name, "design": design, "builtin": False}
    return _save(store, current)


def delete_style(store, style_id: str) -> dict:
    current = load(store)
    if style_id not in current["styles"]:
        raise KeyError(style_id)
    if style_id in BUILT_IN or style_id == HOUSE_ID:
        raise ValueError("House and the built-in styles stay; change House instead.")
    del current["styles"][style_id]
    current["tables"] = {t: s for t, s in current["tables"].items() if s != style_id}
    if current["default"] == style_id:
        current["default"] = HOUSE_ID
    return _save(store, current)


def assign(store, data: dict) -> dict:
    """{"tables": {table_id: style_id, or None for the default}, "default": style_id}, either part optional."""
    current = load(store)
    known = styled_tables()
    if "default" in data:
        if data["default"] not in current["styles"]:
            raise ValueError(f"No table style called {data['default']!r}.")
        current["default"] = data["default"]
    for table_id, style_id in (data.get("tables") or {}).items():
        if table_id not in known:
            raise ValueError(f"{table_id} can't take a table style (Roulette and Craps keep their own look).")
        if style_id in (None, ""):
            current["tables"].pop(table_id, None)
        elif style_id not in current["styles"]:
            raise ValueError(f"No table style called {style_id!r}.")
        else:
            current["tables"][table_id] = style_id
    return _save(store, current)
