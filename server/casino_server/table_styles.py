"""
Table styles: how a table looks, as named designs made on the admin page's Tables tab (its designer is
admin_web/tables/, the same renderer as the signed-off mockup in docs/table_styles/mockup/).

There are three kinds, each with its own styles, default and placement, because the tables have different
parts: the card tables ("cards"), Roulette ("roulette") and Craps ("craps"). A style is only looks: for a
card table the felt, rail, chip tray, printing, betting spots, Jackpot disc, shuffler, shoe, discard rack, card
backs and chips; for Roulette the felt, rail, printing, number colours, float and wheel; for Craps the felt, rail,
printing, rubber, chip rack and dice. Where anything sits on the felt never changes. Every table uses its kind's
default style (House) unless `tables` gives it another. Card House is Mike's design (2026-10-21); Roulette's
and Craps' House is how those tables looked before they took styles.

Saved in the meta table under each kind's KEY:
    {"styles": {style_id: {"name": ..., "design": {...}}}, "tables": {table_id: style_id}, "default": style_id}
Each kind's presets (BUILT_IN) are always there and can't be changed or deleted; save a copy to change one.
House is saved the first time it's asked for and can be changed but not deleted.
"""
import copy
import re

from casino_server import floor, plan, seating

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
    "spots": "deco", "glow": "#ffdf9e",
    "print": {"font": "cinzel", "ink": "#f1e4c4", "primary": "#f1e4c4", "side": "#c9a24a", "accent": "#c9a24a"},
    "back": "lattice", "backColour": "#8e1a22", "cardColour": "#f4f2ec", "front": "classic", "suits": "two",
    "jackpot": "led", "jackpotRim": "thin", "chips": "clay",
    "chairs": {"frame": "brass", "upholstery": "#2a2320"},
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
    "spots": "double", "glow": "#ffdf9e",
    "print": {"font": "cinzel", "ink": "#f1e4c4", "accent": "#c9a24a"},
    "back": "emerald", "cardColour": "#f4f2ec", "front": "classic", "suits": "two",
    "jackpot": "gold", "jackpotRim": "thin", "chips": "clay",
    "chairs": {"frame": "brass", "upholstery": "#2a2320"},
}

# Each card back's colour before the colour was its own choice (Card2D.BACKS): what a design saved then takes.
# Emerald was the lattice in green.
BACK_MAIN = {"charcoal": "#34373c", "lattice": "#8e1a22", "sunburst": "#4d1616", "monogram": "#5a1322", "stripe": "#141414",
             "emerald": "#145238"}


def _preset(name: str, base: dict | None = None, **changes) -> dict:
    design = copy.deepcopy(_PRESET_BASE if base is None else base)
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
                     print__font="cormorant", print__ink="#e8d3a0", print__accent="#e0b84e", glow="#f0c75e",
                     back="monogram", jackpotRim="standard", chips="ceramic"),
    "deco": _preset("Midnight Deco", felt__colour="#14284a", felt__texture="weave", felt__vignette=0.5, border="deco",
                    led="#ffd28a", rail__wood="rosewood", rail__armrest="none", rail__leather="#1a2234",
                    rail__bead="gold", shuffler="brass", shoe="wood", shoeTint="#6b0f19", rack="wood",
                    rackTint="#1e2328", spots="deco", print__font="josefin", print__ink="#e8d3a0",
                    print__accent="#e0b84e", back="sunburst", jackpotRim="standard"),
    "vegas": _preset("Modern Vegas", felt__colour="#1a3f93", felt__texture="weave", felt__vignette=0.35, border="led",
                     led="#8fd3ff", rail__wood="ebony", rail__bead="chrome", tray__finish="steel",
                     shufflerTint="#1c1e22", rack="smoked", rackTint="#1e2328", spots="double",
                     print__font="montserrat", print__ink="#f4f4f2", print__accent="#8fd3ff", glow="#8fd3ff",
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
    "back": ("charcoal", "lattice", "sunburst", "monogram", "stripe"),
    "front": ("classic", "jumbo", "vintage", "minimal"),
    "suits": ("two", "four"),
    "jackpot": ("clear", "gold", "led"),
    "jackpotRim": ("thin", "standard", "heavy"),
    "chips": ("classic", "clay", "ceramic", "stripes", "metal", "house", "vintage"),
    "chairs.frame": seating.CHOICES["frame"],
}
# The printing's colours: ink (titles, rules, follow-up bets like Play), primary (the bet every hand must have: the
# Ante, Blackjack's bet), side (the optional bonus bets) and accent, the trim (gilt, double and deco borders, the
# House chips, the Master Table's crest). The glow is the light round the betting spots that are waiting for your
# chips (the main bet, then the side bets).
COLOURS = ("felt.colour", "led", "rail.leather", "print.ink", "print.primary", "print.side", "print.accent", "glow",
           "shufflerTint", "shoeTint", "rackTint", "backColour", "cardColour", "chairs.upholstery")
RANGES = {"felt.vignette": (0.0, 1.0)}

CARD_GAMES = ("three_card_poker", "blackjack", "mississippi_stud", "pai_gow_fortune", "pai_gow_face_up",
              "ultimate_texas_holdem", "let_it_ride", "high_card_flush", "baccarat", "master_table")
# Which of the designer's layouts each game prints.
LAYOUTS = {"three_card_poker": "tcp", "blackjack": "bj", "mississippi_stud": "ms", "pai_gow_fortune": "pgf",
           "pai_gow_face_up": "pgu", "ultimate_texas_holdem": "uth", "let_it_ride": "lir",
           "high_card_flush": "hcf", "baccarat": "bac", "roulette": "rou", "craps": "crp", "master_table": "mt"}

# ---------------------------------------------------------------- Roulette
# How the roulette table looked before it took a style (TableFelt's Mahogany & Brass).
ROULETTE_HOUSE = {
    "felt": {"colour": "#93141f", "texture": "grain", "vignette": 0.3},
    "border": "none", "led": "#ffd28a",
    "rail": {"wood": "mahogany", "armrest": "none", "leather": "#2a140a", "bead": "brass"},
    "print": {"font": "cinzel", "ink": "#f1e4c4", "accent": "#c9a24a"},
    "numbers": {"red": "#e0453d", "black": "#1a0d0b", "zero": "#1f8a52"},
    "float": "wood",
    "wheel": {"wood": "match", "metal": "brass"},
    "chairs": {"frame": "brass", "upholstery": "#2a2320"},
}
ROULETTE_BUILT_IN = {
    "grand": _preset("Grand Mahogany", ROULETTE_HOUSE, felt__texture="weave", felt__vignette=0.55, border="gilt"),
    "monte": _preset("Monte Carlo", ROULETTE_HOUSE, felt__colour="#0f5b3f", felt__texture="velvet", felt__vignette=0.6,
                     border="double", rail__wood="walnut", rail__bead="gold", print__font="cormorant",
                     print__ink="#e8d3a0", print__accent="#e0b84e", numbers__red="#c8283a", float="lid",
                     wheel__metal="gold"),
    "deco": _preset("Midnight Deco", ROULETTE_HOUSE, felt__colour="#14284a", felt__texture="weave", felt__vignette=0.5,
                    border="deco", rail__wood="rosewood", rail__bead="gold", print__font="josefin", print__ink="#e8d3a0",
                    print__accent="#e0b84e", numbers__red="#b3263a", numbers__black="#0e0f14", wheel__metal="gold"),
    "vegas": _preset("Modern Vegas", ROULETTE_HOUSE, felt__colour="#1a3f93", felt__texture="weave", felt__vignette=0.35,
                     border="led", led="#8fd3ff", rail__wood="ebony", rail__bead="chrome", print__font="montserrat",
                     print__ink="#f4f4f2", print__accent="#8fd3ff", float="steel", wheel__metal="chrome"),
    "cards": _preset("Card tables' House", ROULETTE_HOUSE, felt=copy.deepcopy(HOUSE["felt"]), border=HOUSE["border"],
                     led=HOUSE["led"], rail=copy.deepcopy(HOUSE["rail"]),
                     print={k: HOUSE["print"][k] for k in ("font", "ink", "accent")},
                     wheel__metal="gold"),
}

# ---------------------------------------------------------------- Craps
# How the craps table looked before it took a style.
CRAPS_HOUSE = {
    "felt": {"colour": "#93141f", "texture": "grain", "vignette": 0.3},
    "rail": {"wood": "mahogany", "armrest": "dealer", "leather": "#2a140a", "bead": "brass"},
    "print": {"font": "cinzel", "ink": "#f1e4c4", "accent": "#f2cf6a", "red": "#e0453d"},
    "rubber": "#1b1413",
    "rack": "wood",
    "dice": "red",
}
CRAPS_BUILT_IN = {
    "grand": _preset("Grand Mahogany", CRAPS_HOUSE, felt__texture="weave", felt__vignette=0.55, rail__leather="#1b1a1a"),
    "monte": _preset("Monte Carlo", CRAPS_HOUSE, felt__colour="#0f5b3f", felt__texture="velvet", felt__vignette=0.6,
                     rail__wood="walnut", rail__leather="#1b1a1a", rail__bead="gold", print__font="cormorant",
                     print__ink="#e8d3a0", print__accent="#e0b84e", rack="lid"),
    "deco": _preset("Midnight Deco", CRAPS_HOUSE, felt__colour="#14284a", felt__texture="weave", felt__vignette=0.5,
                    rail__wood="rosewood", rail__leather="#1a2234", rail__bead="gold", print__font="josefin",
                    print__ink="#e8d3a0", print__accent="#e0b84e", rubber="#141a2a"),
    "vegas": _preset("Modern Vegas", CRAPS_HOUSE, felt__colour="#1a3f93", felt__texture="weave", felt__vignette=0.35,
                     rail__wood="ebony", rail__armrest="all", rail__leather="#1b1a1a", rail__bead="chrome",
                     print__font="montserrat", print__ink="#f4f4f2", print__accent="#8fd3ff", rack="steel", dice="blue"),
    "cards": _preset("Card tables' House", CRAPS_HOUSE, felt=copy.deepcopy(HOUSE["felt"]), rail=copy.deepcopy(HOUSE["rail"]),
                     print__ink=HOUSE["print"]["ink"]),
}
FELT_TEXTURES = ("grain", "weave", "velvet", "plain")
DICE = ("red", "green", "blue", "smoke", "amber", "violet")

KINDS = {
    "cards": {"key": KEY, "label": "card table", "games": CARD_GAMES, "house": HOUSE, "built_in": BUILT_IN,
              "choices": CHOICES, "colours": COLOURS, "ranges": RANGES},
    "roulette": {"key": KEY + "_roulette", "label": "roulette table", "games": ("roulette",), "house": ROULETTE_HOUSE,
                 "built_in": ROULETTE_BUILT_IN, "ranges": RANGES,
                 "choices": {"felt.texture": FELT_TEXTURES, "border": CHOICES["border"], "rail.wood": WOODS,
                             "rail.armrest": ("none", "all"), "rail.bead": CHOICES["rail.bead"],
                             "print.font": CHOICES["print.font"], "float": ("wood", "steel", "lid"),
                             "wheel.wood": ("match",) + WOODS, "wheel.metal": ("brass", "gold", "chrome"),
                             "chairs.frame": seating.CHOICES["frame"]},
                 "colours": ("felt.colour", "led", "rail.leather", "print.ink", "print.accent",
                             "numbers.red", "numbers.black", "numbers.zero", "chairs.upholstery")},
    "craps": {"key": KEY + "_craps", "label": "craps table", "games": ("craps",), "house": CRAPS_HOUSE,
              "built_in": CRAPS_BUILT_IN, "ranges": RANGES,
              "choices": {"felt.texture": FELT_TEXTURES, "rail.wood": WOODS, "rail.armrest": ("none", "dealer", "all"),
                          "rail.bead": CHOICES["rail.bead"], "print.font": CHOICES["print.font"],
                          "rack": ("wood", "steel", "lid"), "dice": DICE},
              "colours": ("felt.colour", "rail.leather", "print.ink", "print.accent", "print.red", "rubber")},
}


def _upgrade(design, kind: str):
    """A card design saved before a choice existed, brought up to date so it looks as it did: the side bets take
    what was the accent, the primary bets the ink; a card back takes the colour its design had (the emerald back
    is the lattice in green)."""
    if kind != "cards" or not isinstance(design, dict):
        return design
    design = copy.deepcopy(design)
    pr = design.get("print")
    if isinstance(pr, dict):
        pr.setdefault("side", pr.get("accent", HOUSE["print"]["side"]))
        pr.setdefault("primary", pr.get("ink", HOUSE["print"]["primary"]))
    back = design.get("back")
    if back in BACK_MAIN:
        design.setdefault("backColour", BACK_MAIN[back])
        if back == "emerald":
            design["back"] = "lattice"
    return design


for _s in BUILT_IN.values():
    _s["design"] = _upgrade(_s["design"], "cards")


def _kind(kind: str) -> dict:
    if kind not in KINDS:
        raise ValueError(f"No kind of table called {kind!r}.")
    return KINDS[kind]


def styled_tables(kind: str = "cards") -> dict:
    """The tables of a kind, on the floor or in a blueprint in the floor plan's library (a room taken off the floor
    keeps its tables' styles): {table_id: {name, game, layout, on_floor}}."""
    games = _kind(kind)["games"]
    every = {**plan.every_table(), **floor.TABLES}
    return {tid: {"name": t["name"], "game": t["game"], "layout": LAYOUTS[t["game"]], "on_floor": tid in floor.TABLES}
            for tid, t in every.items() if t.get("game") in games}


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


def clean_design(data: dict, kind: str = "cards") -> dict:
    """A design from the designer, checked, with anything it leaves out taken from its kind's House (ValueError
    says what's wrong)."""
    k = _kind(kind)
    if not isinstance(data, dict):
        raise ValueError("A design is a set of choices.")
    data = _upgrade(data, kind)
    out = copy.deepcopy(k["house"])
    for path, allowed in k["choices"].items():
        try:
            value = _get(data, path)
        except (KeyError, TypeError):
            continue
        if value not in allowed:
            raise ValueError(f"{path} is one of {', '.join(allowed)}.")
        _set(out, path, value)
    for path in k["colours"]:
        try:
            value = str(_get(data, path)).lower()
        except (KeyError, TypeError):
            continue
        if not re.fullmatch(r"#[0-9a-f]{6}", value):
            raise ValueError(f"{path} is a colour like #93141f.")
        _set(out, path, value)
    for path, (lo, hi) in k["ranges"].items():
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


def load(store, kind: str = "cards") -> dict:
    """A kind's styles (the built-ins marked `builtin`), which tables have which, and the default."""
    k = _kind(kind)
    house = k["house"]
    saved = store.get_json(k["key"], None)
    if saved is None:
        saved = {"styles": {HOUSE_ID: {"name": "House", "design": copy.deepcopy(house)}}, "tables": {}, "default": HOUSE_ID}
        store.set_json(k["key"], saved)
    styles = {sid: {"name": s["name"], "design": copy.deepcopy(s["design"]), "builtin": True} for sid, s in k["built_in"].items()}
    for sid, s in (saved.get("styles") or {}).items():
        if sid in k["built_in"]:
            continue
        try:
            design = clean_design(s.get("design") or {}, kind)   # (anything added since it was saved comes from House)
        except ValueError:
            design = copy.deepcopy(house)
        styles[sid] = {"name": str(s.get("name") or sid), "design": design, "builtin": False}
    styles.setdefault(HOUSE_ID, {"name": "House", "design": copy.deepcopy(house), "builtin": False})
    default = saved.get("default") if saved.get("default") in styles else HOUSE_ID
    known = styled_tables(kind)
    tables = {t: sid for t, sid in (saved.get("tables") or {}).items() if sid in styles and t in known}
    return {"styles": styles, "tables": tables, "default": default}


def load_all(store) -> dict:
    """Every kind's styles, as the welcome and the `table_styles` broadcast send them: {kind: load(kind)}."""
    return {kind: load(store, kind) for kind in KINDS}


def _save(store, current: dict, kind: str) -> dict:
    store.set_json(_kind(kind)["key"], {"styles": {sid: {"name": s["name"], "design": s["design"]}
                                                   for sid, s in current["styles"].items() if not s["builtin"]},
                                        "tables": current["tables"], "default": current["default"]})
    return current


def save_style(store, style_id: str, data: dict, kind: str = "cards") -> dict:
    k = _kind(kind)
    if not re.fullmatch(r"[a-z0-9_]{1,30}", style_id):
        raise ValueError("A style's id is lower-case letters, digits and _.")
    if style_id in k["built_in"]:
        raise ValueError("The built-in styles stay as they are: save a copy under a new name.")
    current = load(store, kind)
    old = current["styles"].get(style_id)
    name = str(data.get("name", old["name"] if old else "")).strip()
    if not name or len(name) > 40:
        raise ValueError("Give the style a name (up to 40 characters).")
    design = clean_design(data["design"], kind) if "design" in data else (old["design"] if old else copy.deepcopy(k["house"]))
    current["styles"][style_id] = {"name": name, "design": design, "builtin": False}
    return _save(store, current, kind)


def delete_style(store, style_id: str, kind: str = "cards") -> dict:
    current = load(store, kind)
    if style_id not in current["styles"]:
        raise KeyError(style_id)
    if style_id in _kind(kind)["built_in"] or style_id == HOUSE_ID:
        raise ValueError("House and the built-in styles stay; change House instead.")
    del current["styles"][style_id]
    current["tables"] = {t: s for t, s in current["tables"].items() if s != style_id}
    if current["default"] == style_id:
        current["default"] = HOUSE_ID
    return _save(store, current, kind)


def assign(store, data: dict, kind: str = "cards") -> dict:
    """{"tables": {table_id: style_id, or None for the default}, "default": style_id}, either part optional."""
    current = load(store, kind)
    known = styled_tables(kind)
    if "default" in data:
        if data["default"] not in current["styles"]:
            raise ValueError(f"No table style called {data['default']!r}.")
        current["default"] = data["default"]
    for table_id, style_id in (data.get("tables") or {}).items():
        if table_id not in known:
            raise ValueError(f"{table_id} isn't a {_kind(kind)['label']}.")
        if style_id in (None, ""):
            current["tables"].pop(table_id, None)
        elif style_id not in current["styles"]:
            raise ValueError(f"No table style called {style_id!r}.")
        else:
            current["tables"][table_id] = style_id
    return _save(store, current, kind)
