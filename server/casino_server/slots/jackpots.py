"""
The shared slot progressives: Mini, Minor, Major and Grand, one set for every slot cabinet
(separate from the table games' jackpot in jackpot.py). Each bet puts a share into each meter;
a Jackpot Pick can start on any paid spin, with odds in proportion to the bet so every stake
gets the same return; the pick board's reveal order is drawn up front so the won tier is the
first to three. A win pays that meter and resets it to its seed.

The meters persist in the store's meta table (`slot_progressives`), saved at most every few
seconds, on a win, and on shutdown.
"""
import time

from casino_server.slots.rng import shuffle, weighted

# seed (pence), share of every bet, and how often it's won (1 in `every` pence wagered)
TIERS = [
    {"id": "mini", "name": "MINI", "seed": 1_000, "rate": 0.0025, "every": 150_000},
    {"id": "minor", "name": "MINOR", "seed": 5_000, "rate": 0.0025, "every": 1_000_000},
    {"id": "major", "name": "MAJOR", "seed": 50_000, "rate": 0.005, "every": 15_000_000},
    {"id": "grand", "name": "GRAND", "seed": 500_000, "rate": 0.01, "every": 200_000_000},
]
TIER_IDS = [t["id"] for t in TIERS]
PER_PENCE = sum(1 / t["every"] for t in TIERS)
BOARD = 12
SAVE_INTERVAL = 5.0
_META_KEY = "slot_progressives"
_SETTINGS_KEY = "slot_progressive_settings"


def trigger(bet: int, rng) -> str | None:
    """Does this spin start a Jackpot Pick, and for which tier."""
    if rng() >= bet * PER_PENCE:
        return None
    return weighted(rng, [(t["id"], 1 / t["every"]) for t in TIERS])


def pick_sequence(tier: str, rng) -> dict:
    """The 12-coin board's reveal order: the won tier comes up twice among the others and
    completes on the last reveal; no other tier gets more than two. `rest` is what the coins
    left unpicked show at the end."""
    seq = [tier, tier]
    for t in TIERS:
        if t["id"] != tier:
            seq += [t["id"]] * weighted(rng, [(1, 1), (2, 3)])
    shuffle(rng, seq)
    seq.append(tier)
    pool = [t["id"] for t in TIERS for _ in range(3) if t["id"] != tier]
    shuffle(rng, pool)
    return {"seq": seq, "rest": pool[:BOARD - len(seq)]}


def rtp(settings: dict | None = None) -> float:
    """What the progressives return from bets: every bet's share, plus each seed paid once per
    win. (Real-time growth comes on top, and depends on how busy the slots are.)"""
    settings = settings or {}
    return sum(settings.get(t["id"], {}).get("rate", t["rate"]) + t["seed"] / t["every"] for t in TIERS)


DEFAULT_SETTINGS = {t["id"]: {"rate": t["rate"], "per_second": 0.0} for t in TIERS}
MAX_RATE = 0.05            # at most 5% of every bet into one meter
MAX_PER_SECOND = 1000.0    # at most £10 a second


def clean_settings(raw) -> dict:
    """The admin page's settings, checked: {tier: {rate (share of every bet), per_second (pence)}}."""
    if not isinstance(raw, dict):
        raise ValueError("Expected {tier: {rate, per_second}}.")
    out = {}
    for tid in TIER_IDS:
        if tid not in raw:
            continue
        entry = raw[tid]
        if not isinstance(entry, dict):
            raise ValueError(f"{tid}: expected {{rate, per_second}}.")
        try:
            rate = float(entry.get("rate", DEFAULT_SETTINGS[tid]["rate"]))
            per_second = float(entry.get("per_second", 0.0))
        except (TypeError, ValueError):
            raise ValueError(f"{tid}: the rate and the amount a second are numbers.")
        if not 0.0 <= rate <= MAX_RATE:
            raise ValueError(f"{tid}: the share of each bet is between 0% and {MAX_RATE * 100:g}%.")
        if not 0.0 <= per_second <= MAX_PER_SECOND:
            raise ValueError(f"{tid}: the amount a second is between £0 and £{MAX_PER_SECOND / 100:g}.")
        out[tid] = {"rate": rate, "per_second": per_second}
    return out


class SlotProgressives:
    """The four meters. Each grows by its share of every bet, and (if set) by a fixed amount a
    second while the server runs -- worked out from elapsed time whenever it's read, like the
    table jackpot (jackpot.py), so there's no background task. Clients get the rates with the
    amounts and animate the meters themselves between updates."""

    def __init__(self, store, clock=time.monotonic):
        self.store = store
        self.clock = clock
        saved = store.get_json(_META_KEY, {}) if store else {}
        self._amounts = {t["id"]: max(float(saved.get(t["id"], t["seed"])), t["seed"]) for t in TIERS}
        stored = store.get_json(_SETTINGS_KEY, {}) if store else {}
        self.settings = {tid: {**DEFAULT_SETTINGS[tid], **(stored.get(tid) or {})} for tid in TIER_IDS}
        self._last_tick = clock()
        self._last_save = self._last_tick

    def _tick(self):
        now = self.clock()
        dt = now - self._last_tick
        self._last_tick = now
        if dt > 0:
            for tid in TIER_IDS:
                self._amounts[tid] += self.settings[tid]["per_second"] * dt
        if now - self._last_save >= SAVE_INTERVAL:
            self.save()

    def amount(self, tier: str) -> int:
        self._tick()
        return int(self._amounts[tier])

    def amounts(self) -> dict:
        self._tick()
        return {t: int(a) for t, a in self._amounts.items()}

    def rates(self) -> dict:
        """Pence a second each meter grows by on its own."""
        return {tid: self.settings[tid]["per_second"] for tid in TIER_IDS}

    def rtp(self) -> float:
        return rtp(self.settings)

    def configure(self, changes: dict) -> dict:
        """The admin page's settings (already checked by clean_settings)."""
        self._tick()
        for tid, entry in changes.items():
            self.settings[tid] = {**self.settings[tid], **entry}
        if self.store:
            self.store.set_json(_SETTINGS_KEY, self.settings)
        return self.settings

    def contribute(self, bet: int):
        self._tick()
        for tid in TIER_IDS:
            self._amounts[tid] += bet * self.settings[tid]["rate"]

    def win(self, tier: str) -> int:
        """Pays out the meter and resets it to its seed. Returns the payout in pence."""
        self._tick()
        payout = int(self._amounts[tier])
        self._amounts[tier] = float(next(t["seed"] for t in TIERS if t["id"] == tier))
        self.save()
        return payout

    def reset(self, tier: str):
        """The admin page's reset to seed."""
        self._tick()
        self._amounts[tier] = float(next(t["seed"] for t in TIERS if t["id"] == tier))
        self.save()

    def snapshot(self) -> dict:
        return {"type": "slot_jackpots", "meters": self.amounts(), "rates": self.rates()}

    def save(self):
        self._last_save = self.clock()
        if self.store:
            self.store.set_json(_META_KEY, {t: round(a, 4) for t, a in self._amounts.items()})
