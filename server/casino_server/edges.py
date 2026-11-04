"""
What the house expects to win on every bet spot, for the tracker's "actual against EV" (tracking.py and the admin
page's House section). The figures live in edges.json beside this file, worked out once by tools/edges.py from the
engines themselves (run it again after changing a paytable, a strategy or a slot's maths, or building a slot).

For each game, each spot the tables book money on has:
  edge    the house's expected win per pound staked on it (0.0141 is 1.41%)
  sd      the standard deviation of the bettor's net per pound staked, for the ±2σ band
  line    the bet it belongs to on the House page: a decision game's main line gathers the first wager with what's
          added to it (Play, Raise, Double, Split) and what's paid on it (an Ante Bonus). The EV of the whole line is
          charged on its first wager (the Ante); the rest carry an edge of 0, so a line's actual against its EV is
          skill and luck together (the NPCs' slips, Mike's play)
  source  how it was found: "exact", "enumerated" (every hand counted from the paytable) or "simulated" (NPC
          optimal strategy, `n` rounds)
A progressive Jackpot spot adds `pool`: the chance of each tier that pays a share of the pool, so its EV is worked
out from the pool at the moment the bet goes down. Slots: each machine (variant) has its edge, 1 - RTP, and its
Buy Bonus's.

A Craps bet that wins and stays up is a fresh decision on the same stake: charge() is called again for it.
A spot with no figure (a slot built since edges.json was made) is "unpriced": it still counts, with no EV.
"""
import json
import math
from pathlib import Path

PATH = Path(__file__).with_name("edges.json")
SLOTS = "slots"


class Edges:
    def __init__(self, data: dict | None = None, path: Path = PATH):
        if data is None:
            try:
                data = json.loads(path.read_text())
            except (OSError, ValueError):
                data = {}
        self.games: dict = data.get("games", {})
        self.slots: dict = data.get("slots", {})
        self.made: str | None = data.get("made")

    def spot(self, game: str, spot: str) -> dict | None:
        return self.games.get(game, {}).get("spots", {}).get(spot)

    def line(self, game: str, spot: str) -> str:
        """The House page's line a spot belongs to (its own name when it's a bet on its own)."""
        if game == SLOTS:
            return spot
        s = self.spot(game, spot)
        return s.get("line", spot) if s else spot

    def charge(self, game: str, spot: str, stake: int, pool: int = 0, buy: bool = False) -> tuple[float, float] | None:
        """(expected house win in pence, variance of the bettor's net in pence²) for `stake` going down on a spot, or
        None if it's unpriced. `pool`: the progressive jackpot as the bet goes down. At a slot, `spot` is the
        machine and `buy` a bought bonus."""
        if stake <= 0:
            return 0.0, 0.0
        if game == SLOTS:
            s = self.slots.get(spot)
            if not s:
                return None
            edge, sd = (s.get("buy_edge"), s.get("buy_sd")) if buy else (s.get("edge"), s.get("sd"))
            if edge is None:
                return None
            return stake * edge, (stake * (sd or 0.0)) ** 2
        s = self.spot(game, spot)
        if s is None:
            return None
        if "pool" in s:
            return _jackpot(s, stake, pool)
        return stake * s["edge"], (stake * s["sd"]) ** 2


def _jackpot(s: dict, stake: int, pool: int) -> tuple[float, float]:
    """A progressive Jackpot bet: its fixed prizes' return (per pound staked) plus each pool tier's share of the pool
    now, times its chance."""
    p = s["pool"]
    k = stake / p["bet"]   # (the bet's flat, so k is 1; scaled for safety)
    mean = k * p["fixed"] + p["share"] * pool * k
    second = k * k * p["fixed2"] + p["share2"] * (pool * k) ** 2 + 2 * k * k * p.get("cross", 0.0) * pool
    return stake - mean, max(0.0, second - mean * mean)


def band(var: float) -> float:
    """Two standard deviations of a total, in pence, from its summed variance."""
    return 2 * math.sqrt(max(0.0, var))
