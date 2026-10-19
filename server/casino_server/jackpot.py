"""
The casino's one progressive jackpot, shared by every table and player
(v2: core/jackpot.py). It grows on its own clock while the server runs --
not while it's stopped -- from a floor to a ceiling.

No background task: the amount is worked out from elapsed time whenever it's
read, and saved to the store at most every few seconds. Clients get
{amount, rate} and animate the meter themselves between updates.
"""
import time

JACKPOT_FLOOR = 500_000      # £5,000
JACKPOT_CEILING = 5_000_000  # £50,000
RATE_PER_SECOND = 1.0        # pence/second -- v2's default £0.01/s
SAVE_INTERVAL = 5.0          # seconds

_META_KEY = "jackpot_amount"


class Jackpot:
    def __init__(self, store, rate: float = RATE_PER_SECOND, clock=time.monotonic):
        self.store = store
        self.rate = rate
        self.clock = clock
        self._amount = self._clamp(float(store.get_meta(_META_KEY, str(JACKPOT_FLOOR))))
        self._last_tick = clock()
        self._last_save = self._last_tick

    @staticmethod
    def _clamp(amount: float) -> float:
        return min(max(amount, JACKPOT_FLOOR), JACKPOT_CEILING)

    def _tick(self):
        now = self.clock()
        self._amount = self._clamp(self._amount + self.rate * (now - self._last_tick))
        self._last_tick = now
        if now - self._last_save >= SAVE_INTERVAL:
            self._persist()

    @property
    def amount(self) -> int:
        """Current jackpot in whole pence -- what a win actually pays."""
        self._tick()
        return int(self._amount)

    def snapshot(self) -> dict:
        """What clients need to run the meter: current value and growth rate."""
        amount = self.amount
        return {"type": "jackpot", "amount": amount,
                "rate": self.rate if amount < JACKPOT_CEILING else 0.0,
                "ceiling": JACKPOT_CEILING}

    def win(self) -> int:
        """Pays out the whole pool and resets it to the floor. Returns the payout."""
        payout = self.amount
        self._amount = JACKPOT_FLOOR
        self._persist()
        return payout

    def take(self, share: float) -> int:
        """Pays out a share of the pool (Pai Gow's 50% and 25% tiers), leaving
        the rest growing (never below the floor). Returns the payout."""
        payout = int(self.amount * share)
        self._amount = self._clamp(self._amount - payout)
        self._persist()
        return payout

    def save(self):
        """Brings the amount up to date and writes it -- call on shutdown."""
        self._tick()
        self._persist()

    def _persist(self):
        self._last_save = self.clock()
        self.store.set_meta(_META_KEY, f"{self._amount:.4f}")
