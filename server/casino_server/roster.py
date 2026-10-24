"""
The NPC roster: who the casino's regulars and staff are, what their traits mean,
and the starting cast (seeded on first run; edited on the admin page after that).

Every punter has one archetype -- how they play a session -- and any number of
modifiers. profile() turns those into the numbers npc.py plays by, so behaviour
lives in one place:

  Grinder    long sessions at optimal lines, small units, rare side bets
  Casual     medium sessions, the odd mistake, side bets now and then
  Gambler    a few hands on high-variance lines, big units; riches or bust
  Whale      plays much higher stakes (a budget 10-30x the usual)
  Chaser     raises the stake after a loss, trying to claw it back
  Hit-and-run  leaves once they're up a set share of their budget
  Superstitious  lucky numbers, a favourite table; avoids where they last went bust
  Regular    comes back far sooner (a short cooldown), and is picked more often
  Card counter  Blackjack: bets up when the count is good
  VIP        a friend of the casino: known to the dealers (perks to come)
"""
import random
from dataclasses import dataclass, field

from casino_server import art, staff

# The built-in roles; the admin page adds staff roles (staff.roles(store) has them all). Staff other than dealers
# aren't on the floor yet.
ROLES = {k: r["label"] for k, r in staff.BUILTIN_ROLES.items()}
ON_THE_FLOOR = ("punter", "dealer")

ARCHETYPES = {
    "grinder": {"label": "Grinder", "about": "Long sessions at optimal lines; small, steady stakes."},
    "casual": {"label": "Casual", "about": "Medium sessions, plays a bit loosely; side bets now and then."},
    "gambler": {"label": "Gambler", "about": "A few hands on high-variance lines, big stakes. Riches or bust."},
}
MODIFIERS = {
    "whale": {"label": "Whale", "about": "Plays much higher stakes."},
    "chaser": {"label": "Chaser", "about": "Raises the stake after a loss to claw it back."},
    "hit_and_run": {"label": "Hit-and-run", "about": "Leaves as soon as they're up a set share of their budget."},
    "superstitious": {"label": "Superstitious", "about": "Lucky numbers and a favourite table; avoids where they last went bust."},
    "regular": {"label": "Regular", "about": "Comes back far sooner, and more often."},
    "card_counter": {"label": "Card counter", "about": "Blackjack: bets up when the count is good."},
    "vip": {"label": "VIP", "about": "A friend of the casino, known to the staff. (Perks to come.)"},
}

# Archetype -> session rounds, mistake rate, unit as a share of the budget, side-bet appetite, side-bet size
# as a share of the main bet, budget (pence).
_SESSIONS = {
    "grinder": {"rounds": (40, 120), "mistakes": 0.0, "unit": (0.01, 0.02), "side": 0.4, "side_size": (0.05, 0.1),
                "budget": (30_000, 150_000)},
    "casual": {"rounds": (10, 30), "mistakes": 0.15, "unit": (0.02, 0.04), "side": 1.0, "side_size": (0.05, 0.2),
               "budget": (10_000, 60_000)},
    "gambler": {"rounds": (3, 10), "mistakes": 0.15, "unit": (0.08, 0.15), "side": 1.6, "side_size": (0.1, 0.3),
                "budget": (20_000, 200_000)},
}
WHALE_BUDGET = (10, 30)       # x the archetype's budget
NICE_UNITS = (100, 200, 500, 1_000, 1_500, 2_000, 2_500, 5_000, 7_500, 10_000, 15_000, 20_000, 25_000, 50_000)

DEFAULT_SETTINGS = {
    "npcs_on": True,            # off: they finish their round and leave, and nobody new comes in
    "population": 6,            # punters on the floor
    "cooldown_min": (30, 60),   # minutes away after an ordinary visit
    "bust_cooldown_min": (120, 240),
    "regular_cooldown": 0.3,    # x for Regulars
    "dealer_shift_min": 20,     # minutes before a dealer is relieved
    "dealer_stagger_min": 2,    # between tables' reliefs
}


@dataclass
class Profile:
    """How a punter plays this visit (from their archetype and modifiers)."""
    archetype: str
    rounds: int
    mistakes: float
    unit_share: float
    side_appetite: float
    side_share: float             # a side bet as a share of the main bet
    aggressive: bool
    chaser: bool
    hit_and_run: float | None     # leave once up this share of the budget
    riches: float | None          # a Gambler leaves once their bankroll is this multiple of the budget
    superstitious: bool
    lucky: tuple
    favourite_games: tuple
    avoid_table: str | None
    card_counter: bool
    regular: bool
    vip: bool
    budget: int = 0
    traits: tuple = field(default_factory=tuple)


def budget_range(npc: dict) -> tuple[int, int]:
    s = npc.get("settings") or {}
    lo, hi = _SESSIONS.get(npc.get("archetype") or "casual", _SESSIONS["casual"])["budget"]
    if "whale" in npc.get("traits", []):
        lo, hi = lo * WHALE_BUDGET[0], hi * WHALE_BUDGET[1]
    return int(s.get("budget_min") or lo), int(s.get("budget_max") or hi)


def profile(npc: dict, rng: random.Random) -> Profile:
    arch = npc.get("archetype") or "casual"
    base = _SESSIONS.get(arch, _SESSIONS["casual"])
    traits = tuple(npc.get("traits", []))
    s = npc.get("settings") or {}
    lo, hi = budget_range(npc)
    return Profile(
        archetype=arch, rounds=rng.randint(*base["rounds"]), mistakes=base["mistakes"],
        unit_share=rng.uniform(*base["unit"]), side_appetite=base["side"],
        side_share=rng.uniform(*base["side_size"]), aggressive=arch == "gambler",
        chaser="chaser" in traits,
        hit_and_run=float(s.get("hit_and_run_pct", 50)) / 100 if "hit_and_run" in traits else None,
        riches=2.0 if arch == "gambler" else None,
        superstitious="superstitious" in traits, lucky=tuple(s.get("lucky_numbers") or ()),
        favourite_games=tuple(s.get("favourite_games") or ()), avoid_table=s.get("avoid_table"),
        card_counter="card_counter" in traits, regular="regular" in traits, vip="vip" in traits,
        budget=rng.randrange(lo, hi + 1, 100) if hi > lo else lo, traits=traits)


def nice_unit(pence: float) -> int:
    """The chip-friendly stake nearest a target amount (never below £1)."""
    return min(NICE_UNITS, key=lambda u: abs(u - pence)) if pence >= 100 else 100


# ---------------------------------------------------------------------- looks
_COLOURS = ("black", "navy", "maroon", "forest", "teal", "white", "gray", "charcoal", "tan", "brown", "blue",
            "red", "rose", "lavender", "slate", "sky", "walnut", "green", "purple", "orange", "yellow")
_HAIR_COLOURS = ("black", "dark_brown", "chestnut", "blonde", "ginger", "gray", "raven", "light_brown", "white",
                 "platinum", "redhead", "sandy", "strawberry", "gold")


def random_look(rng: random.Random, body: str | None = None, uniform: dict | None = None) -> dict:
    """A plausible random look (in a uniform for staff: the uniform's pieces for that body)."""
    body = body or rng.choice(art.BODIES)
    cat = {s["slot"]: s for s in art.catalogue()["slots"]}

    def pick(slot, avoid=()):
        opts = [o for o in cat[slot]["options"] if body in o["bodies"] and o["id"] not in avoid]
        o = rng.choice(opts)
        cols = [c for c in o["colours"] if c in _COLOURS + _HAIR_COLOURS] or o["colours"]
        return [o["id"], rng.choice(cols)]

    def hair():
        styles = [o for o in cat["hair"]["options"] if body in o["bodies"]]
        o = rng.choice(styles)
        cols = [c for c in o["colours"] if c in _HAIR_COLOURS] or o["colours"]
        return [o["id"], rng.choice(cols)]

    spec = {"body": body, "skin": rng.choice(art.SKINS), "hair": hair()}
    if uniform:
        spec.update({k: list(v) for k, v in uniform.items()})
    else:
        spec["top"] = pick("top", avoid=("formal",))
        spec["bottom"] = pick("bottom", avoid=("skirt", "skirt_straight", "leggings") if body == "male" else ())
        spec["shoes"] = pick("shoes")
        if rng.random() < 0.15:
            spec["over"] = pick("over") if body == "male" else None
        if rng.random() < 0.2:
            spec["glasses"] = pick("glasses")
        if rng.random() < 0.08:
            spec["neck"] = pick("neck")
        if rng.random() < 0.05:
            spec["hat"] = pick("hat")
    if body == "male" and rng.random() < (0.15 if uniform else 0.3):
        b = pick("beard")
        b[1] = spec["hair"][1] if spec["hair"][1] in [c for o in cat["beard"]["options"] if o["id"] == b[0] for c in o["colours"]] else b[1]
        spec["beard"] = b
    return art.validate(spec)


# ---------------------------------------------------------------------- the starting cast
PUNTER_NAMES = ["Rita", "Dev", "Marcus", "June", "Theo", "Priya", "Sal", "Bea", "Otis", "Lena",
                "Ray", "Ivy", "Gus", "Nora", "Felix", "Mabel", "Arlo", "Tess", "Omar", "Edie"]
DEALER_NAMES = ["Sofia", "Hector", "Amara", "Giles", "Yuki", "Darius", "Elena", "Kofi", "Margot", "Ravi",
                "Celeste", "Bruno", "Ines", "Tobias", "Mei", "Anton", "Rosalind", "Jonas", "Farah", "Callum"]
FEMALE = {"Rita", "June", "Priya", "Bea", "Lena", "Ivy", "Nora", "Mabel", "Tess", "Edie",
          "Sofia", "Amara", "Yuki", "Elena", "Margot", "Celeste", "Ines", "Mei", "Rosalind", "Farah"}


def seed(store, rng: random.Random | None = None):
    """The first cast, if the roster's empty: 20 punters (a spread of archetypes and
    modifiers) and 20 dealers in uniform (one for each of the 15 tables, and some to relieve them)."""
    if store.npcs(archived=None):
        return
    rng = rng or random.Random(2026)
    archetypes = ["grinder"] * 6 + ["casual"] * 9 + ["gambler"] * 5
    rng.shuffle(archetypes)
    for name, arch in zip(PUNTER_NAMES, archetypes):
        traits = [m for m, p in (("whale", 0.1), ("chaser", 0.2), ("hit_and_run", 0.15), ("superstitious", 0.2),
                                 ("regular", 0.3), ("card_counter", 0.08), ("vip", 0.1)) if rng.random() < p]
        settings = {}
        if "superstitious" in traits:
            settings["lucky_numbers"] = sorted(rng.sample(range(37), rng.randint(2, 4)))
        body = "female" if name in FEMALE else "male"
        store.create_npc({"name": name, "role": "punter", "look": random_look(rng, body), "archetype": arch,
                          "traits": traits, "settings": settings, "enabled": True})
    for name in DEALER_NAMES:
        body = "female" if name in FEMALE else "male"
        store.create_npc({"name": name, "role": "dealer", "look": random_look(rng, body, uniform=art.UNIFORMS["dealer"][body]),
                          "archetype": "", "traits": [], "settings": {}, "enabled": True})


# ---------------------------------------------------------------------- bulk creation (the admin page)
# Name pools by body, beyond the starting cast; generate() never repeats a name already on the roster.
MORE_FEMALE = ["Ada", "Agnes", "Alma", "Anya", "Aurora", "Bella", "Bridget", "Carmen", "Cleo", "Dahlia", "Daisy",
               "Della", "Dora", "Eloise", "Esme", "Etta", "Faye", "Flora", "Freya", "Greta", "Hazel", "Hilda",
               "Iris", "Isla", "Jade", "Joy", "Kat", "Kira", "Lola", "Lucia", "Luz", "Maeve", "Maya", "Mina",
               "Nell", "Nia", "Olive", "Opal", "Pearl", "Pia", "Queenie", "Rosa", "Ruby", "Sadie", "Sage", "Stella",
               "Tilly", "Uma", "Vera", "Viola", "Wren", "Xena", "Yara", "Zara", "Zelda", "Gloria", "Martha", "Polly"]
MORE_MALE = ["Abe", "Alf", "Angus", "Barney", "Bert", "Boris", "Cal", "Cedric", "Clive", "Conor", "Cyril", "Dante",
             "Dex", "Eddie", "Elias", "Ezra", "Frank", "Fraser", "Hal", "Hugo", "Ike", "Jasper", "Jude", "Kai",
             "Kit", "Leo", "Lloyd", "Luca", "Mack", "Milo", "Monty", "Nico", "Ned", "Ollie", "Oscar", "Pablo",
             "Percy", "Quinn", "Rafe", "Reggie", "Rex", "Rufus", "Sid", "Silas", "Stan", "Teddy", "Tariq", "Ulric",
             "Vince", "Wes", "Walt", "Yusuf", "Zane", "Duke", "Lenny", "Moe", "Archie", "Vic"]
NAMES = {"female": [n for n in PUNTER_NAMES + DEALER_NAMES if n in FEMALE] + MORE_FEMALE,
         "male": [n for n in PUNTER_NAMES + DEALER_NAMES if n not in FEMALE] + MORE_MALE}
ARCHETYPE_MIX = {"grinder": 0.3, "casual": 0.45, "gambler": 0.25}   # "mix": roughly the starting cast's spread
MAX_BULK = 30


def random_name(rng: random.Random, body: str, taken: set[str]) -> str:
    """A first name for that body nobody has (case-insensitively); "Rita K." once the pool runs dry."""
    low = {t.lower() for t in taken}
    free = [n for n in NAMES[body] if n.lower() not in low]
    if free:
        return rng.choice(free)
    for _ in range(500):
        n = f"{rng.choice(NAMES[body])} {rng.choice('ABCDEFGHJKLMNPRSTVW')}."
        if n.lower() not in low:
            return n
    return f"{rng.choice(NAMES[body])} {rng.randint(100, 999)}"


def lucky_numbers(rng: random.Random) -> list[int]:
    return sorted(rng.sample(range(37), rng.randint(2, 4)))


def generate(count: int, role: str = "punter", archetype: str = "mix", body: str = "", traits=(),
             taken=(), enabled: bool = True, rng: random.Random | None = None, roles: dict | None = None,
             uniform: dict | None = None) -> list[dict]:
    """Drafts for the admin page to review (nothing is saved): `count` NPCs of a role with
    random names and looks. A punter's style is the one given, or a mix; traits are only
    the ones asked for (none by default). Staff come in `uniform` ({male, female} pieces,
    their role's) if it has one. `roles`: every role there is (staff.roles)."""
    rng = rng or random.Random()
    if not 1 <= count <= MAX_BULK:
        raise ValueError(f"Make 1-{MAX_BULK} at a time.")
    if role not in (roles or ROLES):
        raise ValueError(f"Unknown role {role!r}.")
    if role == "punter" and archetype != "mix" and archetype not in ARCHETYPES:
        raise ValueError("Pick a style: Grinder, Casual, Gambler or a mix.")
    if body and body not in art.BODIES:
        raise ValueError(f"Unknown body {body!r}.")
    traits = list(dict.fromkeys(traits)) if role == "punter" else []
    bad = [t for t in traits if t not in MODIFIERS]
    if bad:
        raise ValueError(f"Unknown trait {bad[0]!r}.")
    taken = set(taken)
    out = []
    for _ in range(count):
        b = body or rng.choice(art.BODIES)
        name = random_name(rng, b, taken)
        taken.add(name)
        rec = {"name": name, "role": role, "archetype": "", "traits": [], "settings": {}, "enabled": enabled,
               "look": random_look(rng, b, uniform=uniform[b] if uniform and role != "punter" else None)}
        if role == "punter":
            rec["archetype"] = archetype if archetype != "mix" else \
                rng.choices(list(ARCHETYPE_MIX), weights=list(ARCHETYPE_MIX.values()))[0]
            rec["traits"] = list(traits)
            if "superstitious" in traits:
                rec["settings"]["lucky_numbers"] = lucky_numbers(rng)
        out.append(rec)
    return out

def settings(store) -> dict:
    saved = store.get_json("npc_settings", {})
    return {**DEFAULT_SETTINGS, **{k: v for k, v in saved.items() if k in DEFAULT_SETTINGS}}


GAMES = {"three_card_poker": "Three Card Poker", "blackjack": "Blackjack", "mississippi_stud": "Mississippi Stud",
         "pai_gow_fortune": "Fortune Pai Gow", "pai_gow_face_up": "Face Up Pai Gow",
         "ultimate_texas_holdem": "Ultimate Texas Hold'em", "let_it_ride": "Let It Ride",
         "high_card_flush": "High Card Flush", "baccarat": "Baccarat", "roulette": "Roulette", "craps": "Craps",
         "slots": "Slots"}


def clean(data: dict, existing: dict | None = None, roles: dict | None = None) -> dict:
    """An NPC from the admin page, checked: ValueError says what's wrong. `roles`: every role there is (staff.roles)."""
    base = existing or {}
    out = {}
    name = str(data.get("name", base.get("name", ""))).strip()
    if not name or len(name) > 24:
        raise ValueError("Give them a name (up to 24 characters).")
    out["name"] = name
    role = data.get("role", base.get("role", "punter"))
    if role not in (roles or ROLES):
        raise ValueError(f"Unknown role {role!r}.")
    out["role"] = role
    try:
        out["look"] = art.validate(data.get("look", base.get("look") or {}))
    except art.ArtError as e:
        raise ValueError(str(e))
    if role == "punter":
        arch = data.get("archetype", base.get("archetype") or "casual")
        if arch not in ARCHETYPES:
            raise ValueError("Pick how they play: Grinder, Casual or Gambler.")
        out["archetype"] = arch
        traits = list(dict.fromkeys(data.get("traits", base.get("traits", []))))
        bad = [t for t in traits if t not in MODIFIERS]
        if bad:
            raise ValueError(f"Unknown trait {bad[0]!r}.")
        out["traits"] = traits
    else:
        out["archetype"], out["traits"] = "", []
    s = dict(data.get("settings", base.get("settings", {})) or {})
    clean_s = {}
    if s.get("budget_min") or s.get("budget_max"):
        lo, hi = int(s.get("budget_min") or 0), int(s.get("budget_max") or 0)
        if lo < 500 or hi < lo:
            raise ValueError("A budget is at least £5, and the most can't be below the least.")
        clean_s["budget_min"], clean_s["budget_max"] = lo, hi
    if s.get("lucky_numbers"):
        nums = sorted({int(n) for n in s["lucky_numbers"]})
        if any(n < 0 or n > 36 for n in nums) or len(nums) > 8:
            raise ValueError("Lucky numbers are 0-36, up to eight of them.")
        clean_s["lucky_numbers"] = nums
    if s.get("favourite_games"):
        games = [g for g in s["favourite_games"] if g in GAMES]
        clean_s["favourite_games"] = games
    if s.get("hit_and_run_pct") not in (None, ""):
        pct = int(s["hit_and_run_pct"])
        if not 5 <= pct <= 500:
            raise ValueError("Hit-and-run leaves when up 5-500% of their budget.")
        clean_s["hit_and_run_pct"] = pct
    if s.get("avoid_table"):
        clean_s["avoid_table"] = str(s["avoid_table"])
    out["settings"] = clean_s
    out["enabled"] = bool(data.get("enabled", base.get("enabled", True)))
    return out


def clean_settings(data: dict) -> dict:
    out = {}
    if "npcs_on" in data:
        out["npcs_on"] = bool(data["npcs_on"])
    if "population" in data:
        n = int(data["population"])
        if not 0 <= n <= 30:
            raise ValueError("The floor takes 0-30 punters.")
        out["population"] = n
    for key in ("cooldown_min", "bust_cooldown_min"):
        if key in data:
            lo, hi = (float(x) for x in data[key])
            if lo < 0 or hi < lo or hi > 7 * 24 * 60:
                raise ValueError("Cooldowns are 0 minutes to a week, the longest not below the shortest.")
            out[key] = [lo, hi]
    if "regular_cooldown" in data:
        out["regular_cooldown"] = max(0.05, min(1.0, float(data["regular_cooldown"])))
    for key in ("dealer_shift_min", "dealer_stagger_min"):
        if key in data:
            v = float(data[key])
            if not 0.5 <= v <= 240:
                raise ValueError("Dealer shifts and staggers are 0.5-240 minutes.")
            out[key] = v
    return out
