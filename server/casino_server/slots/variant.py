"""
What a slot variant is: its theme's names for the tiers, its reel strips, pays, upgrade chain, which features it
uses and how often, and its bonus games' settings. Armadillo Goes West is written in Python
(variants/armadillo.py); slots built with the admin page's Slot design wizard are data (variants/<id>.json,
written by its Build step) and load through from_json.

The pays, upgrade chain and feature list default to the house standard in base.py (Armadillo's), so a variant
only states what it changes. Tier ids are W (Wild), H1..Hn, M1..Mn, L1..Ln, BS and FS (the scatters).
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

from casino_server.slots import base


@dataclass(frozen=True)
class SlotVariant:
    id: str
    name: str
    symbols: dict                 # tier -> what this theme calls it
    strips: list                  # base game, one per reel (the top row shows strip[stop])
    free_strips: list             # free games: no scatters
    big_strip: list               # the big symbols Colossal Reels spin
    rates: dict                   # chance of each random feature on a paid spin
    free_rates: dict              # ...and on a free game (at least one is guaranteed)
    wild_counts: list
    wild_reel_counts: list
    colossal_sizes: list
    multipliers: list
    repeats: list
    instants: list                # Instant Win, in multiples of the bet
    trail: dict
    buy_cost: int = 45            # Buy Bonus, in bets (0: no Buy Bonus)
    free_games: int = 3
    pays: dict = field(default_factory=lambda: dict(base.PAYS))           # tier -> pays for 3, 4, 5 (line bets)
    upgrades: dict = field(default_factory=lambda: dict(base.UPGRADES))   # Symbol Upgrade: tier -> the tier above
    features: list = field(default_factory=lambda: list(base.FEATURES))   # in library order (draw order matters)
    art: dict = field(default_factory=dict)      # role -> art id, for feature and bonus pictures (the client's SlotArt)
    theme: dict = field(default_factory=dict)    # the screen's and cabinet's look (Sprites step); {} = Armadillo's
    extras: dict = field(default_factory=dict)


def _pairs(rows) -> list:
    return [tuple(r) for r in rows]


def from_json(path: Path) -> SlotVariant:
    """A variant the Slot design wizard built (its Build step writes the file, strips frozen)."""
    d = json.loads(Path(path).read_text())
    for tier, p in d["pays"].items():
        if len(p) != 3:
            raise ValueError(f"{path.name}: {tier} needs pays for 3, 4 and 5")
    return SlotVariant(
        id=d["id"], name=d["name"], symbols=d["symbols"], strips=d["strips"], free_strips=d["free_strips"],
        big_strip=d["big_strip"], rates=d["rates"], free_rates=d["free_rates"],
        wild_counts=_pairs(d["wild_counts"]), wild_reel_counts=_pairs(d["wild_reel_counts"]),
        colossal_sizes=_pairs(d["colossal_sizes"]), multipliers=_pairs(d["multipliers"]), repeats=_pairs(d["repeats"]),
        instants=_pairs(d["instants"]),
        trail={**d["trail"], **{k: _pairs(d["trail"][k]) for k in ("coins", "crate_radius") if k in d["trail"]}},
        buy_cost=d.get("buy_cost", 45), free_games=d.get("free_games", 3),
        pays={k: tuple(v) for k, v in d["pays"].items()}, upgrades=d["upgrades"], features=d["features"],
        art=d.get("art", {}), theme=d.get("theme", {}), extras=d.get("extras", {}))
