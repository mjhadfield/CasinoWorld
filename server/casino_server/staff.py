"""
Staff roles and uniforms (the admin NPCs tab's Staff & uniforms view).

Punter and Dealer are fixed roles. The rest are staff roles: four come built in (cocktail waiter, pit boss, cashier,
bartender) and the admin page adds more (a Waitress, say). Every staff role, and the dealers, can have a uniform; a
uniform is either the same pieces for both bodies or a male and a female version. Uniforms cover what you'd be issued
(top, over, bottom, shoes, neck, hat); hair, beard and glasses stay the person's own.

The built-in uniforms (art.UNIFORMS) can be changed but not deleted, and the built-in roles keep their names but can
change uniform. Only added roles and uniforms can be deleted, and only while nobody's using them.

Stored in meta "staff" as {"roles": {key: {label, uniform}}, "uniforms": {key: {name, fits, male, female}}}, holding
only what's been added or changed; load() lays that over the built-ins.
"""
import re

from casino_server import art

UNIFORM_SLOTS = ("top", "over", "bottom", "shoes", "neck", "hat")
FIXED = ("punter", "dealer")
BUILTIN_ROLES = {
    "punter": {"label": "Punter", "uniform": ""},
    "dealer": {"label": "Dealer", "uniform": "dealer"},
    "cocktail_waiter": {"label": "Cocktail waiter", "uniform": "cocktail_waiter"},
    "pit_boss": {"label": "Pit boss", "uniform": "pit_boss"},
    "cashier": {"label": "Cashier", "uniform": "cashier"},
    "bartender": {"label": "Bartender", "uniform": "bartender"},
}
BUILTIN_UNIFORMS = {key: {"name": BUILTIN_ROLES[key]["label"], "fits": "split", **pieces}
                    for key, pieces in art.UNIFORMS.items()}
MAX_NAME = 24


def _saved(store) -> dict:
    s = store.get_json("staff", {})
    return {"roles": dict(s.get("roles") or {}), "uniforms": dict(s.get("uniforms") or {})}


def load(store) -> dict:
    """Every role and uniform, built-in ones first, each marked `builtin`."""
    saved = _saved(store)
    roles = {}
    for key, r in {**BUILTIN_ROLES, **saved["roles"]}.items():
        roles[key] = {**r, "label": BUILTIN_ROLES[key]["label"] if key in BUILTIN_ROLES else r["label"],
                      "builtin": key in BUILTIN_ROLES}
    if roles["punter"]["uniform"]:
        roles["punter"]["uniform"] = ""
    uniforms = {key: {**u, "builtin": key in BUILTIN_UNIFORMS} for key, u in {**BUILTIN_UNIFORMS, **saved["uniforms"]}.items()}
    for r in roles.values():   # (a uniform that's gone)
        if r["uniform"] and r["uniform"] not in uniforms:
            r["uniform"] = ""
    return {"roles": roles, "uniforms": uniforms}


def roles(store) -> dict[str, str]:
    """Role key -> label."""
    return {k: r["label"] for k, r in load(store)["roles"].items()}


def role_uniform(store, role: str) -> dict | None:
    """The uniform a role wears ({male: pieces, female: pieces}), or None."""
    data = load(store)
    key = data["roles"].get(role, {}).get("uniform")
    return data["uniforms"].get(key) if key else None


def dress(look: dict, pieces: dict) -> dict:
    """`look` in a uniform: whatever it had in the uniform's slots comes off, then the uniform goes on."""
    out = {k: v for k, v in look.items() if k not in UNIFORM_SLOTS}
    out.update({k: list(v) for k, v in pieces.items()})
    return out


def _slug(label: str, taken) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "role"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}_{n}", n + 1
    return key


def _name(data: dict, what: str) -> str:
    name = " ".join(str(data.get("name") or data.get("label") or "").split())
    if not name or len(name) > MAX_NAME:
        raise ValueError(f"Give the {what} a name (up to {MAX_NAME} characters).")
    return name


def _pieces(raw, body: str) -> dict:
    """A uniform's pieces for one body, checked by building a look from them."""
    raw = raw if isinstance(raw, dict) else {}
    pieces = {slot: [str(raw[slot][0]), str(raw[slot][1])] for slot in UNIFORM_SLOTS
              if isinstance(raw.get(slot), (list, tuple)) and len(raw[slot]) == 2 and raw[slot][0]}
    try:
        art.validate({"body": body, "skin": art.SKINS[0], **pieces})
    except art.ArtError as e:
        raise ValueError(f"{body.title()}: {e}")
    return pieces


def clean_uniform(data: dict) -> dict:
    """A uniform from the admin page: {name, fits: "same", pieces} or {name, fits: "split", male, female}."""
    name = _name(data, "uniform")
    fits = data.get("fits")
    if fits == "same":
        raw = data.get("pieces") or data.get("male")
        try:
            pieces = _pieces(raw, "male")
            _pieces(raw, "female")
        except ValueError as e:
            raise ValueError(f"{e} (the same for both: every piece has to come in both fits)")
        return {"name": name, "fits": "same", "male": pieces, "female": dict(pieces)}
    if fits == "split":
        return {"name": name, "fits": "split", "male": _pieces(data.get("male"), "male"),
                "female": _pieces(data.get("female"), "female")}
    raise ValueError("A uniform is either the same for both, or has male and female versions.")


def save_uniform(store, key: str | None, data: dict) -> str:
    """Add a uniform (key None) or change one. Returns its key."""
    saved = _saved(store)
    every = load(store)["uniforms"]
    rec = clean_uniform(data)
    if key is None:
        key = _slug(rec["name"], set(every))
    elif key not in every:
        raise KeyError(key)
    if any(u["name"].lower() == rec["name"].lower() for k, u in every.items() if k != key):
        raise ValueError(f"There's already a uniform called {rec['name']}.")
    saved["uniforms"][key] = rec
    store.set_json("staff", saved)
    return key


def delete_uniform(store, key: str):
    data = load(store)
    if key not in data["uniforms"]:
        raise KeyError(key)
    if data["uniforms"][key]["builtin"]:
        raise ValueError("The built-in uniforms can be changed but not deleted.")
    wearing = [r["label"] for r in data["roles"].values() if r["uniform"] == key]
    if wearing:
        raise ValueError(f"{', '.join(wearing)} {'wears' if len(wearing) == 1 else 'wear'} it: give "
                         f"{'that role' if len(wearing) == 1 else 'those roles'} another uniform first.")
    saved = _saved(store)
    saved["uniforms"].pop(key, None)
    store.set_json("staff", saved)


def save_role(store, key: str | None, data: dict) -> str:
    """Add a staff role (key None) or change one: its name (added roles only) and its uniform."""
    saved = _saved(store)
    every = load(store)
    if key is not None and key not in every["roles"]:
        raise KeyError(key)
    uniform = str(data.get("uniform") or "")
    if uniform and uniform not in every["uniforms"]:
        raise ValueError("Pick a uniform from the list (or none).")
    if key == "punter" and uniform:
        raise ValueError("Punters wear their own clothes.")
    if key in BUILTIN_ROLES:
        rec = {"label": BUILTIN_ROLES[key]["label"], "uniform": uniform}
    else:
        label = _name(data, "role")
        if any(r["label"].lower() == label.lower() for k, r in every["roles"].items() if k != key):
            raise ValueError(f"There's already a role called {label}.")
        key = key or _slug(label, set(every["roles"]))
        rec = {"label": label, "uniform": uniform}
    saved["roles"][key] = rec
    store.set_json("staff", saved)
    return key


def delete_role(store, key: str, people: int):
    """Delete an added role. `people`: how many NPCs (archived ones too) have it; it must be none."""
    data = load(store)
    if key not in data["roles"]:
        raise KeyError(key)
    if data["roles"][key]["builtin"]:
        raise ValueError("Only roles you've added can be deleted.")
    if people:
        raise ValueError(f"{people} NPC{'s have' if people != 1 else ' has'} this role (archived ones count): "
                         "give them another role first.")
    saved = _saved(store)
    saved["roles"].pop(key, None)
    store.set_json("staff", saved)
