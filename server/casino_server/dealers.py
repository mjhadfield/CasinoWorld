"""
Dealers on shifts: every table has a dealer from the roster (role "dealer"),
and every shift a fresh one relieves them -- staggered a couple of minutes apart
table to table, so the relief walks round the floor, and only between hands
(while the table's taking bets), never mid-deal. With fewer dealers than
tables, dealers simply stay on longer.

The table's dealer goes out in table_state (on_duty {id, name, look}) and a
dealer_change table event when they're relieved.
"""
import random
import time

from casino_server import roster

DEFAULT = {"id": None, "name": "Dealer", "look": "dealer"}


class DealerRoster:
    def __init__(self, casino, rng: random.Random | None = None, clock=time.monotonic, pace: float = 1.0):
        self.casino = casino
        self.rng = rng or random.Random()
        self.clock = clock
        self.pace = pace
        self.on_duty: dict[str, dict] = {}    # table id -> {id, name, look}
        self.relief_at: dict[str, float] = {}
        self.started = False

    def _shift(self) -> tuple[float, float]:
        s = roster.settings(self.casino.store)
        return s["dealer_shift_min"] * 60 * self.pace, s["dealer_stagger_min"] * 60 * self.pace

    def _dealer(self, record: dict) -> dict:
        look = DEFAULT["look"]
        looks = getattr(self.casino, "looks", None)
        if looks is not None:
            try:
                look = looks.ensure(record["look"])
            except Exception as e:
                print(f"Dealer {record['name']}: look not built ({e})")
        return {"id": record["id"], "name": record["name"], "look": look}

    def _off_duty(self) -> list[dict]:
        busy = {d["id"] for d in self.on_duty.values()}
        return [r for r in self.casino.store.npcs("dealer") if r["enabled"] and r["id"] not in busy]

    def start(self, now: float):
        free = self._off_duty()
        self.rng.shuffle(free)
        shift, stagger = self._shift()
        staffed = [t for t, runner in self.casino.tables.items() if getattr(runner.machine, "DEALER", True)]
        for i, table_id in enumerate(staffed):   # (slot cabinets have no dealer)
            self.on_duty[table_id] = self._dealer(free.pop()) if free else dict(DEFAULT)
            self.relief_at[table_id] = now + shift + i * stagger
        self.started = True

    def on_table(self, table_id: str) -> dict:
        return dict(self.on_duty.get(table_id, DEFAULT))

    def tick(self, now: float):
        if not self.started:
            self.start(now)
        shift, _ = self._shift()
        for table_id, due in self.relief_at.items():
            if due > now + shift:   # the shift's been shortened on the admin page: it applies now
                self.relief_at[table_id] = due = now + shift
            if now < due:
                continue
            runner = self.casino.tables[table_id]
            if runner.machine.phase != "betting":
                continue   # not mid-hand: wait for the next betting window
            free = self._off_duty()
            self.relief_at[table_id] = now + shift
            if free:
                self.relieve(table_id, self.rng.choice(free))

    def relieve(self, table_id: str, record: dict):
        self.on_duty[table_id] = self._dealer(record)
        self.casino.tables[table_id].publish([{"kind": "dealer_change", "dealer": self.on_table(table_id)}])

    def restyle(self, record: dict):
        """A dealer's look or name changed on the admin page."""
        for table_id, d in self.on_duty.items():
            if d["id"] == record["id"]:
                self.relieve(table_id, record)

    def status(self) -> dict:
        """npc id -> the table they're dealing."""
        return {d["id"]: table_id for table_id, d in self.on_duty.items() if d["id"] is not None}
