"""
High Card Flush table: a timed state machine that runs a real table's flow.

  betting   Ante, plus the Flush, Straight Flush and £1 Jackpot side bets.
            Countdown from the first bet; closes early once every human is
            Ready. The Jackpot lights lock in as at the other tables.
  dealing   Seven cards to each seat in turn from first base (private), then
            seven face down to the dealer.
  deciding  Everyone decides at once: fold, or raise 1x the Ante (2x with a
            5-card flush, 3x with 6 or 7). Out of time: fold. A raise puts the
            flush down in front, face down, and the other cards aside.
  sweeping  The dealer takes the folded hands with their Ante and side bets,
            and every raised hand's unused cards.
  reveal    The dealer turns their seven cards and announces the flush
            (a 3-card flush, 9-high, qualifies); the flush goes in front, the
            rest is swept away.
  settling  Each player still in, third base back to first: the flush turned
            over, losing bets swept, winners paid beside their stakes.

House rule (this table, not the v2 engine): a fold is swept away unseen and
loses the Flush bonus too. The exception is a straight flush of three or
more with a Straight Flush bet or Jackpot riding: those cards are tucked
under the Straight Flush bet, as with a Prime at Three Card Poker, and that
bet (and the Jackpot) still pays. A raised hand holding a straight flush in
another suit tucks it under the bet the same way.
  clearing  Chips back, cards to the rack, betting opens again.

Seating, betting, Ready and the clock are shared with every table (base.py).
"""
from dataclasses import dataclass, field

from casino_server.dealer import DealerLines
from casino_server.engines import high_card_flush as hcf
from casino_server.engines.cards import Deck
from casino_server.tables.base import CHIPS, TableError, TableMachine, say

SPOTS = ("ante", "flush", "straight_flush", "jackpot")
ACTIONS = {"fold": 0, "raise1": 1, "raise2": 2, "raise3": 3}


@dataclass
class Timings:
    betting: float = 15.0
    betting_npc_only: float = 5.0
    min_betting: float = 3.0
    rebet: float = 3.0
    decide: float = 20.0
    deal_card: float = 0.05
    deal_hand_pause: float = 0.5
    deal_pause: float = 0.8
    jackpot_lock: float = 1.6
    last_decision: float = 0.8
    sweep_pause: float = 0.8
    sweep_each: float = 0.4
    reveal: float = 2.2
    settle_pause: float = 0.9
    settle_base: float = 1.2
    settle_step: float = 0.45
    clear: float = 2.4

    def scaled(self, factor: float) -> "Timings":
        return Timings(**{name: getattr(self, name) * factor for name in self.__dataclass_fields__})

    @classmethod
    def instant(cls) -> "Timings":
        return cls(**{name: 0.0 for name in cls.__dataclass_fields__})


@dataclass
class Hand:
    participant: object
    bets: hcf.Bets
    cards: list
    decided: bool = False
    folded: bool = False
    flush: list = field(default_factory=list)   # a raised hand's flush, face down in front
    held: list = field(default_factory=list)    # a straight flush tucked under the Straight Flush bet
    swept: bool = False
    settled: bool = False
    result: hcf.Result | None = None
    paid: int = 0

    @property
    def side_bets(self) -> bool:
        return bool(self.bets.flush or self.bets.straight_flush or self.bets.jackpot)

    @property
    def in_settle(self) -> bool:
        """Still on the felt for the settle: raised, or a fold kept alive by a straight flush."""
        return not self.folded or bool(self.held)

    @property
    def unused(self) -> list:
        return [c for c in self.cards if c not in self.flush and c not in self.held]


class HighCardFlushMachine(TableMachine):
    game = hcf.GAME_KEY
    label = hcf.GAME_LABEL
    SPOTS = SPOTS
    MAIN_SPOT = "ante"
    FLAT_SPOTS = {"jackpot": hcf.JACKPOT_BET}
    NEEDS_MAIN = "Side bets need an Ante alongside them."
    CANT_COVER = "Not enough balance: you need four times your Ante (to raise 3x), plus side bets."
    CANT_COVER_BOTH = "Not enough balance: you need four times your Ante, plus side bets, on both boxes."
    SECOND_BOX = True

    def __init__(self, table_id: str, seats: int = 6, timings: Timings | None = None,
                 jackpot=None, deck_factory=Deck, lines: DealerLines | None = None):
        super().__init__(table_id, seats, timings or Timings(), jackpot, lines or DealerLines())
        self.deck_factory = deck_factory
        self.round: dict[int, Hand] = {}
        self.dealer_cards: list = []
        self.dealer_shown = False
        self._settle_queue: list[int] = []

    def rules(self) -> dict:
        return {**hcf.rules(), "chips": CHIPS, "min_ante": CHIPS[0], "seats": len(self.seats)}

    def max_cost(self, bets: dict) -> int:
        return bets["ante"] * 4 + bets["flush"] + bets["straight_flush"] + bets["jackpot"]

    def _leaving_mid_hand(self, seat: int, now: float, reason: str) -> list:
        h = self.round.get(seat)
        if h is not None and h.participant is self.seats[seat].participant and not h.decided \
                and self.phase in ("dealing", "deciding"):
            return self._act(seat, 0, now, reason="left")
        return []

    # ------------------------------------------------------------------ deciding
    def play_action(self, seat: int, action: str, now: float) -> list:
        if self.phase != "deciding":
            raise TableError("It's not time to decide.")
        h = self.round.get(seat)
        if h is None or h.participant is not self.seats[seat].participant:
            raise TableError("You're not in this hand.")
        if h.decided:
            raise TableError("You've already decided.")
        self._box_first(seat)
        if action not in ACTIONS:
            raise TableError("Fold, or raise.")
        times = ACTIONS[action]
        allowed = hcf.max_raise(hcf.best_flush(h.cards)[0])
        if times > allowed:
            raise TableError(f"With that flush you can raise at most {allowed}x.")
        return self._act(seat, times, now)

    def _act(self, seat: int, times: int, now: float, reason: str = "") -> list:
        h = self.round[seat]
        h.decided = True
        event = {"kind": "hcf_action", "seat": seat, "times": times}
        if reason:
            event["reason"] = reason
        if times and not h.participant.debit(h.bets.ante * times, "raise"):
            times, event["times"], event["reason"] = 0, 0, "funds"
        if times:
            h.bets.raise_bet = h.bets.ante * times
            event.update(amount=h.bets.raise_bet, _paid=[h.participant])
            h.flush = hcf.best_flush(h.cards)[2]
        else:
            h.folded = True
        h.held = self._held(h)
        event.update(flush_count=len(h.flush), held_count=len(h.held),
                     _private={seat: {"flush": [c.code for c in h.flush], "held": [c.code for c in h.held]}})
        return [event] + self._all_decided(now)

    @staticmethod
    def _held(h: Hand) -> list:
        """A straight flush (3+) to tuck under the Straight Flush bet: one in
        another suit than a raised hand's flush, or any after a fold -- only
        if the Straight Flush bet or the Jackpot is riding on it."""
        if not (h.bets.straight_flush or h.bets.jackpot):
            return []
        skip = h.flush[0].suit if h.flush else None
        run = hcf.straight_flush_cards(h.cards, skip_suit=skip)
        return run if len(run) >= 3 else []

    def _all_decided(self, now: float) -> list:
        if self.phase == "deciding" and all(h.decided for h in self.round.values()):
            end = now + self.timings.last_decision
            if self.deadline is None or end < self.deadline:
                self.deadline = end
        return self._reveal_boxes()

    # ------------------------------------------------------------------ the clock
    def _advance(self, now: float) -> list:
        if self.phase == "betting":
            return self._close_betting(now)
        if self.phase == "dealing":
            return self._open_decisions(now)
        if self.phase == "deciding":
            events = []
            for seat in sorted(self.round):
                if not self.round[seat].decided:
                    events += self._timed_out(seat) + self._act(seat, 0, now, reason="timeout")
            return events + self._sweep_folds(now)
        if self.phase == "sweeping":
            return self._dealer_reveal(now)
        if self.phase == "reveal":
            return self._start_settling(now)
        if self.phase == "settling":
            return self._settle_next(now)
        if self.phase == "clearing":
            return self._open_betting(now)
        return []

    # ------------------------------------------------------------------ round flow
    def _close_betting(self, now: float) -> list:
        events, taken = self._take_bets(now)
        if not taken:
            return events
        deck = self.deck_factory()
        self.round = {i: Hand(self.seats[i].participant,
                              hcf.Bets(b["ante"], b["flush"], b["straight_flush"], b["jackpot"]), deck.deal(7))
                      for i, b in sorted(taken.items())}
        self.dealer_cards = deck.deal(7)
        self.dealer_shown = False
        self.phase = "dealing"
        order = [[who, c] for who in sorted(self.round) for c in range(7)] + [["dealer", c] for c in range(7)]
        jackpots = [i for i in sorted(taken) if taken[i]["jackpot"]]
        t = self.timings
        duration = len(order) * t.deal_card + (len(self.round) + 1) * t.deal_hand_pause + t.deal_pause
        if jackpots:
            duration += t.jackpot_lock
        self.deadline = now + duration
        events.append({"kind": "bets_closed", "seats": sorted(taken), "jackpots": jackpots,
                       "_paid": [self.seats[i].participant for i in sorted(taken)]})
        events += say(self.lines.say("table", "no_more_bets"))
        events.append({"kind": "dealt", "order": order, "interval": t.deal_card, "hand_pause": t.deal_hand_pause,
                       "_private": {i: self._mine(h) for i, h in self.round.items()}})
        return events

    @staticmethod
    def _mine(h: Hand) -> dict:
        length, values, flush = hcf.best_flush(h.cards)
        return {"cards": [c.code for c in h.cards], "hand": hcf.flush_label(length, values),
                "flush": [c.code for c in flush], "max_raise": hcf.max_raise(length)}

    def _box_private(self, seat: int) -> dict:
        return self._mine(self.round[seat])

    def _open_decisions(self, now: float) -> list:
        self.phase = "deciding"
        self.deadline = now + self.timings.decide
        return [{"kind": "decisions_open", "seconds": self.timings.decide, "seats": sorted(self.round),
                 "_private": {i: self._mine(h) for i, h in self.round.items()}}] + \
            say(self.lines.say("high_card_flush", "decide"))

    def _sweep_folds(self, now: float) -> list:
        """The dealer takes the folded hands (with the Ante, the Flush bonus and,
        unless a straight flush is tucked under it, the other side bets) and
        every raised hand's unused cards."""
        self.phase = "sweeping"
        seats = []
        for seat in sorted(self.round, reverse=True):
            h = self.round[seat]
            if h.swept:
                continue
            h.swept = True
            steps = []
            if h.folded:
                lost = [("ante", h.bets.ante), ("flush", h.bets.flush)]
                if not h.held:
                    lost += [("straight_flush", h.bets.straight_flush), ("jackpot", h.bets.jackpot)]
                steps = [{"spot": s, "amount": a} for s, a in lost if a > 0]
            seats.append({"seat": seat, "steps": steps, "cards": len(h.unused)})
        t = self.timings
        self.deadline = now + ((t.sweep_pause + t.sweep_each) * len(seats) + 0.4 * t.sweep_each if seats else 0.0)
        return [{"kind": "fold_sweep", "seats": seats, "pause": t.sweep_pause}] if seats else []

    def _dealer_reveal(self, now: float) -> list:
        self.phase = "reveal"
        if not any(not h.folded for h in self.round.values()):
            return self._start_settling(now)  # nobody's left to play against the dealer
        self.dealer_shown = True
        length, values, flush = hcf.best_flush(self.dealer_cards)
        qualified = hcf.dealer_qualifies(length, values[0] if values else 0)
        self.deadline = now + self.timings.reveal
        label = hcf.flush_label(length, values)
        line = self.lines.say("high_card_flush", "qualifies" if qualified else "no_qualify", dealer=label)
        return [{"kind": "dealer_reveal", "cards": [c.code for c in self.dealer_cards], "hand": label,
                 "flush": [c.code for c in flush], "qualified": qualified}] + say(line)

    def _start_settling(self, now: float) -> list:
        self.phase = "settling"
        for h in self.round.values():
            r = hcf.settle(h.cards, self.dealer_cards, h.bets, h.folded)
            if h.folded:  # house rule: a fold loses the Flush bonus; only a tucked straight flush still pays
                r.flush_return = 0
                if not h.held:
                    r.straight_flush_return, r.jackpot_fixed, r.jackpot_share = 0, 0, 0.0
            h.result = r
        self._settle_queue = [i for i in sorted(self.round, reverse=True) if self.round[i].in_settle]
        return self._settle_next(now)

    def _settle_next(self, now: float) -> list:
        if not self._settle_queue:
            self.phase = "clearing"
            self.deadline = now + self.timings.clear
            return [{"kind": "round_end"}]
        seat = self._settle_queue.pop(0)
        h = self.round[seat]
        h.settled = True
        r = h.result
        events = []
        pool = 0
        if r.jackpot_share and self.jackpot:
            pool = self.jackpot.win() if r.jackpot_share >= 1.0 else self.jackpot.take(r.jackpot_share)
            events.append({"kind": "jackpot_won", "seat": seat, "amount": pool, "name": h.participant.name})
        h.paid = r.total_returned + pool
        h.participant.credit(h.paid, r.outcome)
        steps = self._steps(h, r, pool)
        t = self.timings
        self.deadline = now + t.settle_base + 2 * t.settle_pause + t.settle_step * len(steps)
        label = hcf.flush_label(*r.flush)
        key = "side_bets" if h.folded else {"no_qualify": "no_qualify_win"}.get(r.outcome, r.outcome)
        line = self.lines.say("high_card_flush", key, name=h.participant.name, hand=label,
                              dealer=hcf.flush_label(*r.dealer_flush))
        events.append({"kind": "settle_seat", "seat": seat, "outcome": r.outcome,
                       "flush": [c.code for c in h.flush], "held": [c.code for c in h.held],
                       "hand": label, "straight_flush": r.straight_flush,
                       "steps": steps, "total_returned": h.paid, "say": line, "pause": t.settle_pause,
                       "_paid": [h.participant]})
        return events

    @staticmethod
    def _steps(h: Hand, r: hcf.Result, pool: int) -> list:
        """A raised hand: every bet. A fold kept alive by a tucked straight flush:
        just the Straight Flush bet and the Jackpot (the rest went with the fold)."""
        stakes = [] if h.folded else [("ante", h.bets.ante, r.ante_return), ("raise", h.bets.raise_bet, r.raise_return),
                                      ("flush", h.bets.flush, r.flush_return)]
        stakes += [("straight_flush", h.bets.straight_flush, r.straight_flush_return)]
        steps = []
        for spot, bet, ret in stakes:
            if bet <= 0:
                continue
            if ret == 0:
                steps.append({"spot": spot, "action": "collect", "amount": bet})
            elif ret == bet:
                steps.append({"spot": spot, "action": "push", "amount": bet})
            else:
                steps.append({"spot": spot, "action": "pay", "amount": bet, "payout": ret - bet})
        if h.bets.jackpot:
            win = r.jackpot_fixed + pool
            steps.append({"spot": "jackpot", "action": "pay", "amount": h.bets.jackpot, "payout": win} if win
                         else {"spot": "jackpot", "action": "collect", "amount": h.bets.jackpot})
        return sorted(steps, key=lambda s: s["action"] != "collect")

    def _open_betting(self, now: float) -> list:
        self.round = {}
        self.dealer_cards = []
        self.dealer_shown = False
        self._settle_queue = []
        return self._reopen_betting(now)

    # ------------------------------------------------------------------ snapshot
    def snapshot(self, viewer: int | None, now: float) -> dict:
        seats = []
        for i, s in enumerate(self.seats):
            if s.participant is None:
                seats.append(None)
                continue
            seats.append({**self._seat_entry(i, s), "cards": [], "hand": None, "folded": False, "decided": False,
                          "raise": 0, "result": None})
        for i, h in self.round.items():
            entry = seats[i]
            if entry is None or entry["entity"] != h.participant.entity_id:
                continue
            gone = h.folded and h.swept  # what went with a swept fold
            entry["bets"] = {"ante": 0 if gone else h.bets.ante, "flush": 0 if gone else h.bets.flush,
                             "straight_flush": 0 if gone and not h.held else h.bets.straight_flush,
                             "jackpot": 0 if gone and not h.held else h.bets.jackpot}
            entry["raise"], entry["folded"], entry["decided"] = h.bets.raise_bet, h.folded, h.decided
            if h.settled:
                entry["cards"] = [c.code for c in h.flush + h.held]
                entry["result"] = {"outcome": h.result.outcome, "returned": h.paid}
            elif h.decided:  # arranged: flush in front, any straight flush tucked, the rest aside until swept
                show = self._sees(viewer, i)
                kept = h.flush + h.held + ([] if h.swept else h.unused)
                entry["cards"] = [c.code if show else "??" for c in kept]
                entry["flush_count"], entry["held_count"] = len(h.flush), len(h.held)
                entry["hand"] = self._mine(h)["hand"] if show else None
            else:
                show = self._sees(viewer, i)
                entry["cards"] = [c.code if show else "??" for c in h.cards]
                entry["hand"] = self._mine(h)["hand"] if show else None
        if self.dealer_shown:  # the dealer's flush, in front; the rest has been swept
            dealer = [c.code for c in hcf.best_flush(self.dealer_cards)[2]]
        else:
            dealer = ["??"] * len(self.dealer_cards)
        timer = self._timer(now, ("betting", "deciding"))
        return {"game": self.game, "phase": self.phase, "seats": seats, "dealer": {"cards": dealer},
                "timer": timer, "my_seat": viewer}
