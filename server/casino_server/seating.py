"""
Seating: how the chairs look and how people sit down in them, as named styles.

Every table and slot cabinet uses the "default" style unless `tables` gives it another,
so different chairs per table can come later without changing the format. The client
draws the chair, plays the sit-down and places the craps standing spots from its style.
Signed off on the seating mockup (docs/seating/mockup.html, 2026-10-21).

Saved in the meta table under "seating":
    {"styles": {style_id: style}, "tables": {table_id: style_id}}
A style:
    name         what the admin page calls it
    chair        "stool" (low horseshoe back, footring) or "lounge" (padded tub back, disc base)
    upholstery   the seat and back's colour, "#rrggbb"
    frame        "brass", "chrome" or "gunmetal"
    back         back height, 0.6-1.4 of the chair's own
    size         0.85-1.15 (1 fits a slot bank's 34px spacing with room to spare)
    sit          "swivel" (the chair turns to you, then turns you to the game), "pull" (pulled
                 out, stepped into, pushed in) or "glide" (no chair animation)
    sit_speed    0.5-1.5, how fast the sit-down plays
    slot_screen  "after_sit" (the slot game opens once you're sat and the camera's there) or "at_once"
    craps_spot   "footprints", "spotlight", "medallion" or "ring" (the craps rail's standing spots)
"""
import re

DEFAULT_ID = "default"
DEFAULT_STYLE = {
    "name": "Default", "chair": "stool", "upholstery": "#2a2320", "frame": "brass", "back": 1.4, "size": 1.0,
    "sit": "swivel", "sit_speed": 1.4, "slot_screen": "after_sit", "craps_spot": "footprints",
}
CHOICES = {
    "chair": ("stool", "lounge"),
    "frame": ("brass", "chrome", "gunmetal"),
    "sit": ("swivel", "pull", "glide"),
    "slot_screen": ("after_sit", "at_once"),
    "craps_spot": ("footprints", "spotlight", "medallion", "ring"),
}
RANGES = {"back": (0.6, 1.4), "size": (0.85, 1.15), "sit_speed": (0.5, 1.5)}
KEY = "seating"


def load(store) -> dict:
    """The saved seating, with the default style always there (saved the first time it's asked for)."""
    saved = store.get_json(KEY, None)
    if saved is None:
        saved = {"styles": {DEFAULT_ID: dict(DEFAULT_STYLE)}, "tables": {}}
        store.set_json(KEY, saved)
    styles = {sid: {**DEFAULT_STYLE, **{k: v for k, v in s.items() if k in DEFAULT_STYLE}}
              for sid, s in (saved.get("styles") or {}).items()}   # (dropping fields no longer used)
    styles.setdefault(DEFAULT_ID, dict(DEFAULT_STYLE))
    tables = {t: sid for t, sid in (saved.get("tables") or {}).items() if sid in styles}
    return {"styles": styles, "tables": tables}


def clean_style(data: dict, base: dict | None = None) -> dict:
    """A style from the admin page, checked over `base` (ValueError says what's wrong)."""
    out = dict(base or DEFAULT_STYLE)
    name = str(data.get("name", out["name"])).strip()
    if not name or len(name) > 30:
        raise ValueError("Give the style a name (up to 30 characters).")
    out["name"] = name
    for key, allowed in CHOICES.items():
        if key in data:
            if data[key] not in allowed:
                raise ValueError(f"{key} is one of {', '.join(allowed)}.")
            out[key] = data[key]
    for key, (lo, hi) in RANGES.items():
        if key in data:
            v = float(data[key])
            if not lo <= v <= hi:
                raise ValueError(f"{key} is {lo}-{hi}.")
            out[key] = round(v, 2)
    if "upholstery" in data:
        colour = str(data["upholstery"]).lower()
        if not re.fullmatch(r"#[0-9a-f]{6}", colour):
            raise ValueError("The upholstery is a colour like #2a2320.")
        out["upholstery"] = colour
    return out


def save_style(store, style_id: str, data: dict) -> dict:
    if not re.fullmatch(r"[a-z0-9_]{1,30}", style_id):
        raise ValueError("A style's id is lower-case letters, digits and _.")
    seating = load(store)
    seating["styles"][style_id] = clean_style(data, seating["styles"].get(style_id))
    store.set_json(KEY, seating)
    return seating


def delete_style(store, style_id: str) -> dict:
    if style_id == DEFAULT_ID:
        raise ValueError("The default style stays; change it instead.")
    seating = load(store)
    if style_id not in seating["styles"]:
        raise KeyError(style_id)
    del seating["styles"][style_id]
    seating["tables"] = {t: s for t, s in seating["tables"].items() if s != style_id}
    store.set_json(KEY, seating)
    return seating


def assign(store, tables: dict) -> dict:
    """Give tables their styles: {table_id: style_id}, or None (back to the default)."""
    seating = load(store)
    for table_id, style_id in tables.items():
        if style_id in (None, "", DEFAULT_ID):
            seating["tables"].pop(str(table_id), None)
        elif style_id not in seating["styles"]:
            raise ValueError(f"No seating style called {style_id!r}.")
        else:
            seating["tables"][str(table_id)] = style_id
    store.set_json(KEY, seating)
    return seating
