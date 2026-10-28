"""
Roulette table (single zero, La Partage): a timed state machine that runs a real
table's flow.

  betting    Chips anywhere on the layout. Countdown from the first bet; closes
             early once every human is Ready.
  spinning   The dealer spins the wheel and launches the ball ("Final bets!").
             Bets are still taken until just before the ball reaches the pockets
             (Ready can't cut it short).
  rolling    "No more bets": bets are taken, and the number is drawn there and
             then, with the landing that carries the ball to it, so it never
             exists while anyone can still bet. The ball lands.
  result     The dealer calls it ("17, black, odd, low"); the dolly goes on it.
  sweeping   Every losing chip goes down the chip hole in one sweep (half of
             each even-money stake on a zero).
  settling   Each winning seat is paid from the float, quickly.
  clearing   Winnings go back to the players, the dolly comes off, betting opens.

Seating, betting, Ready and the clock are shared with every table (base.py).
Bet events carry only the spots in use: there are 157 of them.
"""
import math
import random
from dataclasses import dataclass

from casino_server.dealer import DealerLines
from casino_server.engines import roulette as rou
from casino_server.tables.base import CHIPS, TableError, TableMachine, returns_detail, say

HISTORY = 12


@dataclass
class Timings:
    betting: float = 25.0
    betting_npc_only: float = 8.0
    min_betting: float = 3.0
    rebet: float = 3.0
    spin_open: float = 7.3        # bets still taken once the ball's spinning: until just before it reaches the pockets
    ball_track: float = rou.BALL_TRACK   # launch -> the ball reaches the pockets (the landing follows)
    result: float = 1.4
    sweep: float = 1.4
    settle_base: float = 0.5
    settle_step: float = 0.3
    clear: float = 1.8

    def scaled(self, factor: float) -> "Timings":
        return Timings(**{name: getattr(self, name) * factor for name in self.__dataclass_fields__})

    @classmethod
    def instant(cls) -> "Timings":
        return cls(**{name: 0.0 for name in cls.__dataclass_fields__})


@dataclass
class Stake:
    participant: object
    bets: dict
    returns: dict | None = None
    settled: bool = False
    paid: int = 0


class RouletteMachine(TableMachine):
    game = rou.GAME_KEY
    label = rou.GAME_LABEL
    SPOTS = rou.SPOTS
    BETTING_PHASES = ("betting", "spinning")
    QUEUE_BETS = False   # Mike: at the wheel you wait for the next spin (late bets cover the spin itself)
    CANT_COVER = "Not enough balance for that."

    def __init__(self, table_id: str, seats: int = 6, timings: Timings | None = None,
                 jackpot=None, deck_factory=None, lines: DealerLines | None = None, rng=None):
        super().__init__(table_id, seats, timings or Timings(), jackpot, lines or DealerLines())
        self.rng = rng or random.SystemRandom()
        self.round: dict[int, Stake] = {}
        self.number: int | None = None
        self.landing: list = []
        self.ball = 0.0               # the ball's launch angle relative to the rotor
        self.spun_at = 0.0
        self.lands_at = 0.0
        # A table that's been running all day: the board starts with twelve results.
        self.history = [self.rng.randrange(37) for _ in range(HISTORY)]
        self._settle_queue: list[int] = []

    def rules(self) -> dict:
        return {**rou.rules(), "chips": CHIPS, "min_ante": rou.MIN_BET, "seats": len(self.seats)}

    def _bets_view(self, bets: dict) -> dict:
        return {spot: amount for spot, amount in bets.items() if amount}

    def _has_main(self, bets: dict) -> bool:
        return any(amount > 0 for amount in bets.values())

    def _validate_bets(self, bets: dict):
        for spot, amount in bets.items():
            if not amount:
                continue
            bet = rou.BETS[spot]
            if amount < rou.MIN_BET:
                raise TableError("The minimum bet is £1.")
            if amount > bet.limit:
                raise TableError(f"{bet.name}: the table limit is £{bet.limit // 100:,}.")

    def ready(self, seat: int, now: float) -> list:
        if self.phase == "spinning":
            raise TableError("The ball's already spinning.")
        return super().ready(seat, now)

    # ------------------------------------------------------------------ the clock
    def _advance(self, now: float) -> list:
        if self.phase == "betting":
            return self._spin(now)
        if self.phase == "spinning":
            return self._no_more_bets(now)
        if self.phase == "rolling":
            return self._landed(now)
        if self.phase == "result":
            return self._sweep(now)
        if self.phase == "sweeping":
            self.phase = "settling"
            self._settle_queue = [i for i, s in sorted(self.round.items()) if any(s.returns.values())]
            return self._settle_next(now)
        if self.phase == "settling":
            return self._settle_next(now)
        if self.phase == "clearing":
            return self._open_betting(now)
        return []

    def _spin(self, now: float) -> list:
        """Betting's countdown is up: the dealer spins (if anyone has a bet down)."""
        if not any(self._has_main(s.bets) for s in self.seats if s.participant):
            self.deadline = None  # nobody's betting -- stay open until someone does
            return [{"kind": "betting_reset"}]
        self.phase = "spinning"
        self.spun_at = now
        self.ball = self.rng.uniform(0, 2 * math.pi)
        self.deadline = now + self.timings.spin_open
        for s in self.seats:
            s.ready = False  # Ready only meant "spin"; late bets are open to everyone
        return [{"kind": "spin", "open": self.timings.spin_open, "track": self.timings.ball_track,
                 "ball": round(self.ball, 6)}] + \
            say(self.lines.say("roulette", "spin"))

    def _no_more_bets(self, now: float) -> list:
        events, taken = self._take_bets(now)
        events = [e for e in events if e["kind"] != "betting_reset"]  # the ball's spinning whatever happens
        self.round = {i: Stake(self.seats[i].participant, self._bets_view(b)) for i, b in sorted(taken.items())}
        self.number = self.rng.randrange(37)
        scale = self.timings.ball_track / rou.BALL_TRACK
        arrival = rou.arrival_pocket(round(self.ball, 6), scale)
        self.landing = rou.plan_landing(arrival, self.number, self.rng)
        self.lands_at = self.spun_at + self.timings.ball_track + rou.landing_seconds(self.landing) * scale
        self.phase = "rolling"
        self.deadline = max(now, self.lands_at)
        events.append({"kind": "no_more_bets", "seats": sorted(taken), "number": self.number, "landing": self.landing,
                       "land_in": round(self.deadline - now, 3),
                       "_paid": [self.seats[i].participant for i in sorted(taken)]})
        return events + say(self.lines.say("table", "no_more_bets"))

    def _landed(self, now: float) -> list:
        n = self.number
        self.phase = "result"
        self.history = ([n] + self.history)[:HISTORY]
        self.deadline = now + self.timings.result
        if n == 0:
            line = self.lines.say("roulette", "zero") or "Zero."
        else:
            line = self.lines.say("roulette", "result", number=n, colour=rou.colour(n),
                                  parity="odd" if n % 2 else "even", half="low" if n <= 18 else "high") \
                or rou.describe(n) + "."
        return [{"kind": "ball_landed", "number": n, "colour": rou.colour(n), "history": list(self.history)}] + say(line)

    def _sweep(self, now: float) -> list:
        """Every losing chip (and half of each even-money stake on a zero) goes down the hole."""
        self.phase = "sweeping"
        lost = {}
        for i, s in self.round.items():
            s.returns = rou.settle(self.number, s.bets)
            gone = [{"spot": spot, "amount": stake - s.returns[spot]}   # all of it, or half on a La Partage
                    for spot, stake in s.bets.items() if s.returns[spot] < stake]
            if gone:
                lost[i] = gone
            if not any(s.returns.values()):
                s.settled = True
        self.deadline = now + (self.timings.sweep if lost else 0.0)
        return [{"kind": "sweep", "seats": {str(i): g for i, g in lost.items()}}]

    def _settle_next(self, now: float) -> list:
        if not self._settle_queue:
            self.phase = "clearing"
            self.deadline = now + self.timings.clear
            return [{"kind": "round_end"}]
        seat = self._settle_queue.pop(0)
        s = self.round[seat]
        s.settled = True
        s.paid = sum(s.returns.values())
        net = s.paid - sum(s.bets.values())
        s.participant.credit(s.paid, "win" if net > 0 else "lose", returns_detail(
            [(spot, stake, s.returns[spot]) for spot, stake in s.bets.items()]))
        steps = []
        for spot, stake in s.bets.items():
            ret = s.returns[spot]
            if ret > stake:
                steps.append({"spot": spot, "action": "pay", "amount": stake, "payout": ret - stake})
            elif ret:
                steps.append({"spot": spot, "action": "half", "amount": ret})  # La Partage: half stays
        # Outside bets first, then the inside bets (the big straight-up stacks last).
        steps.sort(key=lambda x: len(rou.BETS[x["spot"]].numbers), reverse=True)
        t = self.timings
        self.deadline = now + t.settle_base + t.settle_step * len(steps)
        return [{"kind": "settle_seat", "seat": seat, "steps": steps, "total_returned": s.paid,
                 "_paid": [s.participant]}]

    def _open_betting(self, now: float) -> list:
        self.round = {}
        self.number = None
        self._settle_queue = []
        return self._reopen_betting(now)

    # ------------------------------------------------------------------ snapshot
    def snapshot(self, viewer: int | None, now: float) -> dict:
        seats = []
        for i, s in enumerate(self.seats):
            if s.participant is None:
                seats.append(None)
                continue
            entry = {**self._seat_entry(i, s), "result": None}
            stake = self.round.get(i)
            if stake is not None and stake.participant.entity_id == entry["entity"]:
                entry["bets"] = dict(stake.bets) if not stake.settled or stake.paid else {}
                if stake.settled:
                    entry["result"] = {"returned": stake.paid}
            seats.append(entry)
        spin = None
        if self.phase in ("spinning", "rolling"):
            spin = {"elapsed": round(now - self.spun_at, 3), "track": self.timings.ball_track, "ball": round(self.ball, 6)}
            if self.phase == "rolling":
                spin.update(number=self.number, landing=self.landing, land_in=round(max(0.0, self.lands_at - now), 3))
        dolly = self.number if self.phase in ("result", "sweeping", "settling", "clearing") else None
        return {"game": self.game, "phase": self.phase, "seats": seats, "history": list(self.history),
                "spin": spin, "dolly": dolly, "timer": self._timer(now, ("betting", "spinning")), "my_seat": viewer}
