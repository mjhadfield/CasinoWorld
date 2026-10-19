"""
Armadillo Goes West (after EveryMatrix/SlotMatrix's game; rules sheet in docs/slots/reference).
Signed off by Mike on 2026-10-18 from the mockup (docs/slots/mockup): the game returns about
91.5%, the shared progressives 3.75% more; Buy Bonus (45x) about 93.7%.

The strips are frozen from the mockup's buildStrip (seeds 1000+reel, 2000+reel, 3000), so the
Python engine and the mockup give the same spin for the same seed.
"""
from dataclasses import dataclass, field


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
    extras: dict = field(default_factory=dict)


BASE_STRIPS = [
    ["L2", "M2", "M3", "H2", "M2", "L2", "M4", "L4", "M1", "M1", "BS", "L4", "M4", "M2", "L3", "H2", "H1", "L4", "M3", "L1", "M4", "M1", "M3", "L1", "M3", "L2", "L1", "L4", "L1", "M4", "L3", "L2", "FS", "L3", "M2", "M1", "H1", "M4", "L4", "L4", "M1", "L1", "L1", "L2", "H2", "M2", "M3", "H1", "L3", "L2", "L3", "L3"],
    ["M4", "M1", "H2", "L2", "L1", "W", "L2", "M2", "L4", "L3", "H1", "M4", "L4", "W", "M4", "L3", "L3", "M3", "L3", "M1", "W", "L1", "L1", "L2", "L4", "M1", "M2", "L2", "M3", "BS", "W", "L3", "L2", "H2", "M3", "M2", "M1", "L4", "L4", "M3", "L3", "L1", "M3", "M4", "H1", "FS", "M2", "L1", "L2", "M4", "L4", "L1", "M2", "H1", "M1", "H2"],
    ["L4", "L2", "L1", "L3", "L1", "L3", "L1", "W", "L4", "W", "BS", "L4", "M1", "M2", "L3", "L2", "M4", "BS", "L4", "M4", "H1", "M2", "M1", "M1", "M4", "L4", "M3", "H2", "L4", "L1", "H1", "L2", "L2", "M3", "FS", "L1", "L3", "W", "M2", "L3", "H2", "M1", "M1", "L2", "W", "M2", "L2", "H1", "L3", "H2", "M2", "L1", "M4", "M3", "M3", "M4", "M3"],
    ["M1", "H1", "FS", "M1", "L2", "W", "M2", "L1", "L4", "M3", "M4", "M3", "W", "H2", "L3", "L1", "H2", "W", "M3", "L1", "H2", "L4", "L2", "L2", "M4", "W", "M4", "M3", "L1", "L3", "H1", "L1", "M4", "M2", "L1", "M1", "BS", "L2", "M2", "L4", "L2", "L2", "L3", "M2", "L3", "M1", "H1", "L3", "L4", "M3", "L3", "M4", "L4", "L4", "M1", "M2"],
    ["L4", "L4", "M1", "L3", "L2", "L1", "M3", "M1", "L2", "L1", "L3", "M3", "H1", "L2", "M2", "L3", "M3", "H1", "L4", "H1", "L3", "W", "L2", "L3", "L1", "M3", "FS", "L4", "L3", "M4", "L4", "M3", "W", "M2", "L1", "M1", "H2", "BS", "M2", "H2", "W", "M4", "M1", "L4", "L2", "M1", "L2", "M2", "L1", "M4", "W", "M4", "L1", "M4", "M2", "H2"],
]
FREE_STRIPS = [
    ["H2", "H1", "L1", "M2", "H2", "L1", "M1", "M2", "L2", "M2", "L2", "M1", "L2", "M2", "L2", "L4", "M3", "L4", "M4", "L3", "H1", "L2", "L3", "L4", "M4", "L1", "L2", "L3", "M4", "L1", "L3", "H1", "M1", "L3", "M2", "M3", "M4", "M4", "M3", "L4", "M1", "L3", "M3", "L1", "M3", "L4", "H2", "L1", "M1", "L4"],
    ["L3", "M3", "L3", "H2", "L4", "H1", "M2", "M4", "H1", "M4", "L2", "W", "L4", "L1", "M2", "L1", "L3", "L1", "L1", "L2", "L3", "W", "M3", "M4", "M3", "M3", "L2", "L2", "M1", "H2", "L4", "M1", "M4", "M1", "L2", "L2", "M1", "M3", "M2", "M1", "L1", "L4", "L4", "L3", "L3", "W", "M2", "H2", "M2", "W", "L1", "L4", "M4", "H1"],
    ["M2", "L2", "M3", "M4", "L2", "M4", "H2", "H2", "L1", "W", "M1", "L3", "L1", "H1", "M2", "M3", "M3", "L1", "M4", "M1", "L2", "L1", "M2", "L3", "L4", "M2", "M1", "W", "W", "M1", "L4", "H2", "H1", "M4", "M3", "L2", "L2", "M4", "L4", "L4", "L2", "L3", "M3", "L4", "H1", "L1", "L1", "W", "L3", "L3", "M1", "L3", "L4", "M2"],
    ["L3", "M1", "M2", "L4", "L3", "M1", "M1", "H2", "M3", "L2", "M3", "H1", "L1", "L3", "M4", "H2", "H2", "M2", "H1", "L1", "M4", "L1", "M4", "L3", "L2", "M4", "L1", "L2", "M2", "M2", "L1", "L4", "L3", "M1", "L2", "L4", "W", "L2", "L2", "M1", "L3", "W", "L4", "H1", "M4", "M2", "M3", "L1", "L4", "W", "M3", "W", "L4", "M3"],
    ["L4", "M3", "M1", "M2", "M1", "W", "L3", "M1", "M4", "L2", "M2", "M3", "M3", "L4", "W", "L4", "M2", "L1", "H1", "L1", "L2", "H1", "L3", "H1", "L1", "H2", "L3", "L4", "L1", "M4", "M4", "M2", "L4", "M4", "L2", "M1", "M1", "M3", "M3", "W", "L3", "L4", "M4", "L3", "H2", "L2", "H2", "L1", "W", "L2", "L1", "L3", "L2", "M2"],
]
BIG_STRIP = ["L2", "L4", "L4", "L3", "M1", "L2", "L1", "M4", "M3", "M4", "L1", "L1", "L3", "L3", "M2", "L4", "H2", "M1", "W", "M4", "H1", "H1", "L2", "M2", "M2", "L4", "M3", "L3", "L1", "H2", "M1", "M3", "L2"]


VARIANT = SlotVariant(
    id="armadillo",
    name="Armadillo Goes West",
    symbols={"W": "Wild", "H1": "Armadillo", "H2": "Snake", "M1": "Hat", "M2": "Horseshoe", "M3": "Whiskey",
             "M4": "Boots", "L1": "Spade", "L2": "Club", "L3": "Diamond", "L4": "Heart", "BS": "Bonus",
             "FS": "Free Spins"},
    strips=BASE_STRIPS,
    free_strips=FREE_STRIPS,
    big_strip=BIG_STRIP,
    rates={"wilds": 0.07, "wildReels": 0.014, "colossal": 0.02, "multiplier": 0.035, "upgrade": 0.06,
           "repeat": 0.04, "instant": 0.008},
    free_rates={"wilds": 0.6, "wildReels": 0.32, "colossal": 0.3, "multiplier": 0.5, "upgrade": 0.45,
                "repeat": 0.35, "instant": 0.25},
    wild_counts=[(1, 40), (2, 30), (3, 20), (4, 10)],
    wild_reel_counts=[(1, 70), (2, 25), (3, 5)],
    colossal_sizes=[(2, 60), (3, 30), (4, 10)],
    multipliers=[(2, 50), (3, 25), (4, 15), (5, 10)],
    repeats=[(2, 60), (3, 25), (4, 10), (5, 5)],
    instants=[(1, 30), (2, 25), (3, 15), (5, 12), (10, 9), (20, 5), (50, 2.5), (100, 1), (200, 0.5)],
    trail={
        "length": 120,
        "prizepot": 2000,
        # every board has exactly these, shuffled; the rest of its spaces are coins
        "counts": {"snake": 20, "heart": 2, "forward": 3, "back": 3, "lightning": 2, "crate": 3},
        "upgrade_chance": 0.2,
        "double_chance": 0.4,
        "coins": [(1, 30), (2, 26), (3, 17), (5, 12), (10, 8), (20, 4.5), (50, 2.2), (100, 0.9), (200, 0.4)],
        "crate_radius": [(1, 50), (2, 35), (3, 15)],
    },
    buy_cost=45,
    free_games=3,
)
