"""
Each slot machine's figures for the admin page's Slots section: spins, money staked and returned,
bonuses played and jackpots won, per variant and split between humans and NPCs. The ledger only
knows "slots" (and never sees NPC play), so these count from when they were added.

Counts build up in memory and go into the store's slot_stats table at most every few seconds and
on shutdown, like the progressives (jackpots.py).
"""
import time

FIELDS = ("spins", "staked", "returned", "bonuses", "jackpots")
SAVE_INTERVAL = 5.0


class SlotStats:
    def __init__(self, store, clock=time.monotonic):
        self.store, self.clock = store, clock
        self.pending: dict = {}   # (variant, "human" | "npc") -> {field: count}
        self.saved_at = clock()

    def record(self, variant: str, human: bool, **counts):
        if not any(counts.values()):
            return
        row = self.pending.setdefault((variant, "human" if human else "npc"), dict.fromkeys(FIELDS, 0))
        for k, v in counts.items():
            row[k] += v
        if self.clock() - self.saved_at >= SAVE_INTERVAL:
            self.save()

    def save(self):
        self.saved_at = self.clock()
        if self.store is None or not self.pending:
            return
        self.store.add_slot_stats(self.pending)
        self.pending = {}

    def rows(self) -> list[dict]:
        """Every (variant, who) row: what's saved plus what isn't yet."""
        totals = {}
        for r in self.store.slot_stats() if self.store is not None else []:
            totals[(r["variant"], r["who"])] = {k: r[k] for k in FIELDS}
        for key, row in self.pending.items():
            t = totals.setdefault(key, dict.fromkeys(FIELDS, 0))
            for k in FIELDS:
                t[k] += row[k]
        return [{"variant": v, "who": w, **c} for (v, w), c in sorted(totals.items())]

    def since(self) -> str | None:
        return self.store.get_meta("slot_stats_since") if self.store is not None else None
