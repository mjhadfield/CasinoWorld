"""
Back-off at Blackjack: the house watching for card counters, players and NPCs alike.

Each round dealt at a Blackjack table (a Master Table playing it too), the table hands HeatWatch everyone's main bet
(both boxes of someone playing two) and the true count before the cards came out (BlackjackMachine.count). Heat is
scored against their base, the smallest main bet of their last BASE_ROUNDS rounds:

  BIG times the base or more on a true count of +2 or better     +1 (+2 at HUGE times)
  BIG times the base or more on a count under +1                 -1 (a big bet into a bad count looks like gambling,
                                                                     so a Chaser's loss-chasing about cancels out)
  anything else                                                   -0.25

Heat halves every HALF_LIFE_MIN minutes as well, and never goes below 0. At `warn_at` the dealer passes on the pit
boss's request for level bets; at `back_off_at`, once warned, they're backed off: no blackjack for `bar_min` minutes,
or for an NPC the rest of their visit (the director forgets them when it ends). The table stands a player up once the
round's over; an NPC's director sees to its own (npc.py). Warned and backed off reset once the heat's cooled to half
of `warn_at` (or the bar's run out).

One HeatWatch is shared by the Resort's casinos (a casino on its own has its own), kept in memory: a restart forgives
everyone. The admin page's Settings tune it (`heat_settings` in meta).
"""
import math
import time
from collections import deque
from dataclasses import dataclass, field

BASE_ROUNDS = 20
BIG, HUGE = 2, 4
HOT_COUNT, COLD_COUNT = 2, 1
HALF_LIFE_MIN = 10

DEFAULT_SETTINGS = {"on": True, "warn_at": 6, "back_off_at": 10, "bar_min": 60}
_LIMITS = {
    "warn_at": (1, 100, "Warn at"),
    "back_off_at": (1, 100, "Back off at"),
    "bar_min": (1, 7 * 24 * 60, "The back-off"),
}


def settings(store) -> dict:
    saved = store.get_json("heat_settings", {}) if store is not None else {}
    return {**DEFAULT_SETTINGS, **{k: v for k, v in saved.items() if k in DEFAULT_SETTINGS}}


def clean_settings(data: dict) -> dict:
    out = {}
    if "on" in data:
        if not isinstance(data["on"], bool):
            raise ValueError("Back-off is on or off.")
        out["on"] = data["on"]
    for key, (lo, hi, what) in _LIMITS.items():
        if key not in data:
            continue
        v = data[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != int(v) or not lo <= v <= hi:
            raise ValueError(f"{what} is a whole number from {lo:,} to {hi:,}.")
        out[key] = int(v)
    if out.get("back_off_at", 10**9) <= out.get("warn_at", 0):
        raise ValueError("Back off at has to be more than Warn at.")
    return out


def owner_of(participant):
    """Who's really playing: a second box is its owner's."""
    return getattr(participant, "owner", None) or participant


def key_of(participant) -> tuple | None:
    """Who heat belongs to, across tables and casinos: an NPC by its roster id, a player by their character."""
    p = owner_of(participant)
    npc = getattr(p, "npc", None)
    if npc is not None:
        return ("npc", npc.npc_id)
    pid = getattr(p, "player_id", None)
    return ("player", pid) if pid is not None else None


@dataclass
class Record:
    heat: float = 0.0
    at: float = 0.0                       # when `heat` was last brought up to date
    bets: deque = field(default_factory=lambda: deque(maxlen=BASE_ROUNDS))
    warned: bool = False
    barred_until: float | None = None     # math.inf: an NPC's, for the rest of their visit


class HeatWatch:
    def __init__(self, store=None, clock=time.time):
        self.store = store
        self.clock = clock
        self._records: dict[tuple, Record] = {}

    def settings(self) -> dict:
        return settings(self.store)

    def _record(self, key: tuple, now: float, make: bool = False) -> Record | None:
        rec = self._records.get(key)
        if rec is None:
            if not make:
                return None
            rec = self._records[key] = Record(at=now)
        rec.heat *= 0.5 ** (max(0.0, now - rec.at) / (HALF_LIFE_MIN * 60))
        rec.at = now
        if rec.barred_until is not None and now >= rec.barred_until:
            rec.barred_until, rec.warned, rec.heat = None, False, 0.0
        return rec

    def observe(self, rows: list, true_count: float) -> list:
        """One round's main bets, [(participant, bet)], against the true count before the deal. Returns who's
        reached a stage: [(owner, "warned" | "backed_off", minutes)] (minutes 0 for a warning, or an NPC's
        back-off, which lasts their visit)."""
        s = self.settings()
        if not s["on"]:
            return []
        now = self.clock()
        totals: dict[tuple, list] = {}
        for participant, bet in rows:
            key = key_of(participant)
            if key is not None and bet > 0:
                entry = totals.setdefault(key, [owner_of(participant), 0])
                entry[1] += bet
        reached = []
        for key, (owner, bet) in totals.items():
            rec = self._record(key, now, make=True)
            base = min(rec.bets) if rec.bets else bet
            rec.bets.append(bet)
            if rec.barred_until is not None:
                continue
            ratio = bet / base if base else 1.0
            if ratio >= BIG and true_count >= HOT_COUNT:
                rec.heat += 2 if ratio >= HUGE else 1
            elif ratio >= BIG and true_count < COLD_COUNT:
                rec.heat = max(0.0, rec.heat - 1)
            else:
                rec.heat = max(0.0, rec.heat - 0.25)
            if rec.warned and rec.heat < s["warn_at"] / 2:
                rec.warned = False
            if not rec.warned and rec.heat >= s["warn_at"]:
                rec.warned = True
                reached.append((owner, "warned", 0))
            elif rec.warned and rec.heat >= s["back_off_at"]:
                npc = key[0] == "npc"
                rec.barred_until = math.inf if npc else now + s["bar_min"] * 60
                reached.append((owner, "backed_off", 0 if npc else s["bar_min"]))
        return reached

    def minutes_left(self, participant) -> int | None:
        """How long they're backed off for (rounded up; 0 for the rest of an NPC's visit), or None if they aren't."""
        key = key_of(participant)
        rec = self._record(key, self.clock()) if key is not None else None
        if rec is None or rec.barred_until is None:
            return None
        if rec.barred_until == math.inf:
            return 0
        return max(1, math.ceil((rec.barred_until - self.clock()) / 60))

    def barred(self, participant) -> bool:
        return self.minutes_left(participant) is not None

    def warned(self, participant) -> bool:
        key = key_of(participant)
        rec = self._record(key, self.clock()) if key is not None else None
        return rec is not None and rec.warned and rec.barred_until is None

    def refusal(self, participant) -> str | None:
        """Why they can't sit down at blackjack, or None."""
        left = self.minutes_left(participant)
        if left is None:
            return None
        if left == 0:
            return "The pit boss has asked you not to play blackjack today."
        return f"The pit boss has asked you not to play blackjack for another {left} min."

    def forget(self, participant):
        """An NPC's visit is over: whatever the pit thought of them goes with them."""
        key = key_of(participant)
        if key is not None:
            self._records.pop(key, None)
