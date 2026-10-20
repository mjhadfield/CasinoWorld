"""
The Slot design wizard's later steps (slot_design.py has the designs, Concept and Art). DesignBoard mixes these in,
so every method runs under the board's lock and saves through its Design.

  Value ladder   the chosen symbols ordered into the tiers (W, BS, FS, H1.., M1.., L1..) and the upgrade chain
  Scene          the screen's look as skins (slot_design_scene.py: shapes, palette, colours, fonts, words, decor),
                 the background (the image model or uploaded) and the logo (rendered in a font, the rendered lettering
                 restyled by the image model, or drawn whole by it)
  Features       which of the library's random features the slot uses, their rates and value tables
  Bonus games    each library bonus (the Trail, the free games, the wave battle, the island voyage): on or off, the scatter that starts it, whether
                 Buy Bonus can give it, and its settings; Buy Bonus's price. These make the variant's routes
                 (which bonuses each way in plays, one at random when there are several). A scatter that
                 starts nothing comes off the reels and the Value ladder.
  Art slots      the pictures the game draws outside the reels (shared by Features and Bonus games): a board
                 image, or "sym:<id>" to follow a symbol's chosen take
  Specs          a new feature or bonus type, described for building (Build lists them as code tasks)
  Sprites        win animations per tier group and the floor cabinet (their colours start from the scene's)
  Sounds         the slot's own sound for any slot moment (sounds.py); the rest play "Every slot machine"'s.
                 Kept in the design until Build makes the slot's sound set (slots.<id>).
  Maths          the pays and per-reel symbol counts; the browser simulates and tunes (slots_math.js in a Web
                 Worker) and freezes the strips here, where the server replays a sample of the browser's spins to
                 prove both engines agree. A freeze remembers the settings it measured, so later changes show
                 it as stale.
  Sign-off       the checklist (what Build needs, and what's still a stand-in), the rules screen's text, and
                 the sign-off, which locks everything that changes how the slot pays until it's reopened.
"""
import datetime
import hashlib
import io
import json
from pathlib import Path

from PIL import Image, ImageFont

from casino_server import slot_design_art as art
from casino_server.slots import base
from casino_server.slots.variants.armadillo import VARIANT as ARMADILLO

FONTS_DIR = Path(__file__).resolve().parents[2] / "client" / "assets" / "fonts"
FRAME_STYLES = ("metal", "wood", "neon", "glass")
DECK_STYLES = ("frame",) + FRAME_STYLES   # "frame": match the reel frame's style


def deck_look(sc: dict) -> dict:
    """The deck's style and tint as a built slot and the mockup draw it: "frame" resolved, no tint as None."""
    d = sc.get("deck") or {"style": "frame", "colour": None}
    style = d["style"] if d["style"] != "frame" else sc.get("frame", {}).get("style", "metal")
    return {"style": style, "colour": d.get("colour")}
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
    "b_hero": ("Battle: your ship", "bonuses"),
    "b_enemy": ("Battle: an enemy ship (cloaks, fires back, reveals prizes)", "bonuses"),
    "b_boss": ("Battle: the boss ship after the last wave", "bonuses"),
    "v_ship": ("Voyage: your ship, sailing the map", "bonuses"),
    "v_treasure": ("Voyage island: Treasure Island (a sure prize)", "bonuses"),
    "v_wreck": ("Voyage island: a Shipwreck (relics, maybe a key or an artefact)", "bonuses"),
    "v_skull": ("Voyage island: Skull Island (a big prize, or it sinks you)", "bonuses"),
    "v_port": ("Voyage island: Port Royal (trade relics), and the start port", "bonuses"),
    "v_cove": ("Voyage island: a Hidden Cove (a key opens it)", "bonuses"),
    "v_final": ("Voyage: the final island", "bonuses"),
    "v_chest": ("Voyage: the legendary treasure (a chest with four locks)", "bonuses"),
    "v_relic": ("Voyage: a relic", "bonuses"), "v_key": ("Voyage: a key", "bonuses"),
    "v_art1": ("Voyage: the first artefact", "bonuses"), "v_art2": ("Voyage: the second artefact", "bonuses"),
    "v_art3": ("Voyage: the third artefact", "bonuses"), "v_art4": ("Voyage: the fourth artefact", "bonuses"),
}
VOYAGE_ART = ("v_ship", "v_treasure", "v_wreck", "v_skull", "v_port", "v_cove", "v_final", "v_chest", "v_relic", "v_key",
              "v_art1", "v_art2", "v_art3", "v_art4")
TRAIL_SPACES = ("snake", "heart", "forward", "back", "lightning", "crate")
# Each bonus's way in, as Armadillo has it: the trail from the bonus scatter or Buy Bonus, the free games from theirs.
BONUS_WAYS = {"trail": {"enabled": True, "scatter": "BS", "buyable": True},
              "free": {"enabled": True, "scatter": "FS", "buyable": False},
              "battle": {"enabled": False, "scatter": "BS", "buyable": True},   # not Armadillo's: off until switched on
              "voyage": {"enabled": False, "scatter": "BS", "buyable": True}}
BONUS_TITLES = {"trail": "The trail bonus", "free": "The free games", "battle": "The battle bonus", "voyage": "The voyage bonus"}
TRAIL_WORDS = ("name", "launcher", "hint")   # the trail's words: not part of its maths
BATTLE_WORDS = {"name": "RED ALERT", "hint": "tap a ship to fire", "enemy": "ENEMY SHIP", "boss_name": "FLAGSHIP"}
BATTLE_PAIRS = ("prizes", "spins", "boss")   # the battle's value tables
# The voyage's words (Dead Man's Map's, from the Pirates design's spec): its name, the islands, the treasure.
VOYAGE_WORDS = {"name": "DEAD MAN'S MAP", "hint": "choose your next island", "start": "TORTUGA", "final": "ISLA DE MUERTA",
                "treasure_name": "TREASURE ISLAND", "wreck_name": "SHIPWRECK", "skull_name": "SKULL ISLAND",
                "port_name": "PORT ROYAL", "cove_name": "HIDDEN COVE", "relic": "RELIC", "chest_name": "LEGENDARY TREASURE",
                "legend_name": "THE LEGEND"}
VOYAGE_ARTEFACTS = ["COMPASS", "MEDALLION", "SPYGLASS", "CUTLASS"]
VOYAGE_PAIRS = ("treasure", "relics", "skull", "cove")   # the voyage's value tables
VOYAGE_KINDS = ("treasure", "wreck", "skull", "port")    # what a map island can be (coves are placed apart)
WAYS = tuple(BONUS_WAYS["trail"])
# What each art slot is drawn for: a feature, or a bonus (a picture for something switched off isn't needed).
ART_USE = {"armadillo": ("wildReels", "trail"), "barrel": ("instant",),
           "b_hero": ("battle",), "b_enemy": ("battle",), "b_boss": ("battle",), **{k: ("voyage",) for k in VOYAGE_ART}}
WIN_PRESETS = ("none", "pulse", "bounce", "shine", "glow", "spin")
WIN_DEFAULTS = {"wild": "glow", "high": "shine", "mid": "pulse", "low": "pulse", "scatter": "bounce"}
# The screen's colours (the mockup's names; Armadillo's values) and fonts. Every tone the slot screen draws comes
# from these (shade backs the banners and pop-ups and does the dimming; goldLo is the dark end of gold and coins).
THEME_DEFAULTS = {"gold": "#f4c94f", "goldHi": "#fff1b0", "goldLo": "#9a6614", "edge": "#d9a54a", "cream": "#f6ead0",
                  "muted": "#b89b74", "ink": "#2b1004", "shade": "#1a0b03", "win": "#ffe27a", "spin": "#f0b43a",
                  "alert": "#7d130c"}
FONT_DEFAULTS = {"display": "Rye-Regular.ttf", "ui": "BarlowCondensed-Bold.ttf"}
CABINET_DEFAULTS = {"body": "#4a2c18", "trim": "#ffb347", "title": "#e8a33a"}


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


# What the side panel calls each feature, unless the design names it (Features step).
FEATURE_NAMES = {"wilds": "RANDOM WILDS", "wildReels": "WILD REELS", "colossal": "COLOSSAL REELS", "multiplier": "MULTIPLIER",
                 "upgrade": "SYMBOL UPGRADE", "repeat": "REPEAT WIN", "instant": "INSTANT WIN"}


def features_view(d) -> dict:
    f = d.data.get("features", {})
    A = ARMADILLO
    return {"library": list(base.FEATURES), "enabled": f.get("enabled", list(base.FEATURES)),
            "names": {k: f.get("names", {}).get(k) or FEATURE_NAMES.get(k, k.upper()) for k in base.FEATURES},
            "default_names": FEATURE_NAMES,
            "rates": {**A.rates, **f.get("rates", {})}, "free_rates": {**A.free_rates, **f.get("free_rates", {})},
            "tables": {t: f.get("tables", {}).get(t, [list(p) for p in getattr(A, t)]) for t in TABLES},
            "specs": [x for x in d.data.get("specs", []) if x["kind"] == "feature"]}


def bonuses_view(d) -> dict:
    b = d.data.get("bonuses", {})
    t = {**BONUS_WAYS["trail"], **{k: v for k, v in ARMADILLO.trail.items()}, **b.get("trail", {})}
    t["coins"] = [list(p) for p in t["coins"]]
    t["crate_radius"] = [list(p) for p in t["crate_radius"]]
    t.setdefault("name", "TRAIL BONUS")
    t.setdefault("launcher", "THE LAUNCHER")
    t.setdefault("hint", "fire to move along the trail")
    bt = {**BONUS_WAYS["battle"], **json.loads(json.dumps(base.BATTLE)), **BATTLE_WORDS, **b.get("battle", {})}
    vy = {**BONUS_WAYS["voyage"], **json.loads(json.dumps(base.VOYAGE)), **VOYAGE_WORDS, "artefacts": list(VOYAGE_ARTEFACTS),
          **b.get("voyage", {})}
    view = {"trail": t, "free": {"games": ARMADILLO.free_games, "name": "COMBO FREE GAMES", **BONUS_WAYS["free"], **b.get("free", {})},
            "battle": bt, "voyage": vy,
            "buy": {"enabled": True, "cost": ARMADILLO.buy_cost, **b.get("buy", {})},
            "specs": [x for x in d.data.get("specs", []) if x["kind"] == "bonus"]}
    view["routes"] = routes_of(view)
    view["unused_scatters"] = [s for s in base.SCATTERS if not view["routes"][s]]
    return view


def routes_of(view) -> dict:
    """Which bonuses each way in plays (the variant's routes): 3+ of a scatter, and Buy Bonus when it's offered."""
    on = [k for k in base.BONUSES if view[k]["enabled"]]
    out = {s: [k for k in on if view[k]["scatter"] == s] for s in base.SCATTERS}
    out["buy"] = [k for k in on if view[k]["buyable"]] if view["buy"]["enabled"] else []
    return out


def trail_maths(t: dict) -> dict:
    """The trail's settings the engine uses (not its words or its way in)."""
    return {k: v for k, v in t.items() if k not in TRAIL_WORDS + WAYS}


def scene_match(d) -> tuple[str, dict]:
    """The win glow and the floor cabinet's colours that match the chosen scene (where the Sprites step starts)."""
    from casino_server.slot_design_scene import chosen
    sk = chosen(d)[1]
    pal, cols = sk.get("palette", {}), sk["colours"]
    if sk["base"] == "classic":
        return "#ffe27a", dict(CABINET_DEFAULTS)
    return pal.get("hl", cols["win"]), {"body": pal.get("d", cols["shade"]), "trim": pal.get("hl", cols["edge"]),
                                        "title": pal.get("warn", cols["gold"])}


def sprites_view(d) -> dict:
    from casino_server.slot_design_scene import look
    sp = d.data.get("sprites", {})
    glow, cab = scene_match(d)
    win = {g: {"preset": p, "strength": 1.0, "colour": glow, **sp.get("win", {}).get(g, {})} for g, p in WIN_DEFAULTS.items()}
    lines = (d.data.get("scene", {}).get("logo", {}).get("lines") or [d.data.get("name", "")])[:2]
    lk = look(d)
    return {"win": win, "presets": list(WIN_PRESETS), "colours": lk["colours"], "armadillo_colours": THEME_DEFAULTS,
            "fonts": lk["fonts"], "font_list": _fonts(d), "match": {"glow": glow, "cabinet": cab},
            "cabinet": {**cab, "lines": [x.upper()[:12] for x in lines], **sp.get("cabinet", {})}}


def _armadillo_scatters(s: str) -> list[int]:
    """How many of scatter `s` Armadillo has on each reel (what a scatter switched back on starts from)."""
    return [strip.count(s) for strip in ARMADILLO.strips]


def battle_maths(x: dict) -> dict:
    """The battle's settings the engine uses (not its words or its way in)."""
    return {k: x[k] for k in base.BATTLE}


def voyage_maths(x: dict) -> dict:
    """The voyage's settings the engine uses (not its words or its way in)."""
    return {k: x[k] for k in base.VOYAGE}


def _paying(tiers) -> list:
    return [t for t in tiers if t not in ("BS", "FS")]


def _settings_hash(d) -> str:
    """What a simulation depends on besides the strips: pays, upgrades, features and bonuses."""
    f, b, lad = features_view(d), bonuses_view(d), ladder_view(d)
    blob = {"pays": lad["pays"], "upgrades": lad["upgrades"], "features": {k: f[k] for k in ("enabled", "rates", "free_rates", "tables")},
            "trail": trail_maths(b["trail"]), "free": b["free"]["games"], "buy": b["buy"]["enabled"] and b["buy"]["cost"],
            "routes": b["routes"]}
    if b["battle"]["enabled"]:   # (only when it's on, so switching the library's new bonus in doesn't stale a freeze)
        blob["battle"] = battle_maths(b["battle"])
    if b["voyage"]["enabled"]:
        blob["voyage"] = voyage_maths(b["voyage"])
    return hashlib.sha1(json.dumps(blob, sort_keys=True).encode()).hexdigest()[:12]


def maths_view(d) -> dict:
    m = d.data.get("maths", {})
    tiers = base.tier_ids(d.data["concept"]["tiers"])
    counts = m.get("counts")
    if counts and any(set(c) != set(tiers) for c in counts):
        counts = None   # the tier shape changed since: start again from the stretched defaults
    frozen = bool(m.get("strips")) and counts is not None
    return {"pays": ladder_view(d)["pays"], "counts": counts, "big_counts": m.get("big_counts") if counts else None,
            "strips": m.get("strips") if frozen else None, "free_strips": m.get("free_strips") if frozen else None,
            "big_strip": m.get("big_strip") if frozen else None, "frozen": frozen, "frozen_at": m.get("frozen_at"),
            "report": m.get("report"), "check": m.get("check"),
            "stale": frozen and m.get("settings") != _settings_hash(d), "target": d.data["concept"]["target_rtp"]}


def variant_from_design(d):
    """The design as a slot variant (slots/variant.py), from its frozen maths. Build writes this as JSON."""
    from casino_server.slots.variant import SlotVariant
    m, lad, f, b = maths_view(d), ladder_view(d), features_view(d), bonuses_view(d)
    if not m["frozen"]:
        raise DesignError("Freeze the maths first (Maths & payouts step).")
    names = {s["id"]: s["name"] for s in d.data["symbols"]}
    pair = lambda rows: [tuple(r) for r in rows]
    return SlotVariant(
        id=d.id, name=d.data.get("name", d.id), symbols={t: names.get(lad["slots"].get(t), t) for t in lad["tiers"]},
        strips=m["strips"], free_strips=m["free_strips"], big_strip=m["big_strip"],
        rates={k: f["rates"][k] for k in base.FEATURES}, free_rates={k: f["free_rates"][k] for k in base.FEATURES},
        wild_counts=pair(f["tables"]["wild_counts"]), wild_reel_counts=pair(f["tables"]["wild_reel_counts"]),
        colossal_sizes=pair(f["tables"]["colossal_sizes"]), multipliers=pair(f["tables"]["multipliers"]),
        repeats=pair(f["tables"]["repeats"]), instants=pair(f["tables"]["instants"]),
        trail={**trail_maths(b["trail"]), "coins": pair(b["trail"]["coins"]), "crate_radius": pair(b["trail"]["crate_radius"])},
        buy_cost=b["buy"]["cost"] if b["routes"]["buy"] else 0, free_games=b["free"]["games"], routes=b["routes"],
        pays={k: tuple(v) for k, v in lad["pays"].items() if k in _paying(lad["tiers"])}, upgrades=lad["upgrades"],
        features=f["enabled"], battle=battle_maths(b["battle"]), voyage=voyage_maths(b["voyage"]))


def default_rules(d) -> list[str]:
    """The rules screen's lines, written from the design (the mockup's INFO overlay; editable on the Mockup step)."""
    lad, b = ladder_view(d), bonuses_view(d)
    names = {s["id"]: s["name"] for s in d.data["symbols"]}
    nm = lambda t: names.get(lad["slots"].get(t), t)
    ups = {}
    for frm, to in lad["upgrades"].items():
        ups.setdefault(to, []).append(nm(frm))
    r = b["routes"]
    title = {"trail": b["trail"]["name"], "free": f"{b['free']['games']} {b['free']['name'].lower()}", "battle": b["battle"]["name"],
             "voyage": b["voyage"]["name"]}
    plays = lambda ks: title[ks[0]] if len(ks) == 1 else " or ".join(title[k] for k in ks) + ", at random"
    scatters = [s for s in base.SCATTERS if r[s]]
    ways = [f"3+ {nm(s)}: {plays(r[s])}." for s in scatters]
    if r["buy"]:
        ways.append(f"Buy Bonus ({b['buy']['cost']}x the bet): {plays(r['buy'])}.")
    return [f"{nm('W')} stands in for everything" + (f" except {' and '.join(nm(s) for s in scatters)}" if scatters else "")
            + ". Pays left to right on 25 lines; the longest match on each line pays.",
            "Random features can hit any spin, some before the reels stop and some after.",
            *([" ".join(ways)] if ways else []),
            "Upgrades: " + " · ".join(f"{', '.join(fs)} → {nm(t)}" for t, fs in ups.items())]


def checklist(d) -> list[dict]:
    """What the slot needs before Build (required) and what's still a stand-in or unfinished (worth a look)."""
    lad, m, art_slots = ladder_view(d), maths_view(d), art_view(d)
    cats = {c["id"]: c for c in d.data["categories"]}
    out = [{"id": "ladder", "label": f"Value ladder: {len(lad['slots'])} of {len(lad['tiers'])} tiers filled", "ok": lad["complete"], "required": True, "step": "ladder"},
           {"id": "maths", "label": "Maths frozen" + (" (but settings changed since)" if m["stale"] else ""), "ok": m["frozen"] and not m["stale"], "required": True, "step": "maths"}]
    no_art = [lad["slots"][t] for t in lad["slots"] if not d.chosen_file(d.symbol(lad["slots"][t]))]
    out.append({"id": "art", "label": "Every tier's symbol has art" + (f" (not yet: {', '.join(no_art)})" if no_art else ""), "ok": not no_art, "required": True, "step": "art"})
    for c in d.data["categories"]:
        if c.get("required") is not None:
            have = sum(bool(s.get("keep")) for s in d.data["symbols"] if s["category"] == c["id"])
            out.append({"id": "cat_" + c["id"], "label": f"{c['title']}: {have} of {c['required']} in the final set", "ok": have == c["required"], "required": False, "step": "art"})
    stand = [k for k, a in art_slots.items() if a["used"] and not a["file"]]
    out.append({"id": "art_slots", "label": "Feature and bonus pictures" + (f": {len(stand)} still Armadillo's" if stand else ""), "ok": not stand, "required": False, "step": "bonuses"})
    sc = d.data.get("scene", {})
    out.append({"id": "background", "label": "A background", "ok": bool(sc.get("background")), "required": False, "step": "scene"})
    out.append({"id": "logo", "label": "A logo", "ok": bool(sc.get("logo", {}).get("file")), "required": False, "step": "scene"})
    skin = sc["skins"][sc["skin"]] if sc.get("skin") in sc.get("skins", {}) else {"by": "house"}
    waiting = sc.get("brief", {}).get("status") == "waiting"
    out.append({"id": "skin", "label": "A designed scene" + (" (Claude's brief is waiting)" if waiting else
                f": {skin.get('name')}" if skin.get("by") != "house" else " (still a house look)"),
                "ok": skin.get("by") != "house" and not waiting, "required": False, "step": "scene"})
    out.append({"id": "sounds", "label": f"Own sounds for {len(d.data.get('sounds', {}))} moments (optional)", "ok": True, "required": False, "step": "sounds"})
    specs = d.data.get("specs", [])
    if specs:
        out.append({"id": "specs", "label": f"{len(specs)} new feature/bonus idea{'s' if len(specs) > 1 else ''} to be built in code", "ok": False, "required": False, "step": "build"})
    return out


def signoff_view(d) -> dict:
    so = d.data.get("signed_off")
    return {"signed_off": so, "rules": d.data.get("rules") or default_rules(d), "rules_custom": bool(d.data.get("rules")),
            "checklist": checklist(d), "ready": all(c["ok"] for c in checklist(d) if c["required"])}


def machine_moments() -> dict:
    """The sound moments a slot machine's own set can change (sounds.shows for a machine's set)."""
    from casino_server import sounds
    return {k: m for k, m in sounds.MOMENTS.items() if m["uses"] in ("all", "slots") and m["home"] in ("casino", "slots")}


def sounds_view(d, board) -> dict:
    if board is None:
        return {"moments": []}
    own = d.data.get("sounds", {})
    rows = []
    for k, m in machine_moments().items():
        inherited, src = board.resolve("slots", k)
        rows.append({"key": k, **{x: m[x] for x in ("title", "when", "section", "loop")},
                     "inherited": {**inherited, "from": src}, "own": own.get(k)})
    return {"moments": rows}


def art_view(d) -> dict:
    """Each art slot: what it's for, the step that sets it, what's chosen ("sym:<id>" or a path), its adjustments
    (scale, mirror, ...), the picture chosen (src) and the file it comes to now, adjustments baked in (both None
    until chosen; the mockup then shows Armadillo's)."""
    slots, tweaks = d.data.get("art_slots", {}), d.data.get("art_adjust", {})
    b, on = bonuses_view(d), set(features_view(d)["enabled"])
    on |= {k for k in base.BONUSES if b[k]["enabled"]}
    out = {}
    for key, (label, step) in ART_SLOTS.items():
        v = slots.get(key)
        f = None
        if isinstance(v, str) and v.startswith("sym:"):
            s = next((x for x in d.data["symbols"] if x["id"] == v[4:]), None)
            f = d.chosen_file(s) if s else None
        elif v:
            f = v if d.path(v) else None
        used = bool(on & set(ART_USE.get(key, ("trail",))))   # the trail's pictures unless listed
        a = art.adjust_values(tweaks.get(key))
        out[key] = {"label": label, "step": step, "value": v, "src": f, "file": d.adjusted(key, f, a) if f else None,
                    "adjust": a, "used": used}
    return out


class DesignError(ValueError):
    """A request the board can't take (shown to the page as-is)."""


def ladder_view(d) -> dict:
    """The Value ladder for the overview: every tier of the tier shape, the symbol in each, the upgrade chain and
    each tier's pays (the house defaults until the Maths step changes them)."""
    shape = d.data["concept"]["tiers"]
    unused = bonuses_view(d)["unused_scatters"]   # a scatter that starts nothing isn't on the reels
    tiers = [t for t in base.tier_ids(shape) if t not in unused]
    lad = d.data.get("ladder", {})
    ids = {s["id"] for s in d.data["symbols"]}
    slots = {t: sid for t, sid in lad.get("slots", {}).items() if t in tiers and sid in ids}
    upgrades = {k: v for k, v in (lad.get("upgrades") or base.default_upgrades(shape)).items() if k in tiers and v in tiers}
    pays = {**base.default_pays(shape), **{k: tuple(v) for k, v in d.data.get("maths", {}).get("pays", {}).items() if k in tiers}}
    # a scatter's symbol is kept while it's off the reels (it comes back with its way in)
    scatters = {t: sid for t, sid in lad.get("slots", {}).items() if t in base.SCATTERS and sid in ids}
    return {"tiers": tiers, "slots": slots, "scatters": scatters, "upgrades": upgrades, "default_upgrades": base.default_upgrades(shape),
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


class StepsMixin:
    sounds = None   # the casino's SoundBoard (app.py sets it), for the Sounds step's library and defaults

    @staticmethod
    def _unlocked(d) -> None:
        """A signed-off slot's pays are locked: Value ladder, Features, Bonus games and Maths refuse changes."""
        if d.data.get("signed_off"):
            raise DesignError("This slot is signed off: reopen it (Mockup & sign-off) to change how it pays.")

    # ------------------------------------------------------------- Mockup & sign-off
    def set_rules(self, did: str, lines) -> None:
        with self.lock:
            d = self.design(did)
            if lines is None:
                d.data.pop("rules", None)
            else:
                if not isinstance(lines, list) or not 1 <= len(lines) <= 8:
                    raise DesignError("The rules screen has 1 to 8 lines.")
                d.data["rules"] = [str(x).strip()[:160] for x in lines if str(x).strip()]
            d.save()

    def sign_off(self, did: str) -> dict:
        with self.lock:
            d = self.design(did)
            missing = [c["label"] for c in checklist(d) if c["required"] and not c["ok"]]
            if missing:
                raise DesignError("Not ready to sign off: " + "; ".join(missing) + ".")
            d.data["signed_off"] = {"at": datetime.datetime.now().isoformat(timespec="seconds"), "settings": _settings_hash(d)}
            d.data["steps"]["mockup"] = "done"
            d.save()
            return signoff_view(d)

    def reopen(self, did: str) -> None:
        with self.lock:
            d = self.design(did)
            d.data.pop("signed_off", None)
            d.data["steps"]["mockup"] = "doing"
            d.save()

    # ------------------------------------------------------------- Sprites
    def update_sprites(self, did: str, ch: dict) -> None:
        with self.lock:
            d = self.design(did)
            sp = d.data.setdefault("sprites", {})
            if "win" in ch:
                win = dict(sp.get("win", {}))
                for g, v in (ch["win"] or {}).items():
                    if g not in WIN_DEFAULTS or not isinstance(v, dict):
                        raise DesignError(f"Win animations are set per {', '.join(WIN_DEFAULTS)}.")
                    if v.get("preset", "none") not in WIN_PRESETS:
                        raise DesignError(f"A win animation is one of {', '.join(WIN_PRESETS)}.")
                    strength = v.get("strength", 1.0)
                    if not isinstance(strength, (int, float)) or not 0.25 <= strength <= 2:
                        raise DesignError("Animation strength is 0.25 to 2.")
                    if not art.is_colour(v.get("colour", "#ffe27a")):
                        raise DesignError("A glow colour is like #ffe27a.")
                    win[g] = {"preset": v.get("preset", "none"), "strength": float(strength), "colour": v.get("colour", "#ffe27a")}
                sp["win"] = win
            # the screen's colours and fonts are the chosen scene's (the Scene step's), set here too for older pages
            from casino_server.slot_design_scene import LETTERING, chosen
            skin = chosen(d)[1]
            if "colours" in ch:
                cols = ch["colours"] or {}
                if set(cols) - set(THEME_DEFAULTS) or not all(art.is_colour(c) for c in cols.values()):
                    raise DesignError("Theme colours are " + ", ".join(THEME_DEFAULTS) + ", each like #f4c94f.")
                skin["colours"] = {**skin["colours"], **cols}
            if "fonts" in ch:
                fonts = ch["fonts"] or {}
                if set(fonts) - set(FONT_DEFAULTS):
                    raise DesignError("The fonts are display and ui.")
                for f in fonts.values():
                    if f != LETTERING:
                        _font_path(d, f)
                skin["fonts"] = {**skin["fonts"], **fonts}
            if "cabinet" in ch:
                cab = dict(sp.get("cabinet", {}))
                for k, v in (ch["cabinet"] or {}).items():
                    if k in CABINET_DEFAULTS:
                        if not art.is_colour(v):
                            raise DesignError(f"The cabinet's {k} colour is like #ffb347.")
                        cab[k] = v
                    elif k == "lines":
                        if not isinstance(v, list) or not 1 <= len(v) <= 2:
                            raise DesignError("The topper has one or two lines.")
                        cab[k] = [str(x).upper().strip()[:12] for x in v]
                    else:
                        raise DesignError(f"Can't change the cabinet's {k!r}.")
                sp["cabinet"] = cab
            d.save()

    def font_file(self, did: str, name: str) -> Path:
        with self.lock:
            return _font_path(self.design(did), name)

    # ------------------------------------------------------------- Maths & payouts
    def update_maths(self, did: str, ch: dict) -> None:
        """New pays or reel counts: the old freeze no longer describes the game, so it's dropped."""
        with self.lock:
            d = self.design(did)
            self._unlocked(d)
            tiers = base.tier_ids(d.data["concept"]["tiers"])
            m = d.data.setdefault("maths", {})
            if "pays" in ch:
                pays = ch["pays"]
                if not isinstance(pays, dict) or set(pays) - set(_paying(tiers)):
                    raise DesignError("Pays are for the Wild and the H, M and L tiers.")
                for t, p in pays.items():
                    if not (isinstance(p, list) and len(p) == 3 and all(isinstance(x, int) and 0 <= x <= 5000 for x in p) and p[0] <= p[1] <= p[2]):
                        raise DesignError(f"{t}: pays for 3, 4 and 5 are whole numbers, each at least the one before.")
                m["pays"] = {**m.get("pays", {}), **{t: list(p) for t, p in pays.items()}}
            if "counts" in ch:
                counts = ch["counts"]
                if not isinstance(counts, list) or len(counts) != 5:
                    raise DesignError("Reel counts are five reels of {tier: how many}.")
                unused = bonuses_view(d)["unused_scatters"]
                for i, c in enumerate(counts, 1):
                    if isinstance(c, dict):
                        c.update({s: 0 for s in unused})   # a scatter that starts nothing stays off the reels
                    if not isinstance(c, dict) or set(c) != set(tiers):
                        raise DesignError(f"Reel {i} needs a count for every tier.")
                    if any(not isinstance(n, int) or not 0 <= n <= 40 for n in c.values()):
                        raise DesignError(f"Reel {i}: counts are whole numbers from 0 to 40.")
                    if c["BS"] > 3 or c["FS"] > 3:
                        raise DesignError(f"Reel {i}: at most 3 of each scatter (a reel never shows two).")
                    if not 20 <= sum(c.values()) <= 150:
                        raise DesignError(f"Reel {i} is {sum(c.values())} symbols long: keep it 20 to 150.")
                m["counts"] = counts
            if "big_counts" in ch:
                big = ch["big_counts"]
                if not isinstance(big, dict) or set(big) != set(_paying(tiers)) or any(not isinstance(n, int) or not 0 <= n <= 20 for n in big.values()) or sum(big.values()) < 5:
                    raise DesignError("Colossal symbols: a count of 0 to 20 for every pay tier, at least 5 in all.")
                m["big_counts"] = big
            for k in ("strips", "free_strips", "big_strip", "report", "check", "frozen_at", "settings"):
                m.pop(k, None)
            d.save()

    def freeze_maths(self, did: str, body: dict) -> dict:
        """Keep the browser's strips (built from the counts) with its report, once the server agrees with it:
        the same spins for a sample of seeds, and the same exact line return."""
        from casino_server.slots.outcome import spin_outcome
        from casino_server.slots.rng import mulberry32
        from casino_server.slots import sim
        with self.lock:
            d = self.design(did)
            self._unlocked(d)
            mv = maths_view(d)
            counts, big = mv["counts"], mv["big_counts"]
            if not counts or not big:
                raise DesignError("Save the reel counts first.")
            strips, free, bigs = body.get("strips"), body.get("free_strips"), body.get("big_strip")
            try:
                for i, (strip, c) in enumerate(zip(strips, counts)):
                    if sorted(strip) != sorted(t for t, n in c.items() for _ in range(n)):
                        raise DesignError(f"Reel {i + 1}'s strip doesn't match its counts.")
                for i, (strip, c) in enumerate(zip(free, counts)):
                    if sorted(strip) != sorted(t for t, n in c.items() if t not in ("BS", "FS") for _ in range(n)):
                        raise DesignError(f"Free-game reel {i + 1} doesn't match its counts.")
                if sorted(bigs) != sorted(t for t, n in big.items() for _ in range(n)):
                    raise DesignError("The Colossal strip doesn't match its counts.")
            except TypeError:
                raise DesignError("Send the strips, the free-game strips and the Colossal strip.")
            if len(strips) != 5 or len(free) != 5:
                raise DesignError("Five reels, please.")
            m = d.data.setdefault("maths", {})
            saved = {k: m.get(k) for k in ("strips", "free_strips", "big_strip")}
            m.update(strips=strips, free_strips=free, big_strip=bigs)
            try:
                v = variant_from_design(d)
                bad = []
                for case in (body.get("sample") or [])[:300]:
                    o = spin_outcome(v, case["bet"], mulberry32(case["seed"]))
                    if o["stops"] != case["stops"] or o["total"] != case["total"]:
                        bad.append(case["seed"])
                exact = base.exact_line_rtp(v.strips, v.pays)
                if bad or abs(100 * exact - float(body.get("exact", -1))) > 1e-6:
                    raise DesignError(f"The server's engine disagrees with the browser's ({len(bad)} of the sample spins"
                                      f"{'' if abs(100 * exact - float(body.get('exact', -1))) <= 1e-6 else ', and the exact line return'}).")
            except Exception:
                m.update(saved)
                raise
        check = sim.simulate(v, 30000, 100, 11)["rtp"]
        with self.lock:
            m.update(report=body.get("report"), settings=_settings_hash(d),
                     check={"sample": len(body.get("sample") or []), "exact": round(100 * exact, 4),
                            "python_30k": {k: round(x, 2) for k, x in check.items()}},
                     frozen_at=datetime.datetime.now().isoformat(timespec="seconds"))
            d.save()
            return maths_view(d)

    # ------------------------------------------------------------- Sounds
    def set_sound(self, did: str, key: str, files, gain_db=0.0) -> None:
        if key not in machine_moments():
            raise DesignError(f"{key!r} isn't a slot machine sound.")
        if not isinstance(files, list) or len(files) > 12:
            raise DesignError("A moment has up to 12 sounds (one plays at random).")
        if self.sounds is not None:
            for f in files:
                if not self.sounds.file_path(f):
                    raise DesignError(f"There's no sound {f!r} in the library.")
        if not isinstance(gain_db, (int, float)) or not -30 <= gain_db <= 12:
            raise DesignError("Volume trim is -30 to +12 dB.")
        with self.lock:
            d = self.design(did)
            d.data.setdefault("sounds", {})[key] = {"files": list(files), "gain_db": float(gain_db)}
            d.save()

    def inherit_sound(self, did: str, key: str) -> None:
        with self.lock:
            d = self.design(did)
            d.data.get("sounds", {}).pop(key, None)
            d.save()

    # ------------------------------------------------------------- Features
    def update_features(self, did: str, ch: dict) -> None:
        with self.lock:
            d = self.design(did)
            if set(ch) - {"names"}:   # (the names are words on the screen: they don't change how it pays)
                self._unlocked(d)
            f = d.data.setdefault("features", {})
            if "names" in ch:
                names = ch["names"] or {}
                if not isinstance(names, dict) or set(names) - set(base.FEATURES):
                    raise DesignError("Names are {feature: name} for the library's features.")
                f["names"] = {**f.get("names", {}), **{k: " ".join(str(v or "").upper().split())[:22] for k, v in names.items()}}
                f["names"] = {k: v for k, v in f["names"].items() if v and v != FEATURE_NAMES.get(k)}
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
        """Change the bonus games. Every bonus that's on needs a way in, and at least one stays on. A scatter that
        stops starting anything comes off the reels (its counts go to 0), and one that starts something again gets
        Armadillo's back; either way the frozen strips no longer fit, so the maths is unfrozen."""
        with self.lock:
            d = self.design(did)
            self._unlocked(d)
            before = json.loads(json.dumps(d.data.get("bonuses", {})))
            was = bonuses_view(d)["unused_scatters"]
            try:
                self._apply_bonuses(d, ch)
                view = bonuses_view(d)
                for k, what in BONUS_TITLES.items():
                    x = view[k]
                    if x["enabled"] and not x["scatter"] and not (x["buyable"] and view["buy"]["enabled"]):
                        raise DesignError(f"{what} needs a way in: a scatter, or Buy Bonus.")
                if not any(view[k]["enabled"] for k in base.BONUSES):
                    raise DesignError("Keep at least one bonus game on.")
            except Exception:
                d.data["bonuses"] = before
                raise
            self._scatters_moved(d, was, view["unused_scatters"])
            d.save()

    @staticmethod
    def _scatters_moved(d, was: list, now: list) -> None:
        m = d.data.get("maths", {})
        counts = m.get("counts")
        if not counts or was == now:
            return
        for s in base.SCATTERS:
            if s in now:
                for c in counts:
                    c[s] = 0
            elif s in was and not any(c.get(s) for c in counts):
                for c, n in zip(counts, _armadillo_scatters(s)):
                    c[s] = n
        for k in ("strips", "free_strips", "big_strip", "report", "check", "frozen_at", "settings"):
            m.pop(k, None)

    @staticmethod
    def _apply_bonuses(d, ch: dict) -> None:
        b = d.data.setdefault("bonuses", {})
        for k in base.BONUSES:
            if isinstance(ch.get(k), dict):
                w, cur = ch[k], b.setdefault(k, {})
                for flag in ("enabled", "buyable"):
                    if flag in w:
                        cur[flag] = bool(w[flag])
                if "scatter" in w:
                    if w["scatter"] not in (None, *base.SCATTERS):
                        raise DesignError("A bonus starts from the bonus scatter (BS), the free-spins scatter (FS) or neither.")
                    cur["scatter"] = w["scatter"]
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
        if "battle" in ch:
            b["battle"] = StepsMixin._battle_settings(d, ch["battle"], dict(b.get("battle", {})))
        if "voyage" in ch:
            b["voyage"] = StepsMixin._voyage_settings(d, ch["voyage"], dict(b.get("voyage", {})))
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

    @staticmethod
    def _battle_settings(d, t: dict, cur: dict) -> dict:
        """The battle's words and settings, checked. The per-wave lists (return fire, rewards) follow the waves."""
        if not isinstance(t, dict):
            raise DesignError("The battle's settings are an object.")
        now = bonuses_view(d)["battle"]
        for k in BATTLE_WORDS:
            if k in t:
                cur[k] = str(t[k] or "").strip()[:40] or now[k]
        if "waves" in t:
            w = t["waves"]
            if not isinstance(w, list) or not 1 <= len(w) <= 8 or any(not isinstance(n, int) or not 1 <= n <= 12 for n in w):
                raise DesignError("Waves: 1 to 8 of them, each 1 to 12 ships.")
            cur["waves"] = w
        if "shields" in t:
            if not isinstance(t["shields"], int) or not 1 <= t["shields"] <= 9:
                raise DesignError("Shields: 1 to 9 hits a wave.")
            cur["shields"] = t["shields"]
        if "return_fire" in t:
            if not isinstance(t["return_fire"], list):
                raise DesignError("Return fire: a chance for each wave.")
            cur["return_fire"] = [_rate(x, "return fire") for x in t["return_fire"]]
        if "clear" in t:
            c = t["clear"]
            if not isinstance(c, list) or any(not isinstance(x, (int, float)) or not 0 <= x <= 10000 for x in c):
                raise DesignError("Wave rewards: 0 to 10,000 times the bet for each wave.")
            cur["clear"] = c
        for k in BATTLE_PAIRS:
            if k in t:
                cur[k] = _pairs(t[k], {"prizes": "Ship prizes", "spins": "Free spins", "boss": "Boss prizes"}[k])
                if k == "spins" and any(not float(v).is_integer() or v > 20 for v, _ in cur[k]):
                    raise DesignError("Free spins: whole numbers of games, up to 20.")
        if "spins_chance" in t:
            cur["spins_chance"] = _rate(t["spins_chance"], "free spins chance")
        if "boss_hits" in t:
            if not isinstance(t["boss_hits"], int) or not 1 <= t["boss_hits"] <= 20:
                raise DesignError("The boss takes 1 to 20 hits.")
            cur["boss_hits"] = t["boss_hits"]
        if "boss_fire" in t:
            cur["boss_fire"] = _rate(t["boss_fire"], "boss return fire")
        x = {**now, **cur}
        if any(r > 0.9 for r in x["return_fire"] + [x["boss_fire"]]):
            raise DesignError("Return fire tops out at 0.9: a battle needs some shots to land.")
        n = len(x["waves"])
        if len(x["return_fire"]) != n or len(x["clear"]) != n:
            raise DesignError(f"Give return fire and a reward for each of the {n} waves.")
        return cur

    @staticmethod
    def _voyage_settings(d, t: dict, cur: dict) -> dict:
        """The voyage's words and settings, checked. Four artefacts, so four parts of the treasure."""
        if not isinstance(t, dict):
            raise DesignError("The voyage's settings are an object.")
        now = bonuses_view(d)["voyage"]
        for k in VOYAGE_WORDS:
            if k in t:
                cur[k] = str(t[k] or "").strip()[:40] or now[k]
        if "artefacts" in t:
            a = t["artefacts"]
            if not isinstance(a, list) or len(a) != 4:
                raise DesignError("Name the four artefacts.")
            cur["artefacts"] = [str(x or "").strip()[:24] or now["artefacts"][i] for i, x in enumerate(a)]
        if "legs" in t:
            if not isinstance(t["legs"], int) or not 2 <= t["legs"] <= 8:
                raise DesignError("The map has 2 to 8 legs.")
            cur["legs"] = t["legs"]
        if "kinds" in t:
            k = t["kinds"]
            if (not isinstance(k, list) or [r[0] if isinstance(r, list) and r else None for r in k] != list(VOYAGE_KINDS)
                    or any(len(r) != 2 or not isinstance(r[1], (int, float)) or r[1] < 0 for r in k) or not any(r[1] for r in k[:3])):
                raise DesignError("Islands: a weight from 0 for each of " + ", ".join(VOYAGE_KINDS) + " (not all of the first three 0).")
            cur["kinds"] = [[r[0], r[1]] for r in k]
        if "coves" in t:
            if not isinstance(t["coves"], int) or not 0 <= t["coves"] <= 7:
                raise DesignError("Hidden Coves: 0 to 7.")
            cur["coves"] = t["coves"]
        for k in VOYAGE_PAIRS:
            if k in t:
                cur[k] = _pairs(t[k], {"treasure": "Treasure Island", "relics": "Shipwreck relics", "skull": "Skull Island",
                                       "cove": "Hidden Cove"}[k])
                if k == "relics" and any(not float(v).is_integer() or v > 10 for v, _ in cur[k]):
                    raise DesignError("Shipwreck relics: whole numbers, up to 10.")
        for k in ("item_chance", "key_chance", "sink"):
            if k in t:
                cur[k] = _rate(t[k], {"item_chance": "item chance", "key_chance": "key chance", "sink": "sinking chance"}[k])
        for k in ("artefact_price", "key_price", "spins_price", "spins_games"):
            if k in t:
                if not isinstance(t[k], int) or not 1 <= t[k] <= 20:
                    raise DesignError("Port Royal: prices of 1 to 20 relics, and 1 to 20 free games.")
                cur[k] = t[k]
        for k in ("relic_value", "chest", "legend"):
            if k in t:
                if not isinstance(t[k], (int, float)) or not 0 <= t[k] <= 10000:
                    raise DesignError("Relic value, the chest and the legend: 0 to 10,000 times the bet.")
                cur[k] = t[k]
        if "parts" in t:
            p = t["parts"]
            if not isinstance(p, list) or len(p) != 4 or any(not isinstance(x, (int, float)) or not 0 <= x <= 10000 for x in p):
                raise DesignError("The treasure's parts: four values (one an artefact), 0 to 10,000 times the bet.")
            cur["parts"] = p
        x = {**now, **cur}
        if x["sink"] > 0.9:
            raise DesignError("Sinking tops out at 0.9: Skull Island needs a chance of paying.")
        if x["coves"] > x["legs"] - 1:
            raise DesignError(f"Hidden Coves: at most one a leg, from the second ({x['legs'] - 1} here).")
        return cur

    # ------------------------------------------------------------- art slots and specs
    def set_art_slot(self, did: str, key: str, body: dict) -> None:
        """Choose an art slot's picture ("value": "sym:<id>", a board path or None) and/or its adjustments
        ("adjust": {scale, dx, dy, rot, mirror, flip, bright, sat}, or None for none). Either is optional."""
        if key not in ART_SLOTS:
            raise DesignError(f"There's no art slot {key!r}.")
        with self.lock:
            d = self.design(did)
            if "value" in body:
                value = body["value"]
                if value and str(value).startswith("sym:"):
                    d.symbol(str(value)[4:])
                elif value and (not d.path(value) or str(value).startswith("adj/")):   # (adj/: a baked picture, not a source)
                    raise DesignError(f"Not on the board: {value}")
                slots = d.data.setdefault("art_slots", {})
                if value:
                    slots[key] = value
                else:
                    slots.pop(key, None)
            if "adjust" in body:
                a = body["adjust"]
                if a is not None and not isinstance(a, dict):
                    raise DesignError("Adjustments are an object: scale, dx, dy, rot, mirror, flip, bright, sat.")
                try:
                    a = art.adjust_values(a)
                except (TypeError, ValueError):
                    raise DesignError("Adjustments are numbers (mirror and flip are true or false).") from None
                tweaks = d.data.setdefault("art_adjust", {})
                if a == art.ADJUST:
                    tweaks.pop(key, None)
                    d.clear_adjusted(key)
                else:
                    tweaks[key] = {k: v for k, v in a.items() if v != art.ADJUST[k]}
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
            self._unlocked(d)
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

    def queue_logo(self, did: str, spec: dict) -> dict:
        """Three logo takes from the image model: "stylise" (the words rendered in the font, restyled) or "generate"
        (drawn whole from a prompt)."""
        how = spec.get("how")
        if how not in ("stylise", "generate"):
            raise DesignError("A logo is styled from the lettering (stylise) or generated.")
        lines = [str(x).strip()[:30] for x in (spec.get("lines") or []) if str(x).strip()][:3]
        if not lines:
            raise DesignError("Type the logo's words.")
        style = str(spec.get("style") or "").strip()[:400]
        with self.lock:
            d = self.design(did)
            font = _font_path(d, spec.get("font") or "Cinzel-SemiBold.ttf")
            job = self._queue(d, None, {"how": how, "src": None, "text": style, "lines": lines, "font": font.name,
                                        "out": "logo", "action": "logo"})
            lg = d.data.setdefault("scene", {}).setdefault("logo", {})
            lg.update(lines=lines, style=style)
            d.save()
            return job

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

    def bin_scene(self, did: str, path: str) -> None:
        """Hide a background or logo in the Scene's Bin (nothing is deleted); binning the one in use leaves none."""
        with self.lock:
            d = self.design(did)
            if not (isinstance(path, str) and path.startswith(("scene/bg_", "scene/logo_")) and d.path(path)):
                raise DesignError("Pick one of this slot's backgrounds or logos.")
            sc = d.data.setdefault("scene", {})
            if path not in sc.setdefault("binned", []):
                sc["binned"].append(path)
            if sc.get("background") == path:
                sc["background"] = None
            if sc.get("logo", {}).get("file") == path:
                sc["logo"].pop("file")
            d.save()

    def restore_scene(self, did: str, path: str) -> None:
        with self.lock:
            d = self.design(did)
            sc = d.data.setdefault("scene", {})
            if path not in sc.get("binned", []):
                raise DesignError(f"{path!r} isn't in the Bin.")
            sc["binned"].remove(path)
            d.save()

    def update_scene(self, did: str, ch: dict) -> None:
        with self.lock:
            d = self.design(did)
            sc = d.data.setdefault("scene", {})
            for k, v in ch.items():
                if k == "background":
                    if v and not (v.startswith("scene/bg_") and d.path(v) and v not in sc.get("binned", [])):
                        raise DesignError("Pick one of this slot's backgrounds.")
                    sc["background"] = v or None
                elif k == "logo_file":
                    if not (isinstance(v, str) and v.startswith("scene/logo_") and d.path(v) and v not in sc.get("binned", [])):
                        raise DesignError("Pick one of this slot's logos.")
                    sc.setdefault("logo", {})["file"] = v
                elif k == "frame":   # the chosen scene's (a classic skin's frame and deck)
                    if not isinstance(v, dict) or v.get("style") not in FRAME_STYLES or not art.is_colour(v.get("colour")):
                        raise DesignError(f"A frame is a style ({', '.join(FRAME_STYLES)}) and a colour like #c9a24a.")
                    sc["skins"][sc["skin"]]["frame"] = {"style": v["style"], "colour": v["colour"]}
                elif k == "deck":
                    if not isinstance(v, dict) or v.get("style") not in DECK_STYLES or not (v.get("colour") is None or art.is_colour(v["colour"])):
                        raise DesignError(f"A deck is a style ({', '.join(DECK_STYLES)}) and a colour like #c9a24a, or none.")
                    sc["skins"][sc["skin"]]["deck"] = {"style": v["style"], "colour": v.get("colour")}
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
