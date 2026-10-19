"""
Baccarat table (Punto Banco): a timed state machine that runs a real table's flow.

  betting   Player, Banker or Tie (at least one), plus the Player Dragon and
            Banker Dragon bonuses. Countdown from the first bet; closes early
            once every human is Ready.
  dealing   One coup for the whole table out of the shuffler: Player, Banker,
            Player, Banker, face up, then any third cards by the tableau,
            each announced.
  result    The dealer calls the coup ("Banker wins, 7 over 4").
  settling  Each seat in turn, third base back to first -- quickly, there
            are no cards to turn: losing bets swept, winners paid.
  clearing  Chips back, cards to the rack, betting opens again.

There are no decisions once the bets are down. v2's five 5 Treasures side
bets are in the engine (engines/baccarat.py) but not on this layout yet.
Seating, betting, Ready and the clock are shared with every table (base.py).
"""
from dataclasses import dataclass

from casino_server.dealer import DealerLines
from casino_server.engines import baccarat as bac
from casino_server.engines.cards import Deck
from casino_server.tables.base import CHIPS, TableMachine, say

SPOTS = bac.MAIN_SPOTS + bac.DRAGON_SPOTS


def _eight_decks():
    return Deck(num_decks=8)


@dataclass
class Timings:
    betting: float = 15.0
    betting_npc_only: float = 5.0
    min_betting: float = 3.0
    rebet: float = 3.0
    first_card: float = 0.6
    card: float = 1.2             # each card dealt and turned
    third_card: float = 1.5       # a third card, after a beat
    result: float = 1.8
    settle_base: float = 0.5
    settle_step: float = 0.35
    clear: float = 2.2

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


class BaccaratMachine(TableMachine):
    game = bac.GAME_KEY
    label = bac.GAME_LABEL
    SPOTS = SPOTS
    MAIN_SPOT = "player"
    NEEDS_MAIN = "Dragon bets need a Player, Banker or Tie bet alongside them."
    CANT_COVER = "Not enough balance for that."

    def __init__(self, table_id: str, seats: int = 6, timings: Timings | None = None,
                 jackpot=None, deck_factory=_eight_decks, lines: DealerLines | None = None):
        super().__init__(table_id, seats, timings or Timings(), jackpot, lines or DealerLines())
        self.deck_factory = deck_factory
        self.round: dict[int, Stake] = {}
        self.coup: bac.Coup | None = None
        self.shown = 0          # cards of the coup turned so far
        self._settle_queue: list[int] = []

    def rules(self) -> dict:
        return {**bac.rules(), "chips": CHIPS, "min_ante": CHIPS[0], "seats": len(self.seats)}

    def _has_main(self, bets: dict) -> bool:
        return any(bets.get(s, 0) > 0 for s in bac.MAIN_SPOTS)

    # ------------------------------------------------------------------ the clock
    def _advance(self, now: float) -> list:
        if self.phase == "betting":
            return self._close_betting(now)
        if self.phase == "dealing":
            return self._next_card(now)
        if self.phase == "result":
            return self._start_settling(now)
        if self.phase == "settling":
            return self._settle_next(now)
        if self.phase == "clearing":
            return self._open_betting(now)
        return []

    def _close_betting(self, now: float) -> list:
        events, taken = self._take_bets(now)
        if not taken:
            return events
        self.round = {i: Stake(self.seats[i].participant, dict(b)) for i, b in sorted(taken.items())}
        self.coup = bac.deal_coup(self.deck_factory())
        self.shown = 0
        self.phase = "dealing"
        self.deadline = now + self.timings.first_card
        events.append({"kind": "bets_closed", "seats": sorted(taken), "jackpots": [],
                       "_paid": [self.seats[i].participant for i in sorted(taken)]})
        return events + say(self.lines.say("table", "no_more_bets"))

    def _next_card(self, now: float) -> list:
        """Turn the next card of the coup; once they're all out, call it."""
        coup = self.coup
        if self.shown >= len(coup.order):
            self.phase = "result"
            self.deadline = now + self.timings.result
            return [{"kind": "coup_result", "outcome": coup.outcome, "player_total": coup.player_total,
                     "banker_total": coup.banker_total, "natural": coup.player_natural or coup.banker_natural}] + \
                say(bac.describe(coup) + ".")
        side = coup.order[self.shown]
        index = coup.order[:self.shown].count(side)
        card = (coup.player if side == "player" else coup.banker)[index]
        self.shown += 1
        hand = (coup.player if side == "player" else coup.banker)[:index + 1]
        upcoming = self.shown < len(coup.order) and self.shown >= 4
        self.deadline = now + (self.timings.third_card if upcoming else self.timings.card)
        return [{"kind": "baccarat_card", "side": side, "index": index, "card": card.code, "total": bac.total(hand)}]

    def _start_settling(self, now: float) -> list:
        self.phase = "settling"
        for s in self.round.values():
            s.returns = bac.settle(self.coup, s.bets)
        self._settle_queue = sorted(self.round, reverse=True)
        return self._settle_next(now)

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
        s.participant.credit(s.paid, "win" if net > 0 else "lose")
        steps = []
        for spot in SPOTS:
            bet, ret = s.bets.get(spot, 0), s.returns.get(spot, 0)
            if bet <= 0:
                continue
            if ret == 0:
                steps.append({"spot": spot, "action": "collect", "amount": bet})
            elif ret == bet:
                steps.append({"spot": spot, "action": "push", "amount": bet})
            else:
                steps.append({"spot": spot, "action": "pay", "amount": bet, "payout": ret - bet})
        steps.sort(key=lambda x: x["action"] != "collect")
        t = self.timings
        self.deadline = now + t.settle_base + t.settle_step * len(steps)
        return [{"kind": "settle_seat", "seat": seat, "steps": steps, "total_returned": s.paid, "pause": 0.2,
                 "_paid": [s.participant]}]

    def _open_betting(self, now: float) -> list:
        self.round = {}
        self.coup = None
        self.shown = 0
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
                entry["bets"] = dict(stake.bets)
                if stake.settled:
                    entry["result"] = {"returned": stake.paid}
            seats.append(entry)
        player, banker = [], []
        if self.coup is not None:
            for k, side in enumerate(self.coup.order[:self.shown]):
                hand = player if side == "player" else banker
                source = self.coup.player if side == "player" else self.coup.banker
                hand.append(source[len(hand)].code)
        timer = self._timer(now, ("betting",))
        return {"game": self.game, "phase": self.phase, "seats": seats, "player": player, "banker": banker,
                "timer": timer, "my_seat": viewer}
